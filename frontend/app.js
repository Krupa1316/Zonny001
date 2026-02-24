/* ─────────────────────────────────────────────────────────
   Zonny v0.4 — app.js
   Chat + Agent Convo + IDE (Monaco + xterm) + Company
───────────────────────────────────────────────────────── */
'use strict';

// ═══ Config ═══
const DEFAULT_BASE = 'http://localhost:8000';
const DEFAULT_WS = 'ws://localhost:8000';
function getBase() { return localStorage.getItem('zonny_server') || DEFAULT_BASE; }
function getWsBase() { return getBase().replace(/^http/, 'ws'); }
function getApiKey() { return localStorage.getItem('zonny_api_key') || ''; }
function getWorkspace() { return localStorage.getItem('zonny_workspace') || 'outputs'; }

// ═══ DOM ═══
const $ = id => document.getElementById(id);
const els = {
  chatThread: $('chat-thread'), activityLog: $('activity-log'),
  chatInput: $('chat-input'), sendBtn: $('send-btn'),
  agentRoster: $('agent-roster'), statusDot: $('status-dot'),
  settingsBtn: $('settings-btn'), settingsModal: $('settings-modal'),
  closeModal: $('close-modal'), apiKeyInput: $('api-key-input'),
  saveKeyBtn: $('save-key-btn'), serverUrlInput: $('server-url-input'),
  saveUrlBtn: $('save-url-btn'), workspaceInput: $('workspace-path-input'),
  saveWorkspaceBtn: $('save-workspace-btn'), clearActivity: $('clear-activity'),
  uploadBtn: $('upload-btn'), fileInput: $('file-input'),
  convoThread: $('convo-thread'), convoMeta: $('convo-meta'), clearConvo: $('clear-convo'),
  fileTree: $('file-tree'), explorerPath: $('explorer-path'),
  editorTabsBar: $('editor-tabs-bar'), monacoEl: $('monaco-editor'),
  xtermContainer: $('xterm-container'), terminalReconnect: $('terminal-reconnect'),
  ideBrowseBtn: $('ide-browse-btn'),
  companyPrompt: $('company-prompt'), companyRunBtn: $('company-run-btn'),
  companyTranscript: $('company-transcript'), companyFiles: $('company-files'),
  companyShipReport: $('company-ship-report'), shipReportContent: $('ship-report-content'),
  previewIframe: $('preview-iframe'), previewUrl: $('preview-url'),
  previewRefresh: $('preview-refresh'), previewNewtab: $('preview-newtab'),
  previewEmpty: $('preview-empty'),
};

// ═══ State ═══
let agents = [], selectedAgent = null, agentLogs = {}, isProcessing = false;
let monacoEditor = null, openTabs = {}, activeTabFile = null;
let term = null, termWs = null, fitAddon = null;
let companySession = null, companyRunning = false;

// ═══ Utilities ═══
function escHtml(t) {
  return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function markdownLite(text) {
  let s = escHtml(text);
  s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\n/g, '<br>');
  return s;
}
function initials(name) { return name.split(/[\s_-]+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join(''); }
function timeNow() { return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
function authHdrs() { return { 'Authorization': getApiKey(), 'Content-Type': 'application/json' }; }

// ═══ Tab switching ═══
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`tab-${tab}`).classList.add('active');
    if (tab === 'ide') { setTimeout(() => { monacoEditor?.layout(); fitAddon?.fit(); }, 50); }
  });
});

