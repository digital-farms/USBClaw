#!/usr/bin/env python3
"""
Safe Read-Only Tools for AI USB Assistant
------------------------------------------
Provides a whitelist of system inspection tools that the AI model can invoke.
All tools are strictly read-only. No write, delete, or exec operations.
Zero external dependencies — Python stdlib only.
"""

import os
import sys
import json
import platform
import socket
import shutil
import subprocess
import re
import time
from pathlib import Path
from datetime import datetime

# ============================================================
#  Configuration
# ============================================================
MAX_OUTPUT_CHARS = 50000
MAX_FILE_READ_BYTES = 102400      # 100 KB
MAX_LIST_ITEMS = 500
MAX_LIST_DEPTH = 3
MAX_SEARCH_RESULTS = 50
MAX_LOG_LINES = 200

# Allowed root paths — resolved at runtime
# Users home + all fixed drive roots
ALLOWED_ROOTS = []

def init_allowed_roots(extra_roots=None):
    """Initialize allowed root paths. Call once at startup."""
    global ALLOWED_ROOTS
    roots = set()

    # User home directory
    home = Path.home().resolve()
    roots.add(home)

    # All fixed drive letters on Windows
    if sys.platform == "win32":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                roots.add(drive.resolve())
    else:
        roots.add(Path("/").resolve())

    if extra_roots:
        for r in extra_roots:
            p = Path(r).resolve()
            if p.exists():
                roots.add(p)

    ALLOWED_ROOTS = sorted(roots, key=lambda p: str(p))


# ============================================================
#  Path Validation
# ============================================================
BLOCKED_PATTERNS = [
    re.compile(r"\\\.git\\", re.IGNORECASE),
    re.compile(r"/\.git/", re.IGNORECASE),
    re.compile(r"\\node_modules\\", re.IGNORECASE),
    re.compile(r"/node_modules/", re.IGNORECASE),
]

SENSITIVE_NAMES = frozenset([
    "ntds.dit", "sam", "system", "security",       # Windows security databases
    "shadow", "passwd",                              # Linux auth
    "id_rsa", "id_ed25519", "id_ecdsa",             # SSH keys
    ".env", ".env.local", ".env.production",         # Environment secrets
    "credentials", "credentials.json",
    "keychain", "login.keychain",
    "wallet.dat",                                    # Crypto wallets
])


def validate_path(path_str):
    """
    Validate and resolve a path. Returns resolved Path or raises ToolError.
    Ensures path is within ALLOWED_ROOTS and not sensitive.
    """
    if not path_str or not isinstance(path_str, str):
        raise ToolError("Path is required")

    path_str = path_str.strip().strip("\"'")

    # Expand ~ to home
    if path_str.startswith("~"):
        path_str = str(Path.home() / path_str[1:].lstrip("/\\"))

    try:
        resolved = Path(path_str).resolve()
    except (OSError, ValueError) as e:
        raise ToolError(f"Invalid path: {e}")

    # Check within allowed roots
    if ALLOWED_ROOTS:
        allowed = False
        for root in ALLOWED_ROOTS:
            try:
                resolved.relative_to(root)
                allowed = True
                break
            except ValueError:
                continue
        if not allowed:
            raise ToolError(f"Access denied: path outside allowed directories")

    # Check blocked patterns
    path_s = str(resolved)
    for pat in BLOCKED_PATTERNS:
        if pat.search(path_s):
            raise ToolError(f"Access denied: restricted directory")

    # Check sensitive filenames (only for file reads, not listing)
    if resolved.name.lower() in SENSITIVE_NAMES:
        raise ToolError(f"Access denied: sensitive file")

    return resolved


def _truncate(text, max_chars=None):
    """Truncate text to max length."""
    limit = max_chars or MAX_OUTPUT_CHARS
    if len(text) > limit:
        return text[:limit] + f"\n\n[truncated — showing {limit} of {len(text)} characters]"
    return text


# ============================================================
#  Error Type
# ============================================================
class ToolError(Exception):
    pass


# ============================================================
#  Tool Implementations
# ============================================================

def get_system_info(**kwargs):
    """Get basic system information: OS, CPU, RAM, disk."""
    info = {}

    # OS
    info["os"] = platform.platform()
    info["os_version"] = platform.version()
    info["architecture"] = platform.machine()
    info["hostname"] = socket.gethostname()

    # CPU
    info["cpu"] = platform.processor() or "unknown"
    info["cpu_cores_logical"] = os.cpu_count() or 0

    # RAM — Windows via PowerShell (wmic deprecated on Win11)
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW
            )
            ram_data = json.loads(result.stdout.strip())
            total_kb = ram_data.get("TotalVisibleMemorySize", 0)
            free_kb = ram_data.get("FreePhysicalMemory", 0)
            if total_kb:
                info["ram_total_gb"] = round(total_kb / 1024 / 1024, 1)
                info["ram_free_gb"] = round(free_kb / 1024 / 1024, 1)
                info["ram_used_gb"] = round((total_kb - free_kb) / 1024 / 1024, 1)
        except Exception:
            info["ram"] = "unavailable"

    # Disk usage for all drives
    disks = {}
    if sys.platform == "win32":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                try:
                    usage = shutil.disk_usage(drive)
                    disks[f"{letter}:"] = {
                        "total_gb": round(usage.total / (1024**3), 1),
                        "used_gb": round(usage.used / (1024**3), 1),
                        "free_gb": round(usage.free / (1024**3), 1),
                        "used_percent": round(usage.used / usage.total * 100, 1),
                    }
                except (OSError, PermissionError):
                    pass
    else:
        try:
            usage = shutil.disk_usage("/")
            disks["/"] = {
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "used_percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            pass
    info["disks"] = disks

    # Uptime on Windows
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')"],
                capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW
            )
            boot_str = result.stdout.strip()
            if boot_str:
                boot_time = datetime.strptime(boot_str, "%Y-%m-%d %H:%M:%S")
                uptime = datetime.now() - boot_time
                days = uptime.days
                hours = uptime.seconds // 3600
                info["uptime"] = f"{days}d {hours}h"
        except Exception:
            pass

    return json.dumps(info, indent=2, ensure_ascii=False)


