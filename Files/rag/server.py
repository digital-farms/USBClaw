#!/usr/bin/env python3
"""
RAG Proxy Server for AI USB Assistant
--------------------------------------
Lightweight BM25-based retrieval proxy.
Sits between the user and llama-server, injecting document context into prompts.

Zero external dependencies — Python stdlib only.

Usage:
    python server.py [--port 8085] [--llama-port 8080]
"""

import os
import sys
import json
import math
import re
import time
import hashlib
import argparse
import threading
from collections import Counter, defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from pathlib import Path
from io import BytesIO
import mimetypes

# Tools module (safe read-only system tools)
try:
    from tools import (
        get_tools_openai_format, execute_tool, init_allowed_roots,
        TOOL_REGISTRY
    )
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    print("  [WARN] tools.py not found — tools feature disabled")

# ============================================================
#  Paths
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent  # Files/
DOCS_DIR = BASE_DIR / "data" / "docs"
INDEX_DIR = BASE_DIR / "data" / "index"
INJECT_JS = Path(__file__).resolve().parent / "inject.js"

CHUNKS_FILE = INDEX_DIR / "chunks.json"
INDEX_FILE = INDEX_DIR / "bm25_index.json"
META_FILE = INDEX_DIR / "meta.json"

# ============================================================
#  Global State
# ============================================================
rag_enabled = False
reasoning_enabled = False
tools_enabled = False
rag_lock = threading.Lock()
is_indexing = False
bm25 = None          # BM25Engine instance
chunks = []          # list of {"id", "text", "source", "offset"}
index_meta = {}      # {"doc_count", "chunk_count", "indexed_at", "files"}

MAX_TOOL_ROUNDS = 3  # Max tool call iterations per request

LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
RAG_PORT = 8085

# ============================================================
#  BM25 Engine
# ============================================================
STOP_WORDS_EN = frozenset([
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "and",
    "or", "for", "with", "as", "by", "this", "that", "from", "are", "was",
    "were", "be", "been", "has", "have", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "not", "no", "but", "if",
    "so", "than", "too", "very", "can", "just", "about", "into", "over",
    "after", "before", "between", "under", "again", "then", "once", "all",
    "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "also", "how", "what", "which", "who", "whom",
    "when", "where", "why",
])

STOP_WORDS = STOP_WORDS_EN

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text):
    """Simple whitespace + regex tokenizer with lowercasing and stop word removal."""
    tokens = TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


class BM25Engine:
    """BM25 search engine. Pure Python, no dependencies."""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avgdl = 0.0
        self.doc_lens = []          # [int] length of each doc in tokens
        self.doc_freqs = {}         # {term: int} number of docs containing term
        self.term_freqs = []        # [{term: int}] per-doc term frequencies
        self.idf_cache = {}

    def build(self, documents):
        """Build index from list of strings (one per chunk)."""
        self.doc_count = len(documents)
        self.doc_lens = []
        self.term_freqs = []
        self.doc_freqs = defaultdict(int)

        for doc in documents:
            tokens = tokenize(doc)
            tf = Counter(tokens)
            self.term_freqs.append(dict(tf))
            self.doc_lens.append(len(tokens))
            for term in tf:
                self.doc_freqs[term] += 1

        total_len = sum(self.doc_lens)
        self.avgdl = total_len / self.doc_count if self.doc_count > 0 else 1.0
        self.doc_freqs = dict(self.doc_freqs)
        self._compute_idf()

    def _compute_idf(self):
        """Precompute IDF for all terms."""
        self.idf_cache = {}
        N = self.doc_count
        for term, df in self.doc_freqs.items():
            self.idf_cache[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query, top_k=5):
        """Search for query, return list of (doc_index, score)."""
        if self.doc_count == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * self.doc_count

        for term in query_tokens:
            idf = self.idf_cache.get(term, 0.0)
            if idf <= 0:
                continue
            for i in range(self.doc_count):
                tf = self.term_freqs[i].get(term, 0)
                if tf == 0:
                    continue
                dl = self.doc_lens[i]
                num = tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += idf * (num / den)

        # Get top-k
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, score) for idx, score in ranked[:top_k] if score > 0]

    def to_dict(self):
        return {
            "k1": self.k1,
            "b": self.b,
            "doc_count": self.doc_count,
            "avgdl": self.avgdl,
            "doc_lens": self.doc_lens,
            "doc_freqs": self.doc_freqs,
            "term_freqs": self.term_freqs,
        }

    @classmethod
    def from_dict(cls, d):
        eng = cls(k1=d["k1"], b=d["b"])
        eng.doc_count = d["doc_count"]
        eng.avgdl = d["avgdl"]
        eng.doc_lens = d["doc_lens"]
        eng.doc_freqs = d["doc_freqs"]
        eng.term_freqs = d["term_freqs"]
        eng._compute_idf()
        return eng