// ═══════════════════════════════
// CHAT
// ═══════════════════════════════
async function loadAgents() {
  try {
    const r = await fetch(`${getBase()}/agents/status`, { headers: { 'Authorization': getApiKey() } });
    if (!r.ok) return;
    const d = await r.json();
    agents = d.agents || [];
    renderRoster();
  } catch (e) { console.warn('agents:', e); }
}
function renderRoster() {
  els.agentRoster.innerHTML = '';
  agents.forEach(a => {
    const card = document.createElement('div');
    card.className = 'agent-card'; card.dataset.name = a.name;
    card.innerHTML = `<div class="agent-row">
      <span class="agent-name">${a.name.replace('_agent', '').replace('_', ' ')}</span>
      <span class="agent-badge" id="badge-${a.name}">IDLE</span></div>
      <div class="agent-model">${a.model}</div>`;
    card.addEventListener('click', () => selectAgent(a));
    els.agentRoster.appendChild(card);
  });
}
function selectAgent(a) {
  selectedAgent = a.name;
  document.querySelectorAll('.agent-card').forEach(c => c.classList.toggle('selected', c.dataset.name === a.name));
  $('agent-detail').style.display = 'flex'; $('agent-detail').style.flexDirection = 'column'; $('agent-detail').style.gap = '10px';
  $('agent-detail-empty').style.display = 'none';
  $('detail-avatar').textContent = initials(a.name); $('detail-name').textContent = a.name; $('detail-model').textContent = a.model;
  renderDetailLog(a.name);
}
function renderDetailLog(name) {
  const entries = agentLogs[name] || [];
  $('detail-log').innerHTML = entries.length
    ? entries.slice(-6).map(e => `<div class="detail-log-entry">${escHtml(e.substring(0, 120))}</div>`).join('')
    : '<span style="font-size:11px;color:var(--text-muted)">No activity</span>';
}
function removeWelcome() { els.chatThread.querySelector('.welcome-msg')?.remove(); }
function appendMessage(role, text, agentName = '') {
  removeWelcome();
  const msg = document.createElement('div');
  msg.className = `chat-msg ${role === 'user' ? 'user' : 'agent'}`;
  const av = role === 'user' ? 'You' : (agentName ? initials(agentName) : 'Z');
  const label = role === 'user' ? 'You' : (agentName || 'Zonny');
  msg.innerHTML = `<div class="chat-avatar">${av}</div>
    <div><div class="chat-bubble">${markdownLite(text)}</div>
    <span class="chat-meta">${label} · ${timeNow()}</span></div>`;
  els.chatThread.appendChild(msg);
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}
function showTyping() {
  removeWelcome();
  const el = document.createElement('div');
  el.className = 'chat-msg agent typing-indicator'; el.id = 'typing-bubble';
  el.innerHTML = `<div class="chat-avatar">Z</div>
    <div class="chat-bubble"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>`;
  els.chatThread.appendChild(el);
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}
function removeTyping() { $('typing-bubble')?.remove(); }
function clearHint(el) { el.querySelector('.activity-hint')?.remove(); }
function addActivity(agent, text) {
  clearHint(els.activityLog);
  const item = document.createElement('div'); item.className = 'activity-item';
  item.innerHTML = `<div class="activity-dot" style="background:var(--brand)"></div>
    <span class="activity-agent">${agent}</span>
    <span class="activity-text"> — ${escHtml(text.slice(0, 90))}</span>`;
  els.activityLog.appendChild(item);
  els.activityLog.scrollTop = els.activityLog.scrollHeight;
}
async function sendMessage() {
  const text = els.chatInput.value.trim();
  if (!text || isProcessing) return;
  if (!getApiKey()) { alert('Set API key in Settings first.'); els.settingsModal.classList.remove('hidden'); return; }
  isProcessing = true; els.sendBtn.disabled = true; els.chatInput.value = ''; els.chatInput.style.height = 'auto';
  appendMessage('user', text);
  showTyping();
  els.activityLog.innerHTML = ''; addActivity('user', text);
  try {
    const r = await fetch(`${getBase()}/mcp`, { method: 'POST', headers: authHdrs(), body: JSON.stringify({ session: 'web-' + Date.now(), input: text }) });
    const data = await r.json();
    removeTyping();
    appendMessage('agent', data.response || 'No response.', 'Zonny');
    (data.conversation || []).forEach(msg => {
      addActivity(msg.agent, msg.content.slice(0, 100));
      if (!agentLogs[msg.agent]) agentLogs[msg.agent] = [];
      agentLogs[msg.agent].push(msg.content);
    });
    if (data.conversation?.length) renderConversation(data.conversation, data.specialist, text);
    if (selectedAgent) renderDetailLog(selectedAgent);
  } catch (e) { removeTyping(); appendMessage('agent', `Error: ${e.message}`); }
  finally { isProcessing = false; els.sendBtn.disabled = false; }
}
els.chatInput.addEventListener('input', () => { els.chatInput.style.height = 'auto'; els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 120) + 'px'; });
els.chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
els.sendBtn.addEventListener('click', sendMessage);