def list_files(path=".", **kwargs):
    """List files and directories at the given path."""
    resolved = validate_path(path)

    if not resolved.exists():
        raise ToolError(f"Path does not exist: {path}")
    if not resolved.is_dir():
        raise ToolError(f"Not a directory: {path}")

    entries = []
    count = 0

    try:
        for entry in sorted(resolved.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if count >= MAX_LIST_ITEMS:
                entries.append(f"... and more (limit: {MAX_LIST_ITEMS} items)")
                break

            try:
                stat = entry.stat()
                if entry.is_dir():
                    # Count immediate children
                    try:
                        child_count = sum(1 for _ in entry.iterdir())
                    except PermissionError:
                        child_count = "?"
                    entries.append(f"[DIR]  {entry.name}/  ({child_count} items)")
                else:
                    size = _format_size(stat.st_size)
                    modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
                    entries.append(f"[FILE] {entry.name}  ({size}, {modified})")
                count += 1
            except (PermissionError, OSError):
                entries.append(f"[????] {entry.name}  (access denied)")
                count += 1

    except PermissionError:
        raise ToolError(f"Permission denied: {path}")

    header = f"Directory: {resolved}\nItems: {count}\n"
    return _truncate(header + "\n".join(entries))


def search_in_files(path=".", query="", **kwargs):
    """Search for text in files within a directory. Like grep."""
    if not query:
        raise ToolError("Query is required")

    resolved = validate_path(path)

    if not resolved.exists():
        raise ToolError(f"Path does not exist: {path}")

    SEARCHABLE_EXT = {
        ".txt", ".md", ".log", ".csv", ".json", ".xml", ".html", ".htm",
        ".py", ".js", ".ts", ".css", ".bat", ".cmd", ".ps1", ".sh",
        ".cfg", ".conf", ".ini", ".yaml", ".yml", ".toml", ".env",
        ".c", ".cpp", ".h", ".java", ".cs", ".rb", ".go", ".rs",
    }

    results = []
    files_searched = 0
    query_lower = query.lower()

    def search_dir(dir_path, depth=0):
        nonlocal files_searched
        if depth > MAX_LIST_DEPTH:
            return
        if len(results) >= MAX_SEARCH_RESULTS:
            return

        try:
            for entry in sorted(dir_path.iterdir()):
                if len(results) >= MAX_SEARCH_RESULTS:
                    break

                if entry.is_dir():
                    if entry.name.startswith(".") or entry.name in ("node_modules", "__pycache__", ".git"):
                        continue
                    search_dir(entry, depth + 1)
                elif entry.is_file() and entry.suffix.lower() in SEARCHABLE_EXT:
                    try:
                        if entry.stat().st_size > MAX_FILE_READ_BYTES * 2:
                            continue
                        text = entry.read_text(encoding="utf-8", errors="replace")
                        files_searched += 1
                        for i, line in enumerate(text.splitlines(), 1):
                            if query_lower in line.lower():
                                rel = entry.relative_to(resolved) if entry != resolved else entry.name
                                preview = line.strip()[:200]
                                results.append(f"{rel}:{i}: {preview}")
                                if len(results) >= MAX_SEARCH_RESULTS:
                                    break
                    except (PermissionError, OSError):
                        pass
        except PermissionError:
            pass

    if resolved.is_file():
        # Search single file
        if resolved.suffix.lower() in SEARCHABLE_EXT:
            try:
                text = resolved.read_text(encoding="utf-8", errors="replace")
                files_searched = 1
                for i, line in enumerate(text.splitlines(), 1):
                    if query_lower in line.lower():
                        preview = line.strip()[:200]
                        results.append(f"{resolved.name}:{i}: {preview}")
                        if len(results) >= MAX_SEARCH_RESULTS:
                            break
            except (PermissionError, OSError) as e:
                raise ToolError(f"Cannot read file: {e}")
    else:
        search_dir(resolved)

    header = f"Search: \"{query}\" in {resolved}\nFiles searched: {files_searched}, Matches: {len(results)}\n\n"
    if not results:
        return header + "No matches found."
    return _truncate(header + "\n".join(results))


def read_text_file(path="", **kwargs):
    """Read the contents of a text file."""
    resolved = validate_path(path)

    if not resolved.exists():
        raise ToolError(f"File does not exist: {path}")
    if not resolved.is_file():
        raise ToolError(f"Not a file: {path}")

    # Size check
    try:
        size = resolved.stat().st_size
    except OSError as e:
        raise ToolError(f"Cannot stat file: {e}")

    if size > MAX_FILE_READ_BYTES:
        raise ToolError(f"File too large: {_format_size(size)} (limit: {_format_size(MAX_FILE_READ_BYTES)}). Use read_logs for tail reading.")

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        raise ToolError(f"Permission denied: {path}")
    except OSError as e:
        raise ToolError(f"Cannot read file: {e}")

    header = f"File: {resolved} ({_format_size(size)})\n{'─' * 40}\n"
    return _truncate(header + content)


def get_file_sizes(path=".", **kwargs):
    """Get sizes of files and subdirectories at the given path, sorted by size descending."""
    resolved = validate_path(path)

    if not resolved.exists():
        raise ToolError(f"Path does not exist: {path}")
    if not resolved.is_dir():
        raise ToolError(f"Not a directory: {path}")

    items = []

    try:
        for entry in resolved.iterdir():
            try:
                if entry.is_file():
                    items.append((entry.name, entry.stat().st_size, "file"))
                elif entry.is_dir():
                    total = _dir_size(entry, depth=0, max_depth=2)
                    items.append((entry.name + "/", total, "dir"))
            except (PermissionError, OSError):
                items.append((entry.name, -1, "error"))
    except PermissionError:
        raise ToolError(f"Permission denied: {path}")

    # Sort by size descending
    items.sort(key=lambda x: x[1], reverse=True)

    lines = []
    total_size = 0
    for name, size, kind in items[:MAX_LIST_ITEMS]:
        if size >= 0:
            total_size += size
            lines.append(f"  {_format_size(size):>10}  {name}")
        else:
            lines.append(f"  {'error':>10}  {name}")

    header = f"Directory: {resolved}\nTotal: {_format_size(total_size)}\n{'─' * 40}\n"
    return _truncate(header + "\n".join(lines))


def read_logs(path="", lines=None, **kwargs):
    """Read the last N lines of a file (tail). Good for log files."""
    resolved = validate_path(path)
    max_lines = min(int(lines) if lines else MAX_LOG_LINES, MAX_LOG_LINES)

    if not resolved.exists():
        raise ToolError(f"File does not exist: {path}")
    if not resolved.is_file():
        raise ToolError(f"Not a file: {path}")

    try:
        size = resolved.stat().st_size
    except OSError as e:
        raise ToolError(f"Cannot stat file: {e}")

    # Read up to 1MB from end for tail
    read_size = min(size, 1024 * 1024)

    try:
        with open(resolved, "rb") as f:
            if size > read_size:
                f.seek(size - read_size)
            raw = f.read(read_size)

        text = raw.decode("utf-8", errors="replace")
        all_lines = text.splitlines()
        tail = all_lines[-max_lines:]

        header = f"File: {resolved} ({_format_size(size)})\nShowing last {len(tail)} of {len(all_lines)} lines\n{'─' * 40}\n"
        return _truncate(header + "\n".join(tail))

    except PermissionError:
        raise ToolError(f"Permission denied: {path}")
    except OSError as e:
        raise ToolError(f"Cannot read file: {e}")


def get_network_info(**kwargs):
    """Get basic network information: hostname, IP addresses, interfaces."""
    info = {}

    info["hostname"] = socket.gethostname()

    # Get all IPs for hostname
    try:
        host_info = socket.gethostbyname_ex(socket.gethostname())
        info["aliases"] = host_info[1]
        info["ip_addresses"] = host_info[2]
    except socket.error:
        info["ip_addresses"] = []

    # Try to get default gateway IP by connecting to a non-routable address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))  # Doesn't actually send anything
        info["primary_ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["primary_ip"] = "unknown"

    # On Windows, get network adapter details via PowerShell
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object Name,InterfaceDescription,MacAddress,LinkSpeed | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            adapters = json.loads(result.stdout.strip())
            if isinstance(adapters, dict):
                adapters = [adapters]
            info["active_adapters"] = adapters
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'} | Select-Object IPAddress,InterfaceAlias,PrefixLength | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            ip_addrs = json.loads(result.stdout.strip())
            if isinstance(ip_addrs, dict):
                ip_addrs = [ip_addrs]
            info["ipv4_addresses"] = ip_addrs
        except Exception:
            pass

    return json.dumps(info, indent=2, ensure_ascii=False)


def list_processes(**kwargs):
    """List running processes with CPU/memory usage."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV"],
                capture_output=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode != 0:
                raise ToolError("tasklist command failed")

            # Decode with OEM codepage for correct Windows output
            try:
                output = result.stdout.decode("utf-8")
            except UnicodeDecodeError:
                output = result.stdout.decode("oem", errors="replace")

            lines = output.strip().splitlines()
            if not lines:
                return "No processes found."

            # Parse CSV — first line is header
            # Format: "Image Name","PID","Session Name","Session#","Mem Usage"
            entries = lines[1:]

            def parse_mem(line):
                try:
                    parts = line.split('",')
                    mem_part = parts[-1].replace('"', '').strip()
                    # Extract only digits from memory string (e.g. "65,752 K" -> 65752)
                    digits = re.sub(r'[^\d]', '', mem_part)
                    return int(digits) if digits else 0
                except (IndexError, ValueError):
                    return 0

            entries.sort(key=parse_mem, reverse=True)

            # Build clean output: Name, PID, Memory
            out_lines = [f"{'Process':<40} {'PID':>8} {'Memory':>12}"]
            out_lines.append("-" * 62)
            for line in entries[:50]:
                try:
                    parts = line.split('",')
                    name = parts[0].replace('"', '').strip()
                    pid = parts[1].replace('"', '').strip()
                    mem_part = parts[-1].replace('"', '').strip()
                    digits = re.sub(r'[^\d]', '', mem_part)
                    mem_kb = int(digits) if digits else 0
                    if mem_kb >= 1024:
                        mem_str = f"{mem_kb / 1024:.1f} MB"
                    else:
                        mem_str = f"{mem_kb} KB"
                    out_lines.append(f"{name:<40} {pid:>8} {mem_str:>12}")
                except (IndexError, ValueError):
                    pass

            result_text = f"Top processes by memory (showing 50 of {len(entries)}):\n\n"
            result_text += "\n".join(out_lines)

            return _truncate(result_text)

        except subprocess.TimeoutExpired:
            raise ToolError("Process listing timed out")
        except FileNotFoundError:
            raise ToolError("tasklist command not found")
    else:
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort=-rss"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().splitlines()
            output = lines[:51]  # header + top 50
            return _truncate(f"Top processes by memory:\n\n" + "\n".join(output))
        except Exception as e:
            raise ToolError(f"Cannot list processes: {e}")


# ============================================================
#  Tool: get_event_log
# ============================================================
def get_event_log(log_name="System", level="error", max_events=30):
    """Read recent Windows Event Log entries (errors, warnings, critical)."""
    log_name = str(log_name).strip()
    allowed_logs = {"System", "Application", "Security"}
    if log_name not in allowed_logs:
        raise ToolError(f"Log must be one of: {', '.join(allowed_logs)}")

    level_map = {
        "critical": 1,
        "error": 2,
        "warning": 3,
        "info": 4,
    }
    level = str(level).lower().strip()
    if level not in level_map:
        raise ToolError(f"Level must be one of: {', '.join(level_map.keys())}")

    max_events = min(int(max_events), 50)
    lvl_num = level_map[level]

    if sys.platform != "win32":
        raise ToolError("Event Log is only available on Windows")

    try:
        ps_cmd = (
            f"Get-WinEvent -LogName '{log_name}' -MaxEvents 200 "
            f"| Where-Object {{ $_.Level -le {lvl_num} -and $_.Level -ge 1 }} "
            f"| Select-Object -First {max_events} TimeCreated, Level, Id, ProviderName, Message "
            f"| ForEach-Object {{ "
            f"  $lvl = switch($_.Level) {{ 1 {{'CRITICAL'}} 2 {{'ERROR'}} 3 {{'WARNING'}} 4 {{'INFO'}} default {{'UNKNOWN'}} }}; "
            f"  \"[$lvl] $($_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')) | $($_.ProviderName) (ID:$($_.Id))`n$($_.Message)`n---\" "
            f"}}"
        )
        output = _run_ps(ps_cmd, timeout=30).strip()
        if not output:
            return f"No {level}+ events found in {log_name} log."
        return _truncate(f"Event Log: {log_name} (level >= {level}, last {max_events}):\n\n{output}")
    except subprocess.TimeoutExpired:
        raise ToolError("Event log query timed out")
    except Exception as e:
        raise ToolError(f"Cannot read event log: {e}")


# ============================================================
#  Tool: list_startup_programs
# ============================================================
def list_startup_programs():
    """List programs that run at Windows startup."""
    if sys.platform != "win32":
        raise ToolError("Startup programs listing is only available on Windows")

    sections = []

    # Registry Run keys
    reg_paths = [
        r"HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        r"HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        r"HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    ]

    for reg_path in reg_paths:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-ItemProperty -Path '{reg_path}' -ErrorAction SilentlyContinue "
                 f"| Select-Object * -ExcludeProperty PS* "
                 f"| ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            data = result.stdout.strip()
            if data and data != "null" and data != "{}":
                label = reg_path.replace("HKLM:", "HKLM").replace("HKCU:", "HKCU")
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    items = [f"  {k} = {v}" for k, v in parsed.items() if not k.startswith("(")]
                    if items:
                        sections.append(f"[{label}]\n" + "\n".join(items))
        except Exception:
            pass

    # Startup folder
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-ChildItem \"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\" -ErrorAction SilentlyContinue "
             "| Select-Object Name, Length | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = result.stdout.strip()
        if data and data != "null" and data != "[]":
            items = json.loads(data)
            if isinstance(items, dict):
                items = [items]
            if items:
                names = [f"  {i.get('Name', '?')}" for i in items]
                sections.append("[Startup Folder]\n" + "\n".join(names))
    except Exception:
        pass

    # Scheduled tasks at logon
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-ScheduledTask | Where-Object {$_.Triggers -and ($_.Triggers | Where-Object {$_ -is [CimInstance] -and $_.CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger'})} "
             "| Where-Object {$_.State -ne 'Disabled'} "
             "| Select-Object TaskName, TaskPath, State -First 30 "
             "| ForEach-Object { \"  $($_.State) | $($_.TaskPath)$($_.TaskName)\" }"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.strip()
        if output:
            sections.append(f"[Scheduled Tasks — Logon Trigger]\n{output}")
    except Exception:
        pass

    if not sections:
        return "No startup programs found."

    return _truncate("Startup Programs:\n\n" + "\n\n".join(sections))


# ============================================================
#  Tool: get_disk_health
# ============================================================
def get_disk_health():
    """Get SMART / health data for physical disks."""
    if sys.platform != "win32":
        raise ToolError("Disk health is only available on Windows")

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, BusType, Size, HealthStatus, OperationalStatus "
             "| ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        disks_raw = result.stdout.strip()
        if not disks_raw or disks_raw == "null":
            return "No physical disks found."

        disks = json.loads(disks_raw)
        if isinstance(disks, dict):
            disks = [disks]

        lines = []
        for d in disks:
            size_gb = round(d.get("Size", 0) / (1024 ** 3), 1) if d.get("Size") else "?"
            lines.append(
                f"Disk {d.get('DeviceId', '?')}: {d.get('FriendlyName', 'Unknown')}\n"
                f"  Type: {d.get('MediaType', '?')} | Bus: {d.get('BusType', '?')}\n"
                f"  Size: {size_gb} GB\n"
                f"  Health: {d.get('HealthStatus', '?')} | Status: {d.get('OperationalStatus', '?')}"
            )

        # Try to get reliability counters (temperature, wear, errors)
        try:
            rel_result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-PhysicalDisk | Get-StorageReliabilityCounter "
                 "| Select-Object DeviceId, Temperature, Wear, ReadErrorsTotal, WriteErrorsTotal, PowerOnHours "
                 "| ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            rel_raw = rel_result.stdout.strip()
            if rel_raw and rel_raw != "null":
                counters = json.loads(rel_raw)
                if isinstance(counters, dict):
                    counters = [counters]
                for c in counters:
                    dev_id = c.get("DeviceId", "?")
                    parts = []
                    if c.get("Temperature") is not None:
                        parts.append(f"Temp: {c['Temperature']}°C")
                    if c.get("Wear") is not None:
                        parts.append(f"Wear: {c['Wear']}%")
                    if c.get("PowerOnHours") is not None:
                        hours = c["PowerOnHours"]
                        parts.append(f"Power-on: {hours}h ({round(hours/24)}d)")
                    if c.get("ReadErrorsTotal"):
                        parts.append(f"Read errors: {c['ReadErrorsTotal']}")
                    if c.get("WriteErrorsTotal"):
                        parts.append(f"Write errors: {c['WriteErrorsTotal']}")
                    if parts:
                        lines.append(f"  Disk {dev_id} SMART: {' | '.join(parts)}")
        except Exception:
            pass

        return _truncate("Disk Health:\n\n" + "\n\n".join(lines))

    except Exception as e:
        raise ToolError(f"Cannot get disk health: {e}")


# ============================================================
#  Tool: get_security_status
# ============================================================
def get_security_status():
    """Get Windows security status: Defender, Firewall, UAC."""
    if sys.platform != "win32":
        raise ToolError("Security status is only available on Windows")

    sections = []

    # Windows Defender
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, "
             "AntispywareEnabled, AntivirusSignatureLastUpdated, QuickScanEndTime, FullScanEndTime "
             "| ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = result.stdout.strip()
        if data and data != "null":
            d = json.loads(data)
            lines = []
            for key, label in [
                ("AntivirusEnabled", "Antivirus"),
                ("RealTimeProtectionEnabled", "Real-time Protection"),
                ("AntispywareEnabled", "Antispyware"),
            ]:
                val = d.get(key)
                status = "ON" if val else "OFF" if val is not None else "?"
                lines.append(f"  {label}: {status}")

            sig = d.get("AntivirusSignatureLastUpdated", "")
            if sig:
                # PowerShell JSON date format: /Date(...)/ or ISO
                if isinstance(sig, str) and "Date(" in sig:
                    try:
                        ts = int(re.search(r'Date\((\d+)', sig).group(1)) // 1000
                        sig = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass
                lines.append(f"  Signatures updated: {sig}")

            sections.append("[Windows Defender]\n" + "\n".join(lines))
    except Exception:
        sections.append("[Windows Defender]\n  Unable to query (may require admin)")

    # Firewall
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = result.stdout.strip()
        if data and data != "null":
            profiles = json.loads(data)
            if isinstance(profiles, dict):
                profiles = [profiles]
            lines = [f"  {p.get('Name', '?')}: {'ON' if p.get('Enabled') else 'OFF'}" for p in profiles]
            sections.append("[Firewall]\n" + "\n".join(lines))
    except Exception:
        pass

    # UAC level
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
             "-Name EnableLUA, ConsentPromptBehaviorAdmin -ErrorAction SilentlyContinue) "
             "| Select-Object EnableLUA, ConsentPromptBehaviorAdmin | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = result.stdout.strip()
        if data and data != "null":
            d = json.loads(data)
            lua = "Enabled" if d.get("EnableLUA") else "Disabled"
            sections.append(f"[UAC]\n  UAC: {lua}")
    except Exception:
        pass

    if not sections:
        return "Cannot retrieve security status."

    return _truncate("Security Status:\n\n" + "\n\n".join(sections))


# ============================================================
#  Tool: list_installed_software
# ============================================================
def list_installed_software(search=""):
    """List installed programs from Windows registry."""
    if sys.platform != "win32":
        raise ToolError("Installed software listing is only available on Windows")

    search = str(search).strip()

    # Query both 64-bit and 32-bit registry
    ps_cmd = (
        "$paths = @("
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
        "'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
        "'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'"
        "); "
        "Get-ItemProperty $paths -ErrorAction SilentlyContinue "
        "| Where-Object { $_.DisplayName -and $_.DisplayName -ne '' } "
    )
    if search:
        ps_cmd += f"| Where-Object {{ $_.DisplayName -like '*{search}*' }} "
    ps_cmd += (
        "| Sort-Object DisplayName -Unique "
        "| Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, EstimatedSize "
        "| ConvertTo-Json -Compress"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = result.stdout.strip()
        if not data or data == "null" or data == "[]":
            return "No installed software found." + (f" (filter: '{search}')" if search else "")

        apps = json.loads(data)
        if isinstance(apps, dict):
            apps = [apps]

        lines = []
        for a in apps[:200]:
            name = a.get("DisplayName", "?")
            ver = a.get("DisplayVersion", "")
            pub = a.get("Publisher", "")
            date = a.get("InstallDate", "")
            size_kb = a.get("EstimatedSize", 0) or 0
            size_str = _format_size(size_kb * 1024) if size_kb else ""

            parts = [name]
            if ver:
                parts[0] += f" v{ver}"
            meta = []
            if pub:
                meta.append(pub)
            if size_str:
                meta.append(size_str)
            if date:
                meta.append(f"installed: {date}")
            if meta:
                parts.append(f"  ({', '.join(meta)})")

            lines.append("".join(parts))

        header = f"Installed Software ({len(apps)} programs)"
        if search:
            header += f" [filter: '{search}']"
        return _truncate(header + ":\n\n" + "\n".join(lines))

    except Exception as e:
        raise ToolError(f"Cannot list software: {e}")


# ============================================================
#  Tool: get_gpu_info
# ============================================================
def get_gpu_info():
    """Get GPU / video adapter information."""
    if sys.platform != "win32":
        raise ToolError("GPU info is only available on Windows")

    sections = []

    # WMI video controller
    try:
        data = _run_ps(
            "Get-CimInstance Win32_VideoController "
            "| Select-Object Name, DriverVersion, AdapterRAM, VideoModeDescription, CurrentRefreshRate, Status "
            "| ConvertTo-Json -Compress",
            timeout=15
        ).strip()
        if data and data != "null":
            gpus = json.loads(data)
            if isinstance(gpus, dict):
                gpus = [gpus]
            for i, g in enumerate(gpus):
                ram = g.get("AdapterRAM", 0) or 0
                ram_str = _format_size(ram) if ram > 0 else "shared/unknown"
                lines = [
                    f"GPU {i}: {g.get('Name', 'Unknown')}",
                    f"  Driver: {g.get('DriverVersion', '?')}",
                    f"  VRAM: {ram_str}",
                    f"  Resolution: {g.get('VideoModeDescription', '?')}",
                    f"  Refresh: {g.get('CurrentRefreshRate', '?')} Hz",
                    f"  Status: {g.get('Status', '?')}",
                ]
                sections.append("\n".join(lines))
    except Exception:
        pass

    # nvidia-smi (optional, if NVIDIA GPU present)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 8:
                    sections.append(
                        f"NVIDIA SMI: {parts[0]}\n"
                        f"  Temp: {parts[1]}°C | GPU Load: {parts[2]}% | Mem Load: {parts[3]}%\n"
                        f"  VRAM: {parts[5]} / {parts[4]} MB (free: {parts[6]} MB)\n"
                        f"  Driver: {parts[7]}"
                    )
    except FileNotFoundError:
        pass
    except Exception:
        pass

    if not sections:
        return "No GPU information available."

    return _truncate("GPU Information:\n\n" + "\n\n".join(sections))


# ============================================================
#  Tool: list_open_ports
# ============================================================
def list_open_ports():
    """List open TCP/UDP ports with associated processes."""
    if sys.platform != "win32":
        # Linux fallback
        try:
            result = subprocess.run(
                ["ss", "-tulnp"],
                capture_output=True, text=True, timeout=10
            )
            return _truncate("Open ports:\n\n" + result.stdout)
        except Exception as e:
            raise ToolError(f"Cannot list ports: {e}")

    try:
        ps_cmd = (
            "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue "
            "| Select-Object LocalAddress, LocalPort, OwningProcess "
            "| Sort-Object LocalPort "
            "| ForEach-Object { "
            "  $proc = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName; "
            "  \"TCP  $($_.LocalAddress):$($_.LocalPort)  PID:$($_.OwningProcess)  $proc\" "
            "} | Select-Object -First 80"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.strip()

        # Also get UDP listeners
        try:
            udp_cmd = (
                "Get-NetUDPEndpoint -ErrorAction SilentlyContinue "
                "| Select-Object LocalAddress, LocalPort, OwningProcess "
                "| Sort-Object LocalPort "
                "| ForEach-Object { "
                "  $proc = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName; "
                "  \"UDP  $($_.LocalAddress):$($_.LocalPort)  PID:$($_.OwningProcess)  $proc\" "
                "} | Select-Object -First 40"
            )
            udp_result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", udp_cmd],
                capture_output=True, text=True, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            udp_out = udp_result.stdout.strip()
            if udp_out:
                output += "\n\n" + udp_out
        except Exception:
            pass

        if not output:
            return "No open ports found."

        return _truncate("Open Ports (listening):\n\n" + output)

    except Exception as e:
        raise ToolError(f"Cannot list open ports: {e}")


# ============================================================
#  Tool: list_usb_devices
# ============================================================
def list_usb_devices():
    """List connected USB devices."""
    if sys.platform != "win32":
        # Linux fallback
        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True, text=True, timeout=10
            )
            return _truncate("USB Devices:\n\n" + result.stdout)
        except Exception as e:
            raise ToolError(f"Cannot list USB devices: {e}")

    try:
        data = _run_ps(
            "Get-PnpDevice -Class USB -ErrorAction SilentlyContinue "
            "| Where-Object { $_.Status -eq 'OK' } "
            "| Select-Object FriendlyName, InstanceId, Status "
            "| ConvertTo-Json -Compress",
            timeout=15
        ).strip()
        if not data or data == "null" or data == "[]":
            return "No USB devices found."

        devices = json.loads(data)
        if isinstance(devices, dict):
            devices = [devices]

        lines = []
        for d in devices:
            name = d.get("FriendlyName", "Unknown Device")
            inst = d.get("InstanceId", "")
            # Extract VID/PID from InstanceId if present
            vid_pid = ""
            m = re.search(r'VID_([0-9A-Fa-f]+)&PID_([0-9A-Fa-f]+)', inst)
            if m:
                vid_pid = f" [VID:{m.group(1)} PID:{m.group(2)}]"
            lines.append(f"  {name}{vid_pid}")

        return _truncate(f"USB Devices ({len(devices)} connected):\n\n" + "\n".join(lines))

    except Exception as e:
        raise ToolError(f"Cannot list USB devices: {e}")


# ============================================================
#  Tool: get_battery_info
# ============================================================
def get_battery_info():
    """Get battery status and health (laptops only)."""
    if sys.platform != "win32":
        # Linux fallback
        try:
            bat_path = Path("/sys/class/power_supply/BAT0")
            if not bat_path.exists():
                return "No battery found (desktop PC)."
            info = {}
            for f in ["status", "capacity", "cycle_count", "energy_full", "energy_full_design"]:
                p = bat_path / f
                if p.exists():
                    info[f] = p.read_text().strip()
            return f"Battery: {json.dumps(info, indent=2)}"
        except Exception as e:
            raise ToolError(f"Cannot read battery info: {e}")

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Battery "
             "| Select-Object Name, Status, BatteryStatus, EstimatedChargeRemaining, "
             "DesignCapacity, FullChargeCapacity, EstimatedRunTime "
             "| ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        data = result.stdout.strip()
        if not data or data == "null" or data == "[]":
            return "No battery found (desktop PC or battery not detected)."

        bat = json.loads(data)
        if isinstance(bat, list):
            bat = bat[0] if bat else {}

        status_map = {
            1: "Discharging", 2: "AC Power", 3: "Fully Charged",
            4: "Low", 5: "Critical", 6: "Charging", 7: "Charging+High",
            8: "Charging+Low", 9: "Charging+Critical", 10: "Undefined", 11: "Partially Charged"
        }
        bat_status = status_map.get(bat.get("BatteryStatus", 0), "Unknown")
        charge = bat.get("EstimatedChargeRemaining", "?")
        design = bat.get("DesignCapacity", 0)
        full = bat.get("FullChargeCapacity", 0)
        runtime = bat.get("EstimatedRunTime")

        lines = [
            f"Battery: {bat.get('Name', 'Unknown')}",
            f"  Status: {bat_status}",
            f"  Charge: {charge}%",
        ]

        if design and full and design > 0:
            health = round(full / design * 100, 1)
            lines.append(f"  Health: {health}% (capacity {full} / {design} mWh)")

        if runtime and runtime != 71582788:  # Magic value for "plugged in"
            hours = runtime // 60
            mins = runtime % 60
            lines.append(f"  Est. runtime: {hours}h {mins}m")
        elif runtime == 71582788:
            lines.append(f"  Est. runtime: on AC power")

        return "\n".join(lines)

    except Exception as e:
        raise ToolError(f"Cannot get battery info: {e}")


# ============================================================
#  Tool: read_clipboard
# ============================================================
def read_clipboard():
    """Read current text content from the system clipboard."""
    if sys.platform == "win32":
        try:
            text = _run_ps("Get-Clipboard", timeout=5).strip()
            if not text:
                return "Clipboard is empty (no text content)."
            return _truncate(f"Clipboard content ({len(text)} chars):\n\n{text}")
        except Exception as e:
            raise ToolError(f"Cannot read clipboard: {e}")
    else:
        # Linux — try xclip
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5
            )
            text = result.stdout.strip()
            if not text:
                return "Clipboard is empty."
            return _truncate(f"Clipboard content ({len(text)} chars):\n\n{text}")
        except Exception as e:
            raise ToolError(f"Cannot read clipboard: {e}")


# ============================================================
#  Helpers
# ============================================================
def _run_ps(command, timeout=15):
    """Run a PowerShell command with UTF-8 output encoding. Returns stdout string."""
    # Prefix forces PowerShell to output UTF-8 instead of OEM codepage
    full_cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + command
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", full_cmd],
        capture_output=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    # Try UTF-8 first, fall back to oem
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("oem", errors="replace")


def _format_size(size_bytes):
    """Format bytes to human-readable."""
    if size_bytes < 0:
        return "error"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 ** 3):.1f} GB"


def _dir_size(path, depth=0, max_depth=2):
    """Calculate total size of a directory (with depth limit)."""
    total = 0
    if depth > max_depth:
        return 0
    try:
        for entry in path.iterdir():
            try:
                if entry.is_file() and not entry.is_symlink():
                    total += entry.stat().st_size
                elif entry.is_dir() and not entry.is_symlink():
                    total += _dir_size(entry, depth + 1, max_depth)
            except (PermissionError, OSError):
                pass
    except PermissionError:
        pass
    return total


# ============================================================
#  Tool Registry & Executor
# ============================================================
TOOL_REGISTRY = {
    "get_system_info": {
        "fn": get_system_info,
        "description": "Get system information: OS, CPU, RAM, disk usage, uptime",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "list_files": {
        "fn": list_files,
        "description": "List files and directories at the given path with sizes and dates",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list. Use ~ for home directory."},
            },
            "required": ["path"],
        },
    },
    "search_in_files": {
        "fn": search_in_files,
        "description": "Search for text in files within a directory (like grep). Searches text files recursively.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory or file path to search in"},
                "query": {"type": "string", "description": "Text to search for (case-insensitive)"},
            },
            "required": ["path", "query"],
        },
    },
    "read_text_file": {
        "fn": read_text_file,
        "description": "Read the full contents of a text file (max 100KB)",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the text file"},
            },
            "required": ["path"],
        },
    },
    "get_file_sizes": {
        "fn": get_file_sizes,
        "description": "Get sizes of all files and subdirectories at a path, sorted by size. Useful for finding what takes up disk space.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to analyze"},
            },
            "required": ["path"],
        },
    },
    "read_logs": {
        "fn": read_logs,
        "description": "Read the last N lines of a file (tail). Good for large log files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the log file"},
                "lines": {"type": "integer", "description": "Number of lines from end (default: 200, max: 200)"},
            },
            "required": ["path"],
        },
    },
    "get_network_info": {
        "fn": get_network_info,
        "description": "Get network information: hostname, IP addresses, network interfaces",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "list_processes": {
        "fn": list_processes,
        "description": "List running processes sorted by memory usage (top 50)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "get_event_log": {
        "fn": get_event_log,
        "description": "Read recent Windows Event Log entries (errors, warnings, critical events). Great for diagnosing crashes, BSODs, driver issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "log_name": {"type": "string", "description": "Log name: System, Application, or Security (default: System)"},
                "level": {"type": "string", "description": "Minimum level: critical, error, warning, info (default: error)"},
                "max_events": {"type": "integer", "description": "Max events to return (default: 30, max: 50)"},
            },
        },
    },
    "list_startup_programs": {
        "fn": list_startup_programs,
        "description": "List programs that run at Windows startup (registry Run keys, Startup folder, scheduled tasks). Key for diagnosing slow boot.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "get_disk_health": {
        "fn": get_disk_health,
        "description": "Get SMART health data for physical disks: temperature, wear level, power-on hours, error counts. Predicts disk failure.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "get_security_status": {
        "fn": get_security_status,
        "description": "Get Windows security status: Defender (antivirus on/off, signatures age), Firewall profiles, UAC level.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "list_installed_software": {
        "fn": list_installed_software,
        "description": "List installed programs with version, publisher, size, install date. Optional search filter.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Optional filter by name (e.g. 'chrome', 'nvidia')"},
            },
        },
    },
    "get_gpu_info": {
        "fn": get_gpu_info,
        "description": "Get GPU information: model, driver, VRAM, resolution. NVIDIA GPUs also show temperature and load via nvidia-smi.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "list_open_ports": {
        "fn": list_open_ports,
        "description": "List open TCP/UDP ports with process names. Useful for finding what's listening on the network.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "list_usb_devices": {
        "fn": list_usb_devices,
        "description": "List connected USB devices with VID/PID identifiers.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "get_battery_info": {
        "fn": get_battery_info,
        "description": "Get battery status, charge level, health percentage, and estimated runtime (laptops only).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "read_clipboard": {
        "fn": read_clipboard,
        "description": "Read current text from the system clipboard. User can copy an error message and ask the AI to analyze it.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def get_tools_openai_format():
    """Return tools definitions in OpenAI function calling format."""
    tools = []
    for name, spec in TOOL_REGISTRY.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        })
    return tools


def execute_tool(name, arguments=None):
    """
    Execute a tool by name with given arguments.
    Returns (success: bool, result: str).
    """
    if name not in TOOL_REGISTRY:
        return False, f"Unknown tool: {name}. Available: {', '.join(TOOL_REGISTRY.keys())}"

    fn = TOOL_REGISTRY[name]["fn"]
    args = arguments or {}

    # Ensure args is a dict
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return False, f"Invalid arguments JSON: {args}"

    try:
        result = fn(**args)
        return True, result
    except ToolError as e:
        return False, f"Tool error: {e}"
    except Exception as e:
        return False, f"Unexpected error in {name}: {type(e).__name__}: {e}"


# ============================================================
#  Init on import
# ============================================================
init_allowed_roots()