# ============================================================
#  Document Chunker
# ============================================================
SUPPORTED_EXT = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"}
CHUNK_SIZE = 500      # characters per chunk
CHUNK_OVERLAP = 100   # overlap between chunks


def read_documents(docs_dir):
    """Read all supported files from docs directory. Returns [(filename, content)]."""
    results = []
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        return results

    for fpath in sorted(docs_path.rglob("*")):
        if fpath.is_file() and fpath.suffix.lower() in SUPPORTED_EXT:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                rel = fpath.relative_to(docs_path)
                results.append((str(rel), content))
            except Exception as e:
                print(f"  [WARN] Cannot read {fpath}: {e}")
    return results


def chunk_text(text, source, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    text = text.strip()
    if not text:
        return []

    result = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence/paragraph boundary
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", "! ", "? ", "; ", ", "]:
                last_sep = chunk.rfind(sep)
                if last_sep > chunk_size * 0.3:
                    chunk = chunk[:last_sep + len(sep)]
                    end = start + len(chunk)
                    break

        chunk = chunk.strip()
        if chunk:
            result.append({
                "id": f"{source}:{idx}",
                "text": chunk,
                "source": source,
                "offset": start,
            })
            idx += 1

        start = end - overlap
        if start <= (end - chunk_size):
            start = end  # prevent infinite loop

    return result


# ============================================================
#  Index Management
# ============================================================
def build_index():
    """Read docs, chunk, build BM25 index, save to disk."""
    global bm25, chunks, index_meta, is_indexing

    is_indexing = True
    print(f"\n  [RAG] Indexing documents from {DOCS_DIR}...")

    try:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)

        docs = read_documents(DOCS_DIR)
        if not docs:
            print("  [RAG] No documents found.")
            is_indexing = False
            return {"ok": False, "error": "No documents found in data/docs/"}

        all_chunks = []
        for filename, content in docs:
            file_chunks = chunk_text(content, filename)
            all_chunks.extend(file_chunks)
            print(f"  [RAG]   {filename}: {len(file_chunks)} chunks")

        if not all_chunks:
            is_indexing = False
            return {"ok": False, "error": "Documents are empty"}

        engine = BM25Engine()
        engine.build([c["text"] for c in all_chunks])

        # Save
        with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False)

        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(engine.to_dict(), f)

        meta = {
            "doc_count": len(docs),
            "chunk_count": len(all_chunks),
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": [d[0] for d in docs],
        }
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        with rag_lock:
            bm25 = engine
            chunks = all_chunks
            index_meta = meta

        print(f"  [RAG] Done: {len(docs)} files, {len(all_chunks)} chunks")
        return {"ok": True, "doc_count": len(docs), "chunk_count": len(all_chunks)}

    except Exception as e:
        print(f"  [RAG] Index error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        is_indexing = False


def load_index():
    """Load saved index from disk if exists."""
    global bm25, chunks, index_meta

    if not CHUNKS_FILE.exists() or not INDEX_FILE.exists():
        return False

    try:
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            bm25 = BM25Engine.from_dict(json.load(f))
        if META_FILE.exists():
            with open(META_FILE, "r", encoding="utf-8") as f:
                index_meta = json.load(f)
        print(f"  [RAG] Loaded index: {len(chunks)} chunks from {index_meta.get('doc_count', '?')} files")
        return True
    except Exception as e:
        print(f"  [RAG] Failed to load index: {e}")
        return False


def search_chunks(query, top_k=5):
    """Search indexed chunks. Returns list of chunk dicts with scores."""
    if bm25 is None or not chunks:
        return []

    results = bm25.search(query, top_k=top_k)
    return [
        {**chunks[idx], "score": round(score, 3)}
        for idx, score in results
    ]


# ============================================================
#  Prompt Augmentation
# ============================================================
RAG_SYSTEM_TEMPLATE = """You have access to the following excerpts from local documents. Use them to answer the user's question when relevant. If the documents don't contain the answer, say so and answer based on your own knowledge.

--- DOCUMENTS ---
{context}
--- END DOCUMENTS ---"""


def augment_messages(messages):
    """If RAG is on, find relevant chunks and inject context into messages."""
    if not rag_enabled or bm25 is None:
        return messages

    # Find the last user message
    user_query = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_query = content
            elif isinstance(content, list):
                # OAI format with text parts
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        user_query = part.get("text", "")
                        break
            break

    if not user_query:
        return messages

    results = search_chunks(user_query, top_k=5)
    if not results:
        return messages

    # Build context string
    context_parts = []
    for r in results:
        context_parts.append(f"[{r['source']}]\n{r['text']}")
    context = "\n\n".join(context_parts)

    rag_system = RAG_SYSTEM_TEMPLATE.format(context=context)

    # Inject as system message
    augmented = list(messages)
    # Check if there's already a system message
    if augmented and augmented[0].get("role") == "system":
        augmented[0] = {
            "role": "system",
            "content": augmented[0]["content"] + "\n\n" + rag_system
        }
    else:
        augmented.insert(0, {"role": "system", "content": rag_system})

    print(f"  [RAG] Injected {len(results)} chunks into prompt")
    return augmented


# ============================================================
#  HTTP Proxy Handler
# ============================================================
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class RAGHandler(BaseHTTPRequestHandler):
    """Proxies requests to llama-server, intercepts chat completions for RAG."""

    server_version = "RAGProxy/1.0"

    def log_message(self, fmt, *args):
        # Quieter logging
        try:
            msg = fmt % args if args else fmt
        except Exception:
            msg = str(fmt)
        if "/rag/" in msg:
            return
        sys.stderr.write(f"  [PROXY] {msg}\n")

    # ---------- Routing ----------

    def do_GET(self):
        if self.path == "/rag/inject.js":
            self._serve_inject_js()
        elif self.path.startswith("/rag/status"):
            self._handle_rag_status()
        elif self.path == "/rag/files":
            self._handle_list_files()
        elif self.path == "/rag/tools/status":
            self._handle_tools_status()
        else:
            self._proxy_get()

    def do_POST(self):
        if self.path == "/rag/reindex":
            self._handle_reindex()
        elif self.path == "/rag/toggle":
            self._handle_toggle()
        elif self.path == "/rag/reasoning":
            self._handle_reasoning_toggle()
        elif self.path == "/rag/tools/toggle":
            self._handle_tools_toggle()
        elif self.path == "/rag/search":
            self._handle_search()
        elif self.path == "/rag/upload":
            self._handle_upload()
        elif self.path == "/v1/chat/completions":
            self._handle_chat_completions()
        else:
            self._proxy_post()

    def do_DELETE(self):
        if self.path.startswith("/rag/files/"):
            self._handle_delete_file()
        else:
            self._send_error(404, "Not found")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    # ---------- RAG Endpoints ----------

    def _handle_rag_status(self):
        global rag_enabled, reasoning_enabled, tools_enabled, index_meta, is_indexing
        status = {
            "rag_enabled": rag_enabled,
            "reasoning_enabled": reasoning_enabled,
            "tools_enabled": tools_enabled,
            "tools_available": TOOLS_AVAILABLE,
            "is_indexing": is_indexing,
            "has_index": bm25 is not None,
            "meta": index_meta,
        }
        self._send_json(200, status)

    def _handle_reindex(self):
        if is_indexing:
            self._send_json(409, {"ok": False, "error": "Indexing already in progress"})
            return

        # Run in background thread
        def do_reindex():
            result = build_index()
            # result is stored in globals

        t = threading.Thread(target=do_reindex, daemon=True)
        t.start()
        self._send_json(202, {"ok": True, "message": "Indexing started"})

    def _handle_toggle(self):
        global rag_enabled
        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if "enabled" in data:
            rag_enabled = bool(data["enabled"])
        else:
            rag_enabled = not rag_enabled

        self._send_json(200, {"rag_enabled": rag_enabled})
        print(f"  [RAG] {'Enabled' if rag_enabled else 'Disabled'}")

    def _handle_reasoning_toggle(self):
        global reasoning_enabled
        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if "enabled" in data:
            reasoning_enabled = bool(data["enabled"])
        else:
            reasoning_enabled = not reasoning_enabled

        self._send_json(200, {"reasoning_enabled": reasoning_enabled})
        print(f"  [REASONING] {'Enabled' if reasoning_enabled else 'Disabled'}")

    def _handle_tools_toggle(self):
        global tools_enabled
        if not TOOLS_AVAILABLE:
            self._send_json(400, {"ok": False, "error": "Tools module not available"})
            return

        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if "enabled" in data:
            tools_enabled = bool(data["enabled"])
        else:
            tools_enabled = not tools_enabled

        self._send_json(200, {"tools_enabled": tools_enabled})
        print(f"  [TOOLS] {'Enabled' if tools_enabled else 'Disabled'}")

    def _handle_tools_status(self):
        tool_list = []
        if TOOLS_AVAILABLE:
            for name, spec in TOOL_REGISTRY.items():
                tool_list.append({
                    "name": name,
                    "description": spec["description"],
                })
        self._send_json(200, {
            "tools_enabled": tools_enabled,
            "tools_available": TOOLS_AVAILABLE,
            "tools": tool_list,
        })

    def _handle_search(self):
        body = self._read_body()
        try:
            data = json.loads(body)
            query = data.get("query", "")
            top_k = data.get("top_k", 5)
        except (json.JSONDecodeError, AttributeError):
            self._send_json(400, {"error": "Invalid JSON"})
            return

        results = search_chunks(query, top_k)
        self._send_json(200, {"results": results})

    # ---------- File Management ----------

    def _handle_list_files(self):
        """List all files in docs directory."""
        files = []
        if DOCS_DIR.exists():
            for fpath in sorted(DOCS_DIR.rglob("*")):
                if fpath.is_file() and fpath.name != ".gitkeep":
                    try:
                        stat = fpath.stat()
                        rel = str(fpath.relative_to(DOCS_DIR)).replace("\\", "/")
                        files.append({
                            "name": rel,
                            "size": stat.st_size,
                            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                        })
                    except Exception:
                        pass
        self._send_json(200, {"files": files})

    def _handle_upload(self):
        """Handle file upload (multipart/form-data)."""
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            # Parse multipart
            try:
                boundary = content_type.split("boundary=")[1].strip()
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                # Simple multipart parser
                files_saved = []
                parts = body.split(("--" + boundary).encode())
                for part in parts:
                    if b"filename=" not in part:
                        continue

                    # Extract filename
                    header_end = part.find(b"\r\n\r\n")
                    if header_end == -1:
                        continue
                    header_text = part[:header_end].decode("utf-8", errors="replace")
                    file_data = part[header_end + 4:]
                    # Strip trailing \r\n
                    if file_data.endswith(b"\r\n"):
                        file_data = file_data[:-2]
                    if file_data.endswith(b"--"):
                        file_data = file_data[:-2]
                    if file_data.endswith(b"\r\n"):
                        file_data = file_data[:-2]

                    # Get filename from Content-Disposition
                    fname_match = re.search(r'filename="([^"]+)"', header_text)
                    if not fname_match:
                        fname_match = re.search(r"filename=([^\s;]+)", header_text)
                    if not fname_match:
                        continue

                    filename = fname_match.group(1)
                    # Sanitize filename
                    filename = Path(filename).name
                    if not filename:
                        continue

                    # Check extension
                    ext = Path(filename).suffix.lower()
                    if ext not in SUPPORTED_EXT:
                        self._send_json(400, {
                            "ok": False,
                            "error": f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXT))}"
                        })
                        return

                    # Save
                    DOCS_DIR.mkdir(parents=True, exist_ok=True)
                    dest = DOCS_DIR / filename
                    dest.write_bytes(file_data)
                    files_saved.append(filename)
                    print(f"  [RAG] Uploaded: {filename} ({len(file_data)} bytes)")

                if files_saved:
                    self._send_json(200, {"ok": True, "files": files_saved})
                else:
                    self._send_json(400, {"ok": False, "error": "No valid files in upload"})

            except Exception as e:
                self._send_json(500, {"ok": False, "error": f"Upload failed: {e}"})
        else:
            self._send_json(400, {"ok": False, "error": "Expected multipart/form-data"})

    def _handle_delete_file(self):
        """Delete a file from docs directory."""
        # /rag/files/filename.txt
        filename = self.path[len("/rag/files/"):]
        filename = filename.replace("/", os.sep)

        if not filename or ".." in filename:
            self._send_json(400, {"ok": False, "error": "Invalid filename"})
            return

        fpath = DOCS_DIR / filename
        if not fpath.exists():
            self._send_json(404, {"ok": False, "error": "File not found"})
            return

        # Safety: ensure file is inside DOCS_DIR
        try:
            fpath.resolve().relative_to(DOCS_DIR.resolve())
        except ValueError:
            self._send_json(403, {"ok": False, "error": "Access denied"})
            return

        try:
            fpath.unlink()
            print(f"  [RAG] Deleted: {filename}")
            self._send_json(200, {"ok": True, "deleted": filename})
        except Exception as e:
            self._send_json(500, {"ok": False, "error": str(e)})

    # ---------- Chat Completions Intercept ----------

    def _handle_chat_completions(self):
        """Intercept chat completions — augment with RAG if enabled, run tool loop if tools enabled, then proxy."""
        body = self._read_body()

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            # Can't parse — just proxy as-is
            self._proxy_raw_post(body)
            return

        # Augment messages if RAG is on
        if rag_enabled and bm25 is not None:
            data["messages"] = augment_messages(data.get("messages", []))

        # Reasoning toggle
        if not reasoning_enabled:
            data["chat_template_kwargs"] = {"enable_thinking": False}
            data["reasoning_budget"] = 0
        else:
            data["chat_template_kwargs"] = {"enable_thinking": True}
            data["reasoning_budget"] = -1

        # If tools not enabled or not available, just proxy
        if not tools_enabled or not TOOLS_AVAILABLE:
            body = json.dumps(data).encode("utf-8")
            self._proxy_raw_post(body)
            return

        # === Tool calling loop ===
        # Strategy: disable reasoning for intermediate "tool picker" rounds
        # to make them fast, then re-enable reasoning for the final answer.
        original_stream = data.get("stream", False)
        original_reasoning = reasoning_enabled
        tools_defs = get_tools_openai_format()
        data["tools"] = tools_defs
        tool_calls_log = []  # Track what tools were called for UI
        url = f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions"

        # Hint: call ALL needed tools at once to minimize slow round-trips
        messages = data.get("messages", [])
        messages.insert(0, {
            "role": "system",
            "content": (
                "IMPORTANT: When using tools, call ALL the tools you need in a SINGLE response. "
                "Do NOT call tools one at a time. Batch all tool calls together."
            ),
        })

        for round_num in range(MAX_TOOL_ROUNDS):
            # Intermediate rounds: no streaming, no reasoning, short output
            data["stream"] = False
            data["chat_template_kwargs"] = {"enable_thinking": False}
            data["reasoning_budget"] = 0
            data["max_tokens"] = 512      # Limit output — only need tool call JSON
            data["n_predict"] = 512       # llama.cpp alias

            req_body = json.dumps(data).encode("utf-8")
            print(f"  [TOOLS] Round {round_num + 1}: asking LLM to pick tools...")

            try:
                req = Request(url, data=req_body, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Content-Length", str(len(req_body)))

                resp = urlopen(req, timeout=300)
                resp_body = resp.read()
                resp_data = json.loads(resp_body)
            except Exception as e:
                self._send_error(502, f"Cannot reach llama-server: {e}")
                return

            # Check if model returned tool calls
            choices = resp_data.get("choices", [])
            if not choices:
                self._send_tool_response(resp_data, tool_calls_log, original_stream)
                return

            message = choices[0].get("message", {})
            finish_reason = choices[0].get("finish_reason", "")
            tool_calls = message.get("tool_calls", [])

            if not tool_calls or finish_reason != "tool_calls":
                # Model gave a final text response (no more tools needed)
                # If reasoning was on, re-do this as the final answer with reasoning
                if original_reasoning and tool_calls_log:
                    break  # Fall through to final-answer block below
                self._send_tool_response(resp_data, tool_calls_log, original_stream)
                return

            # Execute ALL tool calls from this round (parallel batch)
            data["messages"].append(message)  # Add assistant message with tool_calls

            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name", "")
                fn_args_raw = tc.get("function", {}).get("arguments", "{}")
                tc_id = tc.get("id", f"call_{round_num}")

                try:
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except json.JSONDecodeError:
                    fn_args = {}

                print(f"  [TOOLS]   -> {fn_name}({json.dumps(fn_args, ensure_ascii=False)})")
                start_time = time.time()

                success, result = execute_tool(fn_name, fn_args)
                elapsed = round(time.time() - start_time, 2)

                tool_calls_log.append({
                    "name": fn_name,
                    "args": fn_args,
                    "success": success,
                    "time": elapsed,
                })

                status = "OK" if success else "FAIL"
                print(f"  [TOOLS]      {status} ({elapsed}s, {len(result)} chars)")

                data["messages"].append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result,
                })

            print(f"  [TOOLS] Round {round_num + 1} done: {len(tool_calls)} tool(s) executed")

        # Final answer: remove tools, restore reasoning, let LLM summarize
        print(f"  [TOOLS] Generating final answer ({len(tool_calls_log)} tools used)...")
        data.pop("tools", None)
        data.pop("max_tokens", None)
        data.pop("n_predict", None)

        # Restore original reasoning setting for the final answer
        if original_reasoning:
            data["chat_template_kwargs"] = {"enable_thinking": True}
            data["reasoning_budget"] = -1
        else:
            data["chat_template_kwargs"] = {"enable_thinking": False}
            data["reasoning_budget"] = 0

        # If client wants streaming, use real streaming for the final answer
        # This avoids timeout — data flows continuously from llama → proxy → client
        if original_stream:
            data["stream"] = True
            self._stream_final_with_tools(url, data, tool_calls_log)
        else:
            data["stream"] = False
            req_body = json.dumps(data).encode("utf-8")
            try:
                req = Request(url, data=req_body, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Content-Length", str(len(req_body)))
                resp = urlopen(req, timeout=600)
                resp_body = resp.read()
                resp_data = json.loads(resp_body)
                self._send_tool_response(resp_data, tool_calls_log, False)
            except Exception as e:
                self._send_error(502, f"Cannot reach llama-server: {e}")

    def _stream_final_with_tools(self, url, data, tool_calls_log):
        """Stream the final LLM answer to client, prepending tool summary as first chunk."""
        req_body = json.dumps(data).encode("utf-8")

        try:
            req = Request(url, data=req_body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Content-Length", str(len(req_body)))
            upstream = urlopen(req, timeout=600)
        except Exception as e:
            self._send_error(502, f"Cannot reach llama-server: {e}")
            return

        # Start SSE response to client
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Transfer-Encoding", "chunked")
            self._send_cors_headers()
            self.end_headers()

            def write_chunk(raw_bytes):
                self.wfile.write(f"{len(raw_bytes):x}\r\n".encode())
                self.wfile.write(raw_bytes)
                self.wfile.write(b"\r\n")

            summary_injected = False

            # Read upstream SSE line by line and forward to client
            for raw_line in upstream:
                line = raw_line.decode("utf-8", errors="replace")

                # Inject tool summary into the first content chunk
                if not summary_injected and line.startswith("data: {"):
                    try:
                        chunk_data = json.loads(line[6:])
                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        # Look for the first chunk that has content or role
                        if "content" in delta or "role" in delta:
                            if tool_calls_log:
                                summary = self._build_tool_summary(tool_calls_log)
                                # Inject summary as content before the real content
                                summary_chunk = dict(chunk_data)
                                summary_chunk["choices"] = [{
                                    "index": 0,
                                    "delta": {"content": summary + "\n\n"},
                                    "finish_reason": None,
                                }]
                                summary_line = f"data: {json.dumps(summary_chunk, ensure_ascii=False)}\n\n"
                                write_chunk(summary_line.encode("utf-8"))
                            summary_injected = True
                    except (json.JSONDecodeError, IndexError, KeyError):
                        summary_injected = True

                # Forward the original line
                write_chunk(raw_line)
                self.wfile.flush()

            # Final zero-length chunk
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            self.close_connection = True

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"  [TOOLS] Stream final error: {e}")

    def _send_tool_response(self, resp_data, tool_calls_log, as_stream):
        """Send the final tool response — as SSE if the client requested streaming."""
        # Extract content from the non-streaming response
        content = ""
        choices = resp_data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")

        # Prepend tool summary to content if tools were used
        if tool_calls_log:
            summary = self._build_tool_summary(tool_calls_log)
            content = summary + "\n\n" + content

        if not as_stream:
            # Client expects non-streaming JSON
            if choices:
                resp_data["choices"][0]["message"]["content"] = content
            self._send_json(200, resp_data)
            return

        # Client expects SSE streaming — convert to SSE format
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Transfer-Encoding", "chunked")
            self._send_cors_headers()
            self.end_headers()

            model_name = resp_data.get("model", "")
            chat_id = resp_data.get("id", "chatcmpl-tools")
            created = resp_data.get("created", int(time.time()))

            def write_sse(data_dict):
                line = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n"
                payload = line.encode("utf-8")
                # Chunked transfer encoding: size in hex + \r\n + data + \r\n
                self.wfile.write(f"{len(payload):x}\r\n".encode())
                self.wfile.write(payload)
                self.wfile.write(b"\r\n")

            # First chunk: role announcement (required by llama.cpp WebUI)
            role_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }],
            }
            write_sse(role_chunk)

            # Send content in chunks to simulate streaming
            chunk_size = 20  # characters per chunk
            for i in range(0, len(content), chunk_size):
                text_chunk = content[i:i + chunk_size]
                chunk_data = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": text_chunk},
                        "finish_reason": None,
                    }],
                }
                write_sse(chunk_data)

            # Send finish chunk
            finish_data = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }],
            }
            write_sse(finish_data)

            # Send [DONE] marker
            done_line = b"data: [DONE]\n\n"
            self.wfile.write(f"{len(done_line):x}\r\n".encode())
            self.wfile.write(done_line)
            self.wfile.write(b"\r\n")

            # Final zero-length chunk to signal end of chunked transfer
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"  [TOOLS] SSE send error: {e}")

    @staticmethod
    def _build_tool_summary(tool_calls_log):
        """Build a markdown summary of tool calls."""
        lines = ["> **Tools used:**"]
        for tc in tool_calls_log:
            icon = "\u2705" if tc["success"] else "\u274c"
            lines.append(f"> {icon} `{tc['name']}` ({tc['time']}s)")
        return "\n".join(lines)

    # ---------- Proxy Methods ----------

    def _proxy_get(self):
        """Proxy GET request to llama-server, inject script into HTML."""
        url = f"http://{LLAMA_HOST}:{LLAMA_PORT}{self.path}"
        try:
            req = Request(url)
            # Forward headers (except Host)
            for key, val in self.headers.items():
                if key.lower() not in ("host", "accept-encoding"):
                    req.add_header(key, val)

            resp = urlopen(req, timeout=30)
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")

            # Inject our JS into HTML responses
            if "text/html" in content_type:
                content = self._inject_script(content)

            self.send_response(resp.status)
            for key, val in resp.headers.items():
                if key.lower() not in ("transfer-encoding", "content-length", "content-encoding"):
                    self.send_header(key, val)
            self.send_header("Content-Length", len(content))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)

        except (URLError, HTTPError) as e:
            self._send_error(502, f"Cannot reach llama-server: {e}")
        except Exception as e:
            self._send_error(500, str(e))

    def _proxy_post(self):
        """Proxy POST request to llama-server."""
        body = self._read_body()
        self._proxy_raw_post(body)

    def _proxy_raw_post(self, body):
        """Send raw POST body to llama-server and stream response back."""
        url = f"http://{LLAMA_HOST}:{LLAMA_PORT}{self.path}"
        try:
            req = Request(url, data=body if isinstance(body, bytes) else body.encode("utf-8"), method="POST")
            for key, val in self.headers.items():
                if key.lower() not in ("host", "accept-encoding", "content-length"):
                    req.add_header(key, val)
            req.add_header("Content-Length", str(len(body) if isinstance(body, bytes) else len(body.encode("utf-8"))))

            resp = urlopen(req, timeout=600)

            # Send response headers
            self.send_response(resp.status)
            is_stream = False
            for key, val in resp.headers.items():
                if key.lower() not in ("transfer-encoding", "content-encoding"):
                    self.send_header(key, val)
                if key.lower() == "content-type" and "text/event-stream" in val:
                    is_stream = True
            self._send_cors_headers()
            self.end_headers()

            # Stream response
            if is_stream:
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                content = resp.read()
                self.wfile.write(content)

        except (URLError, HTTPError) as e:
            self._send_error(502, f"Cannot reach llama-server: {e}")
        except BrokenPipeError:
            pass  # Client disconnected during stream
        except Exception as e:
            self._send_error(500, str(e))

    # ---------- Helpers ----------

    def _inject_script(self, html_bytes):
        """Inject RAG control script into HTML."""
        html = html_bytes.decode("utf-8", errors="replace")
        inject_tag = '\n<script src="/rag/inject.js"></script>\n'
        # Try to inject before </head> or </body> or at the end
        if "</head>" in html:
            html = html.replace("</head>", inject_tag + "</head>", 1)
        elif "</body>" in html:
            html = html.replace("</body>", inject_tag + "</body>", 1)
        else:
            html += inject_tag
        return html.encode("utf-8")

    def _serve_inject_js(self):
        """Serve the inject.js file."""
        try:
            content = INJECT_JS.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", len(content))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_error(404, "inject.js not found")

    def _read_body(self):
        """Read request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length)
        return b""

    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code, message):
        self._send_json(code, {"error": {"message": message, "code": code}})

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")


# ============================================================
#  Main
# ============================================================
def main():
    global LLAMA_PORT, RAG_PORT

    parser = argparse.ArgumentParser(description="RAG Proxy for AI USB Assistant")
    parser.add_argument("--port", type=int, default=8085, help="Proxy port (default: 8085)")
    parser.add_argument("--llama-port", type=int, default=8080, help="llama-server port (default: 8080)")
    args = parser.parse_args()

    RAG_PORT = args.port
    LLAMA_PORT = args.llama_port

    # Ensure directories exist
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing index
    if load_index():
        print(f"  [RAG] Index ready")
    else:
        print(f"  [RAG] No index found. Place documents in {DOCS_DIR}")
        print(f"  [RAG] Then click 'Reindex' in the UI or POST /rag/reindex")

    print()
    print(f"  ============================================")
    print(f"   RAG Proxy Server")
    print(f"   Listening:    http://{LLAMA_HOST}:{RAG_PORT}")
    print(f"   Proxying to:  http://{LLAMA_HOST}:{LLAMA_PORT}")
    print(f"   Documents:    {DOCS_DIR}")
    print(f"  ============================================")
    print()

    server = ThreadedHTTPServer((LLAMA_HOST, RAG_PORT), RAGHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  [RAG] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