// ═══ Agent Conversation ═══
function renderConversation(conversation, specialist, userQuery) {
  els.convoMeta.textContent = `${conversation.length} messages · specialist: ${specialist || 'auto'}`;
  const empty = els.convoThread.querySelector('.convo-empty'); if (empty) empty.remove();
  const userEl = document.createElement('div'); userEl.className = 'convo-msg user-msg';
  userEl.innerHTML = `<div class="convo-avatar">You</div>
    <div class="convo-content"><div class="convo-header-row"><span class="convo-agent-name">You</span><span class="convo-role-tag">USER</span></div>
    <div class="convo-bubble">${markdownLite(userQuery)}</div></div>`;
  els.convoThread.appendChild(userEl);
  conversation.forEach((msg, i) => {
    const isAsst = msg.agent.includes('assistant'), isLast = i === conversation.length - 1;
    if (isAsst && isLast && conversation.length > 1) { const sep = document.createElement('div'); sep.className = 'final-separator'; sep.textContent = 'FINAL ANSWER'; els.convoThread.appendChild(sep); }
    const cls = isAsst ? 'assistant-msg' : 'specialist-msg', tag = isAsst ? 'SYNTHESISER' : 'SPECIALIST';
    const el = document.createElement('div'); el.className = `convo-msg ${cls}`;
    el.innerHTML = `<div class="convo-avatar">${initials(msg.agent)}</div>
      <div class="convo-content"><div class="convo-header-row"><span class="convo-agent-name">${msg.agent}</span><span class="convo-role-tag">${tag}</span></div>
      <div class="convo-bubble">${markdownLite(msg.content)}</div></div>`;
    els.convoThread.appendChild(el);
  });
  els.convoThread.scrollTop = els.convoThread.scrollHeight;
}
els.clearConvo.addEventListener('click', () => {
  els.convoThread.innerHTML = `<div class="convo-empty"><div class="welcome-icon">🤝</div><h3>Agent Conversation</h3><p>Discussion will appear here after you chat.</p></div>`;
  els.convoMeta.textContent = 'No conversation yet.';
});

// ═══════════════════════════════
// IDE — FILE TREE
// ═══════════════════════════════
let currentDir = getWorkspace();
async function loadFileTree(path) {
  currentDir = path;
  els.explorerPath.textContent = path;
  try {
    const r = await fetch(`${getBase()}/files/tree?path=${encodeURIComponent(path)}`, { headers: { 'Authorization': getApiKey() } });
    const d = await r.json();
    renderTree(d.entries || []);
  } catch (e) { els.fileTree.innerHTML = `<div class="tree-item" style="color:var(--accent-red)">Error loading dir</div>`; }
}
function renderTree(entries) {
  els.fileTree.innerHTML = '';
  // Back button
  const back = document.createElement('div'); back.className = 'tree-item';
  back.innerHTML = `<span class="tree-icon">↑</span><span class="tree-name">..</span>`;
  back.addEventListener('click', () => {
    const parts = currentDir.replace(/\\/g, '/').split('/'); parts.pop(); loadFileTree(parts.join('/') || '.');
  });
  els.fileTree.appendChild(back);
  entries.forEach(e => {
    const item = document.createElement('div');
    item.className = 'tree-item' + (e.type === 'directory' ? ' tree-dir' : '');
    const icon = e.type === 'directory' ? '📁' : fileIcon(e.ext || '');
    item.innerHTML = `<span class="tree-icon">${icon}</span><span class="tree-name">${escHtml(e.name)}</span>`;
    item.addEventListener('click', () => {
      if (e.type === 'directory') loadFileTree(e.path);
      else openFile(e.path, e.name);
    });
    els.fileTree.appendChild(item);
    if (activeTabFile === e.path) item.classList.add('active');
  });
}
function fileIcon(ext) {
  const m = { 'py': '🐍', 'js': '📜', 'ts': '📜', 'html': '🌐', 'css': '🎨', 'json': '📋', 'md': '📝', 'txt': '📄', 'sh': '⚙', 'yaml': '⚙', 'yml': '⚙' };
  return m[ext] || '📄';
}
function extFromName(name) { return name.split('.').pop().toLowerCase(); }

