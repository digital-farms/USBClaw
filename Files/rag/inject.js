/**
 * RAG Controls — injected into llama.cpp WebUI
 * Adds a floating panel with: RAG toggle, Reindex button, file manager, status
 */
(function () {
    'use strict';

    const RAG_BASE = window.location.origin;
    let ragEnabled = false;
    let reasoningEnabled = false;
    let toolsEnabled = false;
    let toolsAvailable = false;
    let ragStatus = {};
    let pollTimer = null;
    let fileList = [];

    // ========== Create Panel ==========
    function createPanel() {
        const panel = document.createElement('div');
        panel.id = 'rag-panel';
        panel.innerHTML = `
            <style>
                #rag-panel {
                    position: fixed;
                    bottom: 16px;
                    right: 16px;
                    z-index: 99999;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 13px;
                }
                .rag-fab {
                    width: 44px;
                    height: 44px;
                    border-radius: 50%;
                    border: none;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.4);
                    transition: all 0.2s;
                    background: #1e1e2e;
                    color: #888;
                }
                .rag-fab:hover {
                    transform: scale(1.05);
                    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
                }
                .rag-fab.active {
                    background: #1a2e1a;
                    color: #4ade80;
                }
                #reasoning-toggle-btn.active {
                    background: #1a1a3e;
                    color: #818cf8;
                }
                #tools-toggle-btn.active {
                    background: #2e1a1a;
                    color: #f97316;
                }
                .rag-fab-row {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                }
                #rag-popup {
                    display: none;
                    position: absolute;
                    bottom: 52px;
                    right: 0;
                    width: 320px;
                    max-height: 480px;
                    background: #111118;
                    border: 1px solid #2a2a3a;
                    border-radius: 12px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                    overflow: hidden auto;
                }
                #rag-popup.visible { display: block; }
                .rag-header {
                    padding: 12px 14px;
                    border-bottom: 1px solid #2a2a3a;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }
                .rag-header h3 {
                    margin: 0;
                    font-size: 14px;
                    font-weight: 600;
                    color: #e0e0e0;
                }
                .rag-body { padding: 12px 14px; }
                .rag-row {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }
                .rag-row:last-child { margin-bottom: 0; }
                .rag-label {
                    color: #aaa;
                    font-size: 13px;
                }
                .rag-switch {
                    position: relative;
                    width: 40px;
                    height: 22px;
                    cursor: pointer;
                }
                .rag-switch input { display: none; }
                .rag-switch-track {
                    position: absolute;
                    inset: 0;
                    background: #2a2a3a;
                    border-radius: 11px;
                    transition: background 0.2s;
                }
                .rag-switch input:checked + .rag-switch-track {
                    background: #1a3a1e;
                }
                .rag-switch-thumb {
                    position: absolute;
                    top: 3px;
                    left: 3px;
                    width: 16px;
                    height: 16px;
                    background: #666;
                    border-radius: 50%;
                    transition: all 0.2s;
                }
                .rag-switch input:checked ~ .rag-switch-thumb {
                    left: 21px;
                    background: #4ade80;
                }
                .rag-btn {
                    width: 100%;
                    padding: 8px 12px;
                    border: 1px solid #2a2a3a;
                    border-radius: 8px;
                    background: #1a1a24;
                    color: #ccc;
                    font-size: 12px;
                    cursor: pointer;
                    transition: all 0.15s;
                    text-align: center;
                }
                .rag-btn:hover {
                    background: #222233;
                    border-color: #3b3b5c;
                    color: #fff;
                }
                .rag-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                .rag-status {
                    font-size: 11px;
                    color: #666;
                    margin-top: 8px;
                    line-height: 1.5;
                }
                .rag-dot {
                    display: inline-block;
                    width: 6px;
                    height: 6px;
                    border-radius: 50%;
                    margin-right: 4px;
                    vertical-align: middle;
                }
                .rag-dot-on { background: #4ade80; }
                .rag-dot-off { background: #ef4444; }
                .rag-dot-loading { background: #eab308; animation: rag-pulse 1s infinite; }
                @keyframes rag-pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.3; }
                }
                .rag-divider {
                    height: 1px;
                    background: #2a2a3a;
                    margin: 10px 0;
                }
                .rag-section-title {
                    font-size: 11px;
                    color: #666;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 8px;
                }
                .rag-file-list {
                    max-height: 180px;
                    overflow-y: auto;
                    margin-bottom: 8px;
                }
                .rag-file-list::-webkit-scrollbar { width: 4px; }
                .rag-file-list::-webkit-scrollbar-track { background: transparent; }
                .rag-file-list::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
                .rag-file-item {
                    display: flex;
                    align-items: center;
                    padding: 5px 0;
                    border-bottom: 1px solid #1a1a24;
                    gap: 6px;
                }
                .rag-file-item:last-child { border-bottom: none; }
                .rag-file-icon {
                    color: #555;
                    flex-shrink: 0;
                }
                .rag-file-info {
                    flex: 1;
                    min-width: 0;
                    overflow: hidden;
                }
                .rag-file-name {
                    font-size: 12px;
                    color: #ccc;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .rag-file-meta {
                    font-size: 10px;
                    color: #555;
                }
                .rag-file-del {
                    background: none;
                    border: none;
                    color: #555;
                    cursor: pointer;
                    padding: 2px 4px;
                    border-radius: 4px;
                    font-size: 14px;
                    line-height: 1;
                    flex-shrink: 0;
                    transition: all 0.15s;
                }
                .rag-file-del:hover {
                    color: #ef4444;
                    background: rgba(239,68,68,0.1);
                }
                .rag-dropzone {
                    border: 1px dashed #333;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                    color: #555;
                    font-size: 11px;
                    cursor: pointer;
                    transition: all 0.2s;
                    position: relative;
                }
                .rag-dropzone:hover {
                    border-color: #555;
                    color: #888;
                }
                .rag-dropzone.drag-over {
                    border-color: #4ade80;
                    background: rgba(74,222,128,0.05);
                    color: #4ade80;
                }
                .rag-dropzone input[type="file"] {
                    position: absolute;
                    inset: 0;
                    opacity: 0;
                    cursor: pointer;
                }
                .rag-empty {
                    font-size: 11px;
                    color: #444;
                    text-align: center;
                    padding: 8px 0;
                    font-style: italic;
                }
                .rag-upload-progress {
                    font-size: 11px;
                    color: #eab308;
                    text-align: center;
                    padding: 4px 0;
                }
                .tool-log-block {
                    background: #0d0d14;
                    border: 1px solid #1e1e2e;
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin-bottom: 8px;
                    font-size: 12px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    color: #888;
                    line-height: 1.6;
                }
                .tool-log-block .tool-log-title {
                    font-size: 11px;
                    color: #555;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 4px;
                }
                .tool-log-block .tool-log-item {
                    color: #aaa;
                }
                .tool-log-block .tool-ok { color: #4ade80; }
                .tool-log-block .tool-fail { color: #ef4444; }

                #tools-popup {
                    display: none;
                    position: absolute;
                    bottom: 52px;
                    right: 0;
                    width: 320px;
                    max-height: 520px;
                    background: #111118;
                    border: 1px solid #2a2a3a;
                    border-radius: 12px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                    overflow: hidden auto;
                }
                #tools-popup.visible { display: block; }

                .tools-switch input:checked + .rag-switch-track {
                    background: #3a1e0e;
                }
                .tools-switch input:checked ~ .rag-switch-thumb {
                    left: 21px;
                    background: #f97316;
                }

                .tools-list {
                    max-height: 320px;
                    overflow-y: auto;
                }
                .tools-list::-webkit-scrollbar { width: 4px; }
                .tools-list::-webkit-scrollbar-track { background: transparent; }
                .tools-list::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
                .tool-item {
                    padding: 8px 0;
                    border-bottom: 1px solid #1a1a24;
                }
                .tool-item:last-child { border-bottom: none; }
                .tool-item-name {
                    font-size: 12px;
                    font-weight: 600;
                    color: #e0e0e0;
                    font-family: 'Consolas', 'Monaco', monospace;
                }
                .tool-item-desc {
                    font-size: 11px;
                    color: #666;
                    margin-top: 2px;
                    line-height: 1.4;
                }
                .tool-item-params {
                    font-size: 10px;
                    color: #555;
                    margin-top: 2px;
                    font-family: 'Consolas', 'Monaco', monospace;
                }
                .tool-cat-header {
                    font-size: 10px;
                    color: #f97316;
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                    font-weight: 600;
                    padding: 8px 0 2px 0;
                    border-bottom: 1px solid #1e1e2e;
                    margin-bottom: 2px;
                }
                .tool-cat-header:first-child {
                    padding-top: 0;
                }
            </style>

            <div id="tools-popup">
                <div class="rag-header">
                    <h3>System Tools</h3>
                </div>
                <div class="rag-body">
                    <div class="rag-row">
                        <span class="rag-label">Enable tools</span>
                        <label class="rag-switch tools-switch">
                            <input type="checkbox" id="tools-enabled-cb">
                            <span class="rag-switch-track"></span>
                            <span class="rag-switch-thumb"></span>
                        </label>
                    </div>
                    <div class="rag-status" id="tools-status-text" style="margin-bottom:6px">
                        18 read-only inspection tools — the AI can look but never modify.
                    </div>

                    <div class="rag-divider"></div>
                    <div class="rag-section-title">Available tools</div>
                    <div id="tools-list" class="tools-list"></div>
                </div>
            </div>

            <div id="rag-popup">
                <div class="rag-header">
                    <h3>Local Documents</h3>
                </div>
                <div class="rag-body">
                    <div class="rag-row">
                        <span class="rag-label">Use local docs</span>
                        <label class="rag-switch">
                            <input type="checkbox" id="rag-enabled-cb">
                            <span class="rag-switch-track"></span>
                            <span class="rag-switch-thumb"></span>
                        </label>
                    </div>
                    <div class="rag-row">
                        <button class="rag-btn" id="rag-reindex-btn">Reindex Documents</button>
                    </div>
                    <div class="rag-status" id="rag-status-text">Checking...</div>

                    <div class="rag-divider"></div>
                    <div class="rag-section-title">Files</div>
                    <div class="rag-file-list" id="rag-file-list">
                        <div class="rag-empty">Loading...</div>
                    </div>
                    <div class="rag-dropzone" id="rag-dropzone">
                        <input type="file" id="rag-file-input" multiple accept=".txt,.md,.csv,.log,.json,.xml,.html,.htm">
                        Drop files here or click to upload
                    </div>
                    <div class="rag-upload-progress" id="rag-upload-msg" style="display:none"></div>
                </div>
            </div>

            <div class="rag-fab-row">
                <button id="reasoning-toggle-btn" class="rag-fab" title="Thinking/Reasoning">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.5 4.5-3 5.5V16a1 1 0 0 1-1 1h-6a1 1 0 0 1-1-1v-1.5C6.5 13.5 5 11.5 5 9a7 7 0 0 1 7-7z"/>
                        <line x1="9" y1="20" x2="15" y2="20"/>
                        <line x1="10" y1="23" x2="14" y2="23"/>
                    </svg>
                </button>
                <button id="tools-toggle-btn" class="rag-fab" title="System Tools">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                    </svg>
                </button>
                <button id="rag-toggle-btn" class="rag-fab" title="Local Documents (RAG)">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                        <polyline points="10 9 9 9 8 9"/>
                    </svg>
                </button>
            </div>
        `;
        document.body.appendChild(panel);
        return panel;
    }

    // ========== Helpers ==========
    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // ========== Event Handlers ==========
    function init() {
        const panel = createPanel();
        const toggleBtn = document.getElementById('rag-toggle-btn');
        const reasoningBtn = document.getElementById('reasoning-toggle-btn');
        const toolsBtn = document.getElementById('tools-toggle-btn');
        const popup = document.getElementById('rag-popup');
        const toolsPopup = document.getElementById('tools-popup');
        const enabledCb = document.getElementById('rag-enabled-cb');
        const toolsEnabledCb = document.getElementById('tools-enabled-cb');
        const reindexBtn = document.getElementById('rag-reindex-btn');
        const fileInput = document.getElementById('rag-file-input');
        const dropzone = document.getElementById('rag-dropzone');

        // Toggle RAG popup
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toolsPopup.classList.remove('visible');
            popup.classList.toggle('visible');
            if (popup.classList.contains('visible')) loadFiles();
        });

        // Toggle reasoning (single click, no popup)
        reasoningBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                const resp = await fetch(RAG_BASE + '/rag/reasoning', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: !reasoningEnabled })
                });
                const data = await resp.json();
                reasoningEnabled = data.reasoning_enabled;
                updateUI();
            } catch (e) {
                console.error('[RAG] Reasoning toggle error:', e);
            }
        });

        // Toggle tools popup
        toolsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            popup.classList.remove('visible');
            toolsPopup.classList.toggle('visible');
            if (toolsPopup.classList.contains('visible')) renderToolsList();
        });

        // Tools enable/disable checkbox
        toolsEnabledCb.addEventListener('change', async () => {
            try {
                const resp = await fetch(RAG_BASE + '/rag/tools/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: toolsEnabledCb.checked })
                });
                const data = await resp.json();
                toolsEnabled = data.tools_enabled;
                updateUI();
            } catch (e) {
                console.error('[TOOLS] Toggle error:', e);
            }
        });

        // Close popups on outside click
        document.addEventListener('click', (e) => {
            if (!panel.contains(e.target)) {
                popup.classList.remove('visible');
                toolsPopup.classList.remove('visible');
            }
        });

        // Toggle RAG
        enabledCb.addEventListener('change', async () => {
            try {
                const resp = await fetch(RAG_BASE + '/rag/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: enabledCb.checked })
                });
                const data = await resp.json();
                ragEnabled = data.rag_enabled;
                updateUI();
            } catch (e) {
                console.error('[RAG] Toggle error:', e);
            }
        });

        // Reindex
        reindexBtn.addEventListener('click', async () => {
            reindexBtn.disabled = true;
            reindexBtn.textContent = 'Indexing...';
            try {
                await fetch(RAG_BASE + '/rag/reindex', { method: 'POST' });
                const waitForIndex = setInterval(async () => {
                    await pollStatus();
                    if (!ragStatus.is_indexing) {
                        clearInterval(waitForIndex);
                        reindexBtn.disabled = false;
                        reindexBtn.textContent = 'Reindex Documents';
                    }
                }, 1000);
            } catch (e) {
                console.error('[RAG] Reindex error:', e);
                reindexBtn.disabled = false;
                reindexBtn.textContent = 'Reindex Documents';
            }
        });

        // File upload via input
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) uploadFiles(fileInput.files);
            fileInput.value = '';
        });

        // Drag & drop
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        });
        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('drag-over');
        });
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) uploadFiles(e.dataTransfer.files);
        });

        // Initial status check + periodic poll
        pollStatus();
        loadFiles();
        pollTimer = setInterval(pollStatus, 5000);
    }

    // ========== File Management ==========
    async function loadFiles() {
        const listEl = document.getElementById('rag-file-list');
        if (!listEl) return;
        try {
            const resp = await fetch(RAG_BASE + '/rag/files');
            const data = await resp.json();
            fileList = data.files || [];
            renderFiles();
        } catch (e) {
            listEl.innerHTML = '<div class="rag-empty">Cannot load files</div>';
        }
    }

    function renderFiles() {
        const listEl = document.getElementById('rag-file-list');
        if (!listEl) return;

        if (fileList.length === 0) {
            listEl.innerHTML = '<div class="rag-empty">No documents yet</div>';
            return;
        }

        listEl.innerHTML = fileList.map(f => `
            <div class="rag-file-item">
                <svg class="rag-file-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <div class="rag-file-info">
                    <div class="rag-file-name" title="${f.name}">${f.name}</div>
                    <div class="rag-file-meta">${formatSize(f.size)} &middot; ${f.modified}</div>
                </div>
                <button class="rag-file-del" data-file="${f.name}" title="Delete">&times;</button>
            </div>
        `).join('');

        // Bind delete buttons
        listEl.querySelectorAll('.rag-file-del').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const name = btn.dataset.file;
                if (!confirm('Delete ' + name + '?')) return;
                await deleteFile(name);
            });
        });
    }

    async function uploadFiles(files) {
        const msgEl = document.getElementById('rag-upload-msg');
        msgEl.style.display = 'block';
        msgEl.textContent = 'Uploading...';

        try {
            const formData = new FormData();
            for (const f of files) formData.append('file', f);

            const resp = await fetch(RAG_BASE + '/rag/upload', {
                method: 'POST',
                body: formData,
            });
            const data = await resp.json();

            if (data.ok) {
                msgEl.textContent = 'Uploaded ' + data.files.join(', ');
            } else {
                msgEl.textContent = data.error || 'Upload failed';
                msgEl.style.color = '#ef4444';
            }
            setTimeout(() => { msgEl.style.display = 'none'; msgEl.style.color = ''; }, 3000);
            loadFiles();
        } catch (e) {
            msgEl.textContent = 'Upload error';
            msgEl.style.color = '#ef4444';
            setTimeout(() => { msgEl.style.display = 'none'; msgEl.style.color = ''; }, 3000);
        }
    }

    async function deleteFile(name) {
        try {
            const resp = await fetch(RAG_BASE + '/rag/files/' + encodeURIComponent(name), {
                method: 'DELETE',
            });
            await resp.json();
            loadFiles();
        } catch (e) {
            console.error('[RAG] Delete error:', e);
        }
    }

    // ========== Tools Panel ==========
    const TOOLS_INFO = [
        { cat: 'System', name: 'get_system_info', icon: '\uD83D\uDDA5\uFE0F', desc: 'OS, CPU, RAM, disk usage, uptime', params: 'none' },
        { cat: 'System', name: 'get_gpu_info', icon: '\uD83C\uDFAE', desc: 'GPU model, driver, VRAM, temp (NVIDIA)', params: 'none' },
        { cat: 'System', name: 'get_battery_info', icon: '\uD83D\uDD0B', desc: 'Battery charge, health, runtime (laptops)', params: 'none' },
        { cat: 'System', name: 'list_usb_devices', icon: '\uD83D\uDD0C', desc: 'Connected USB devices with VID/PID', params: 'none' },
        { cat: 'Files', name: 'list_files', icon: '\uD83D\uDCC2', desc: 'List files and directories with sizes', params: 'path' },
        { cat: 'Files', name: 'read_text_file', icon: '\uD83D\uDCC4', desc: 'Read full contents of a text file', params: 'path' },
        { cat: 'Files', name: 'search_in_files', icon: '\uD83D\uDD0D', desc: 'Search text in files recursively (grep)', params: 'path, query' },
        { cat: 'Files', name: 'get_file_sizes', icon: '\uD83D\uDCCA', desc: 'Disk space analysis sorted by size', params: 'path' },
        { cat: 'Files', name: 'read_logs', icon: '\uD83D\uDCDC', desc: 'Tail last N lines of a log file', params: 'path, lines' },
        { cat: 'Files', name: 'read_clipboard', icon: '\uD83D\uDCCB', desc: 'Read text from system clipboard', params: 'none' },
        { cat: 'Diagnostics', name: 'get_event_log', icon: '\u26A0\uFE0F', desc: 'Windows Event Log — errors, crashes, BSODs', params: 'log_name, level' },
        { cat: 'Diagnostics', name: 'get_disk_health', icon: '\uD83D\uDC9A', desc: 'SMART disk health, temp, wear, errors', params: 'none' },
        { cat: 'Diagnostics', name: 'list_startup_programs', icon: '\uD83D\uDE80', desc: 'Autorun programs (registry, startup, tasks)', params: 'none' },
        { cat: 'Diagnostics', name: 'list_installed_software', icon: '\uD83D\uDCE6', desc: 'Installed programs with versions', params: 'search' },
        { cat: 'Network', name: 'get_network_info', icon: '\uD83C\uDF10', desc: 'Hostname, IP addresses, adapters', params: 'none' },
        { cat: 'Network', name: 'list_open_ports', icon: '\uD83D\uDD13', desc: 'Open TCP/UDP ports with process names', params: 'none' },
        { cat: 'Security', name: 'get_security_status', icon: '\uD83D\uDEE1\uFE0F', desc: 'Defender, Firewall, UAC status', params: 'none' },
        { cat: 'Security', name: 'list_processes', icon: '\u2699\uFE0F', desc: 'Running processes sorted by memory', params: 'none' },
    ];

    function renderToolsList() {
        const listEl = document.getElementById('tools-list');
        if (!listEl) return;

        // Group by category
        const cats = {};
        TOOLS_INFO.forEach(t => {
            if (!cats[t.cat]) cats[t.cat] = [];
            cats[t.cat].push(t);
        });

        let html = '';
        for (const [cat, tools] of Object.entries(cats)) {
            html += `<div class="tool-cat-header">${cat}</div>`;
            html += tools.map(t => `
                <div class="tool-item">
                    <div class="tool-item-name">${t.icon} ${t.name}</div>
                    <div class="tool-item-desc">${t.desc}</div>
                    ${t.params !== 'none' ? `<div class="tool-item-params">${t.params}</div>` : ''}
                </div>
            `).join('');
        }
        listEl.innerHTML = html;
    }

    async function pollStatus() {
        try {
            const resp = await fetch(RAG_BASE + '/rag/status');
            ragStatus = await resp.json();
            ragEnabled = ragStatus.rag_enabled;
            reasoningEnabled = ragStatus.reasoning_enabled;
            toolsEnabled = ragStatus.tools_enabled || false;
            toolsAvailable = ragStatus.tools_available || false;
            updateUI();
        } catch (e) {
            ragStatus = {};
        }
    }

    function updateUI() {
        const toggleBtn = document.getElementById('rag-toggle-btn');
        const reasoningBtn = document.getElementById('reasoning-toggle-btn');
        const toolsBtn = document.getElementById('tools-toggle-btn');
        const enabledCb = document.getElementById('rag-enabled-cb');
        const toolsEnabledCb = document.getElementById('tools-enabled-cb');
        const statusText = document.getElementById('rag-status-text');
        const toolsStatusText = document.getElementById('tools-status-text');

        if (!toggleBtn) return;

        // Button appearance
        toggleBtn.classList.toggle('active', ragEnabled);
        enabledCb.checked = ragEnabled;

        // Reasoning button
        if (reasoningBtn) {
            reasoningBtn.classList.toggle('active', reasoningEnabled);
            reasoningBtn.title = reasoningEnabled ? 'Thinking: ON (click to disable)' : 'Thinking: OFF (click to enable)';
        }

        // Tools button & checkbox
        if (toolsBtn) {
            if (!toolsAvailable) {
                toolsBtn.style.display = 'none';
            } else {
                toolsBtn.style.display = 'flex';
                toolsBtn.classList.toggle('active', toolsEnabled);
                toolsBtn.title = toolsEnabled ? 'System Tools: ON (click to open)' : 'System Tools: OFF (click to open)';
            }
        }
        if (toolsEnabledCb) {
            toolsEnabledCb.checked = toolsEnabled;
        }
        if (toolsStatusText) {
            if (toolsEnabled) {
                toolsStatusText.innerHTML = '<span class="rag-dot rag-dot-on" style="background:#f97316"></span> Tools active — AI can inspect your system (read-only).';
            } else {
                toolsStatusText.innerHTML = 'Read-only system inspection — the AI can look but never modify.';
            }
        }

        // Status text
        const meta = ragStatus.meta || {};
        const parts = [];

        if (ragStatus.is_indexing) {
            parts.push('<span class="rag-dot rag-dot-loading"></span> Indexing...');
        } else if (ragStatus.has_index) {
            parts.push(`<span class="rag-dot rag-dot-on"></span> Index: ${meta.chunk_count || 0} chunks from ${meta.doc_count || 0} files`);
            if (meta.indexed_at) parts.push(`Updated: ${meta.indexed_at}`);
        } else {
            parts.push('<span class="rag-dot rag-dot-off"></span> No index. Place docs in <code>data/docs/</code> and click Reindex.');
        }

        statusText.innerHTML = parts.join('<br>');
    }

    // ========== Start ==========
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