els.ideBrowseBtn.addEventListener('click', () => {
  const p = prompt('Enter directory path to open:', currentDir);
  if (p) loadFileTree(p);
});

// ═══ MONACO EDITOR ═══
const langMap = { 'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'html': 'html', 'css': 'css', 'json': 'json', 'md': 'markdown', 'sh': 'shell', 'yaml': 'yaml', 'yml': 'yaml', 'txt': 'plaintext' };
require(['vs/editor/editor.main'], () => {
  monacoEditor = monaco.editor.create($('monaco-editor'), {
    theme: 'vs-dark', fontSize: 14, minimap: { enabled: false },
    fontFamily: 'JetBrains Mono, monospace', fontLigatures: true,
    scrollBeyondLastLine: false, automaticLayout: true,
    value: '// Open a file from the explorer to start editing\n',
    language: 'plaintext',
  });
  monacoEditor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveCurrentFile);
});
async function openFile(path, name) {
  activeTabFile = path;
  if (openTabs[path]) { switchToTab(path); return; }
  try {
    const r = await fetch(`${getBase()}/files/read`, { method: 'POST', headers: authHdrs(), body: JSON.stringify({ path }) });
    if (!r.ok) throw new Error(`${r.status}`);
    const d = await r.json();
    const ext = extFromName(name);
    const lang = langMap[ext] || 'plaintext';
    openTabs[path] = { name, lang, content: d.content, model: monaco.editor.createModel(d.content, lang) };
    addEditorTab(path, name);
    switchToTab(path);
  } catch (e) { alert(`Cannot open file: ${e.message}`); }
}
function addEditorTab(path, name) {
  const hint = els.editorTabsBar.querySelector('.no-file-hint'); if (hint) hint.remove();
  const tab = document.createElement('div'); tab.className = 'editor-tab'; tab.dataset.path = path;
  tab.innerHTML = `<span>${escHtml(name)}</span><span class="editor-tab-close" data-close="${path}">✕</span>`;
  tab.addEventListener('click', e => {
    if (e.target.dataset.close) { closeTab(e.target.dataset.close); return; }
    switchToTab(path);
  });
  els.editorTabsBar.appendChild(tab);
}
function switchToTab(path) {
  activeTabFile = path;
  document.querySelectorAll('.editor-tab').forEach(t => t.classList.toggle('active', t.dataset.path === path));
  document.querySelectorAll('.tree-item').forEach(t => t.classList.remove('active'));
  if (monacoEditor && openTabs[path]) monacoEditor.setModel(openTabs[path].model);
}
function closeTab(path) {
  delete openTabs[path];
  document.querySelector(`.editor-tab[data-path="${CSS.escape(path)}"]`)?.remove();
  const remaining = Object.keys(openTabs);
  if (remaining.length) switchToTab(remaining[remaining.length - 1]);
  else { monacoEditor?.setValue('// Open a file to start editing'); activeTabFile = null; }
}
async function saveCurrentFile() {
  if (!activeTabFile || !monacoEditor) return;
  const content = monacoEditor.getValue();
  try {
    await fetch(`${getBase()}/files/write`, { method: 'POST', headers: authHdrs(), body: JSON.stringify({ path: activeTabFile, content }) });
    if (openTabs[activeTabFile]) openTabs[activeTabFile].content = content;
  } catch (e) { alert(`Save failed: ${e.message}`); }
}

// ═══ XTERM TERMINAL ═══
function initTerminal() {
  if (term) { term.dispose(); }
  term = new Terminal({
    theme: { background: '#0a0a0f', foreground: '#eaedf5', cursor: '#7c5cfc' },
    fontFamily: 'JetBrains Mono, monospace', fontSize: 13, cursorBlink: true
  });
  fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open($('xterm-container'));
  fitAddon.fit();
  connectTerminal();
}
function connectTerminal() {
  if (termWs) { try { termWs.close(); } catch (e) { } }
  const url = `${getWsBase()}/terminal?api_key=${encodeURIComponent(getApiKey())}`;
  termWs = new WebSocket(url);
  termWs.onopen = () => term.writeln('\r\x1b[32m[Terminal connected]\x1b[0m\r\n');
  termWs.onclose = () => term.writeln('\r\x1b[31m[Terminal disconnected]\x1b[0m');
  termWs.onerror = () => term.writeln('\r\x1b[31m[Terminal error — check API key]\x1b[0m');
  termWs.onmessage = e => term.write(e.data);
  term.onData(data => { if (termWs?.readyState === 1) termWs.send(data); });
}
els.terminalReconnect.addEventListener('click', connectTerminal);
window.addEventListener('resize', () => fitAddon?.fit());

// ═══════════════════════════════
// COMPANY
// ═══════════════════════════════
const AGENT_COLORS = {
  ceo_agent: 'agent-ceo', architect_agent: 'agent-architect',
  frontend_agent: 'agent-frontend', backend_agent: 'agent-backend',
  qa_agent: 'agent-qa', reviewer_agent: 'agent-reviewer',
};
const AGENT_ICONS = {
  ceo_agent: '👔', architect_agent: '🏗', frontend_agent: '🎨',
  backend_agent: '⚙', qa_agent: '🧪', reviewer_agent: '✅',
};
function setPipeStage(agent, status) {
  const el = document.querySelector(`.pipe-stage[data-agent="${agent}"]`);
  if (!el) return;
  el.classList.remove('running', 'done');
  if (status === 'running') el.classList.add('running');
  if (status === 'done') el.classList.add('done');
  el.querySelector('.pipe-status').textContent = status;
}
function resetPipeline() {
  document.querySelectorAll('.pipe-stage').forEach(s => { s.classList.remove('running', 'done'); s.querySelector('.pipe-status').textContent = 'idle'; });
}
function addCompanyMsg(agent, content) {
  const empty = els.companyTranscript.querySelector('.company-empty'); if (empty) empty.remove();
  const colorClass = AGENT_COLORS[agent] || 'agent-ceo';
  const icon = AGENT_ICONS[agent] || '🤖';
  const label = agent.replace('_agent', '').replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  const msg = document.createElement('div'); msg.className = 'company-msg';
  // Render code blocks separately
  const displayed = content.length > 3000 ? content.slice(0, 3000) + '…' : content;
  msg.innerHTML = `<div class="company-msg-header ${colorClass}">${icon} <strong>${label}</strong></div>
    <div class="company-msg-body">${markdownLite(displayed)}</div>`;
  els.companyTranscript.appendChild(msg);
  els.companyTranscript.scrollTop = els.companyTranscript.scrollHeight;
}
function addGeneratedFile(f) {
  const hint = els.companyFiles.querySelector('.activity-hint'); if (hint) hint.remove();
  const ext = f.split('.').pop().toLowerCase();
  const item = document.createElement('div'); item.className = 'gen-file-item';
  item.innerHTML = `<span class="gen-file-icon">${fileIcon(ext)}</span>
    <span class="gen-file-name">${escHtml(f)}</span>`;
  item.addEventListener('click', () => {
    if (companySession) openFile(`outputs/${companySession}/${f}`, f);
  });
  els.companyFiles.appendChild(item);
}
async function runCompany() {
  const prompt = els.companyPrompt.value.trim();
  if (!prompt || companyRunning) return;
  if (!getApiKey()) { alert('Set API key in Settings first.'); return; }
  companyRunning = true; els.companyRunBtn.disabled = true;
  companySession = 'cmp-' + Date.now().toString(36);
  resetPipeline();
  els.companyTranscript.innerHTML = '';
  els.companyFiles.innerHTML = '<p class="activity-hint">Generating…</p>';
  els.companyShipReport.style.display = 'none';
  let currentAgent = null;
  const body = JSON.stringify({ session: companySession, prompt });
  try {
    const r = await fetch(`${getBase()}/company/stream`, { method: 'POST', headers: authHdrs(), body });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        try {
          const ev = JSON.parse(line.slice(5).trim());
          if (ev.type === 'message') {
            if (currentAgent && currentAgent !== ev.agent) setPipeStage(currentAgent, 'done');
            currentAgent = ev.agent;
            setPipeStage(ev.agent, 'running');
            addCompanyMsg(ev.agent, ev.content);
            if (ev.files_extracted?.length) ev.files_extracted.forEach(f => addGeneratedFile(f));
          } else if (ev.type === 'done') {
            if (currentAgent) setPipeStage(currentAgent, 'done');
            if (ev.ship_report) {
              els.companyShipReport.style.display = 'block';
              els.shipReportContent.textContent = ev.ship_report.replace(/TERMINATE/g, '').trim();
            }
            if (ev.files) {
              els.companyFiles.innerHTML = '';
              Object.keys(ev.files).forEach(f => addGeneratedFile(f));
            }
            // Refresh IDE file tree to show new files
            loadFileTree(`outputs/${companySession}`);
            // Auto-open preview
            loadPreview(companySession);
          }
        } catch (e) { }
      }
    }
  } catch (e) { addCompanyMsg('system', 'Error: ' + e.message); }
  finally { companyRunning = false; els.companyRunBtn.disabled = false; }
}
els.companyRunBtn.addEventListener('click', runCompany);
els.companyPrompt.addEventListener('keydown', e => { if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); runCompany(); } });

// ═══════════════════════════════
// PREVIEW
// ═══════════════════════════════
function loadPreview(session) {
  if (!session) return;
  const url = `${getBase()}/preview/${session}`;
  els.previewIframe.src = url;
  els.previewUrl.textContent = url;
  els.previewEmpty.classList.add('hidden');
  // Switch to preview tab
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="preview"]').classList.add('active');
  $('tab-preview').classList.add('active');
}
els.previewRefresh.addEventListener('click', () => {
  if (companySession) els.previewIframe.src = `${getBase()}/preview/${companySession}`;
});
els.previewNewtab.addEventListener('click', () => {
  if (companySession) window.open(`${getBase()}/preview/${companySession}`, '_blank');
});

// ═══ Settings ═══
els.settingsBtn.addEventListener('click', () => {
  els.apiKeyInput.value = getApiKey(); els.serverUrlInput.value = getBase(); els.workspaceInput.value = getWorkspace();
  els.settingsModal.classList.remove('hidden');
});
els.closeModal.addEventListener('click', () => els.settingsModal.classList.add('hidden'));
els.settingsModal.addEventListener('click', e => { if (e.target === els.settingsModal) els.settingsModal.classList.add('hidden'); });
els.saveKeyBtn.addEventListener('click', () => { localStorage.setItem('zonny_api_key', els.apiKeyInput.value.trim()); loadAgents(); els.settingsModal.classList.add('hidden'); });
els.saveUrlBtn.addEventListener('click', () => { localStorage.setItem('zonny_server', els.serverUrlInput.value.trim()); els.settingsModal.classList.add('hidden'); });
els.saveWorkspaceBtn.addEventListener('click', () => { localStorage.setItem('zonny_workspace', els.workspaceInput.value.trim()); loadFileTree(els.workspaceInput.value.trim()); els.settingsModal.classList.add('hidden'); });
els.clearActivity.addEventListener('click', () => { els.activityLog.innerHTML = '<p class="activity-hint">Activity will appear here…</p>'; });
els.uploadBtn.addEventListener('click', () => els.fileInput.click());
els.fileInput.addEventListener('change', async () => {
  const file = els.fileInput.files[0]; if (!file) return;
  const form = new FormData(); form.append('file', file);
  try { const r = await fetch(`${getBase()}/v1/upload`, { method: 'POST', headers: { 'Authorization': getApiKey() }, body: form }); const d = await r.json(); addActivity('system', `Uploaded ${file.name}`); } catch (e) { addActivity('system', 'Upload failed'); }
  els.fileInput.value = '';
});

// ═══ Server health ═══
async function checkServer() {
  try { const r = await fetch(`${getBase()}/`); els.statusDot.classList.toggle('offline', !r.ok); }
  catch { els.statusDot.classList.add('offline'); }
}

// ═══ Boot ═══
checkServer();
setInterval(checkServer, 30000);
loadAgents();
loadFileTree(getWorkspace());
// Terminal inits once IDE tab is first visited
document.querySelector('[data-tab="ide"]').addEventListener('click', () => {
  if (!term) setTimeout(initTerminal, 100);
}, { once: true });
