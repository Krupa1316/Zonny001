/* ─────────────────────────────────────────────────────────
   Zonny Web UI — app.js  v0.3.1
   Fixes:
     • Chat messages display in correct order
     • User message shows first, typing indicator then final answer
     • Agent Conversation tab shows full interrnal discussion
     • SSE activity feed still visible live during processing
───────────────────────────────────────────────────────── */

'use strict';

// ═══ Config ═══
const DEFAULT_BASE = 'http://localhost:8000';

function getBase() { return localStorage.getItem('zonny_server') || DEFAULT_BASE; }
function getApiKey() { return localStorage.getItem('zonny_api_key') || ''; }

// ═══ DOM refs ═══
const els = {
  chatThread: document.getElementById('chat-thread'),
  activityLog: document.getElementById('activity-log'),
  chatInput: document.getElementById('chat-input'),
  sendBtn: document.getElementById('send-btn'),
  agentRoster: document.getElementById('agent-roster'),
  statusDot: document.getElementById('status-dot'),
  settingsBtn: document.getElementById('settings-btn'),
  settingsModal: document.getElementById('settings-modal'),
  closeModal: document.getElementById('close-modal'),
  apiKeyInput: document.getElementById('api-key-input'),
  saveKeyBtn: document.getElementById('save-key-btn'),
  serverUrlInput: document.getElementById('server-url-input'),
  saveUrlBtn: document.getElementById('save-url-btn'),
  uploadBtn: document.getElementById('upload-btn'),
  fileInput: document.getElementById('file-input'),
  clearActivity: document.getElementById('clear-activity'),
  pipelineBar: document.getElementById('pipeline-bar'),
  agentDetail: document.getElementById('agent-detail'),
  agentDetailEmpty: document.getElementById('agent-detail-empty'),
  detailAvatar: document.getElementById('detail-avatar'),
  detailName: document.getElementById('detail-name'),
  detailModel: document.getElementById('detail-model'),
  detailTask: document.getElementById('detail-task'),
  detailStatus: document.getElementById('detail-status'),
  detailLog: document.getElementById('detail-log'),
  // Conversation tab
  convoThread: document.getElementById('convo-thread'),
  convoMeta: document.getElementById('convo-meta'),
  clearConvo: document.getElementById('clear-convo'),
};

// ═══ State ═══
let agents = [];
let selectedAgent = null;
let agentLogs = {};   // name → [{content, time}]
let isProcessing = false;
let lastConversation = [];

// ═══ Tab switching ═══
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
  });
});

// ═══ Utilities ═══
function escapeHtml(t) {
  return t
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function markdownLite(text) {
  let s = escapeHtml(text);
  // Code blocks
  s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  // Inline code
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // Newlines
  s = s.replace(/\n/g, '<br>');
  return s;
}

function initials(name) {
  return name.split(/[\s_-]+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');
}

function timeNow() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function authHeaders() {
  return { 'Authorization': getApiKey(), 'Content-Type': 'application/json' };
}

// ═══ Server health check ═══
async function checkServer() {
  try {
    const r = await fetch(`${getBase()}/`, { method: 'GET' });
    els.statusDot.classList.toggle('offline', !r.ok);
  } catch {
    els.statusDot.classList.add('offline');
  }
}
setInterval(checkServer, 30000);
checkServer();

// ═══ Agent Roster ═══
async function loadAgents() {
  try {
    const r = await fetch(`${getBase()}/agents/status`, {
      headers: { 'Authorization': getApiKey() }
    });
    if (!r.ok) return;
    const data = await r.json();
    agents = data.agents || [];
    renderRoster();
    renderPipeline();
  } catch (e) {
    console.warn('Agent load failed:', e);
  }
}

function renderRoster() {
  els.agentRoster.innerHTML = '';
  agents.forEach(a => {
    const card = document.createElement('div');
    card.className = 'agent-card';
    card.dataset.name = a.name;
    card.innerHTML = `
      <div class="agent-row">
        <span class="agent-name">${a.name.replace('_agent', '').replace('_', ' ')}</span>
        <span class="agent-badge" id="badge-${a.name}">IDLE</span>
      </div>
      <div class="agent-model">${a.model}</div>`;
    card.addEventListener('click', () => selectAgent(a));
    els.agentRoster.appendChild(card);
  });
}

function setAgentStatus(name, status) {
  const badge = document.getElementById(`badge-${name}`);
  const card = document.querySelector(`[data-name="${name}"]`);
  if (!badge || !card) return;
  const labels = { idle: 'IDLE', active: 'ACTIVE', thinking: 'THINKING', done: 'DONE' };
  badge.textContent = (labels[status] || status).toUpperCase();
  badge.className = 'agent-badge' + (status === 'active' || status === 'thinking' ? ' active-badge' : '');
  card.classList.toggle('active', status === 'active' || status === 'thinking');
}

function resetAllStatuses() {
  agents.forEach(a => setAgentStatus(a.name, 'idle'));
}

// ═══ Agent detail (right panel) ═══
function selectAgent(a) {
  selectedAgent = a.name;
  document.querySelectorAll('.agent-card').forEach(c =>
    c.classList.toggle('selected', c.dataset.name === a.name));
  els.agentDetail.style.display = 'flex';
  els.agentDetail.style.flexDirection = 'column';
  els.agentDetail.style.gap = '14px';
  els.agentDetailEmpty.style.display = 'none';
  els.detailAvatar.textContent = initials(a.name);
  els.detailName.textContent = a.name;
  els.detailModel.textContent = a.model;
  renderDetailLog(a.name);
}

function renderDetailLog(name) {
  const entries = agentLogs[name] || [];
  if (entries.length === 0) {
    els.detailLog.innerHTML = '<span style="font-size:11px;color:var(--text-muted)">No activity yet</span>';
    return;
  }
  els.detailLog.innerHTML = entries.slice(-8).map(e =>
    `<div class="detail-log-entry" title="${timeNow()}">${escapeHtml(e.substring(0, 140))}${e.length > 140 ? '…' : ''}</div>`
  ).join('');
}

// ═══ Pipeline Visualization ═══
function renderPipeline() {
  const nodes = ['User', ...agents.map(a => a.name.replace('_agent', '')), 'Final'];
  els.pipelineBar.innerHTML = nodes.map((n, i) => `
    <div class="pipe-node" id="pipe-${i}">
      <div class="pipe-dot" id="pipe-dot-${i}">${i === 0 ? '👤' : i === nodes.length - 1 ? '✓' : initials(n)}</div>
      <div class="pipe-label">${n}</div>
    </div>`).join('');
}

function activatePipeNode(index, done = false) {
  const dot = document.getElementById(`pipe-dot-${index}`);
  if (!dot) return;
  dot.className = 'pipe-dot ' + (done ? 'done' : 'active');
}

// ═══ Chat Thread ═══
function removeWelcome() {
  const w = els.chatThread.querySelector('.welcome-msg');
  if (w) w.remove();
}

function appendMessage(role, text, agentName = '') {
  removeWelcome();
  const msg = document.createElement('div');
  msg.className = `chat-msg ${role === 'user' ? 'user' : 'agent'}`;
  const av = role === 'user' ? 'You' : (agentName ? initials(agentName) : 'Z');
  const label = role === 'user' ? 'You' : (agentName || 'Zonny');
  msg.innerHTML = `
    <div class="chat-avatar">${av}</div>
    <div>
      <div class="chat-bubble">${markdownLite(text)}</div>
      <span class="chat-meta">${label} · ${timeNow()}</span>
    </div>`;
  els.chatThread.appendChild(msg);
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
  return msg;
}

function showTyping() {
  removeWelcome();
  const el = document.createElement('div');
  el.className = 'chat-msg agent typing-indicator';
  el.id = 'typing-bubble';
  el.innerHTML = `
    <div class="chat-avatar">Z</div>
    <div class="chat-bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>`;
  els.chatThread.appendChild(el);
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typing-bubble');
  if (t) t.remove();
}

// ═══ Activity Feed ═══
function clearHint() {
  const hint = els.activityLog.querySelector('.activity-hint');
  if (hint) hint.remove();
}

function addActivity(agentName, text) {
  clearHint();
  const colors = {
    user: '#f5c842', system: '#555b72',
  };
  const cls = agentName === 'user' ? 'user-agent'
    : agentName === 'system' ? 'system-agent' : '';
  const item = document.createElement('div');
  item.className = 'activity-item';
  const short = text.length > 90 ? text.slice(0, 90) + '…' : text;
  item.innerHTML = `
    <div class="activity-dot" style="background:${colors[agentName] || '#7c5cfc'}"></div>
    <span class="activity-agent ${cls}">${agentName}</span>
    <span class="activity-text"> — ${escapeHtml(short)}</span>`;
  els.activityLog.appendChild(item);
  els.activityLog.scrollTop = els.activityLog.scrollHeight;
}

// ═══ Agent Conversation Tab ═══
function renderConversation(conversation, specialist, userQuery) {
  lastConversation = conversation;

  // Switch meta label
  els.convoMeta.textContent = `${conversation.length} messages · Specialist: ${specialist || 'auto'}`;

  // Remove empty state
  const empty = els.convoThread.querySelector('.convo-empty');
  if (empty) empty.remove();

  // Clear previous
  els.convoThread.innerHTML = '';

  // User message first
  const userEl = document.createElement('div');
  userEl.className = 'convo-msg user-msg';
  userEl.innerHTML = `
    <div class="convo-avatar">You</div>
    <div class="convo-content">
      <div class="convo-header-row">
        <span class="convo-agent-name">You</span>
        <span class="convo-role-tag">USER</span>
      </div>
      <div class="convo-bubble">${markdownLite(userQuery)}</div>
    </div>`;
  els.convoThread.appendChild(userEl);

  // Agent messages
  conversation.forEach((msg, i) => {
    const isAssistant = msg.agent.includes('assistant') || msg.agent === 'synthesiser';
    const isLast = i === conversation.length - 1;

    if (isAssistant && isLast && conversation.length > 1) {
      // Add visual separator before final answer
      const sep = document.createElement('div');
      sep.className = 'final-separator';
      sep.textContent = '✓ FINAL ANSWER';
      els.convoThread.appendChild(sep);
    }

    const cls = isAssistant ? 'assistant-msg' : 'specialist-msg';
    const tag = isAssistant ? 'SYNTHESISER' : 'SPECIALIST';

    const el = document.createElement('div');
    el.className = `convo-msg ${cls}`;
    el.innerHTML = `
      <div class="convo-avatar">${initials(msg.agent)}</div>
      <div class="convo-content">
        <div class="convo-header-row">
          <span class="convo-agent-name">${msg.agent}</span>
          <span class="convo-role-tag">${tag}</span>
        </div>
        <div class="convo-bubble">${markdownLite(msg.content)}</div>
      </div>`;
    els.convoThread.appendChild(el);
  });

  els.convoThread.scrollTop = els.convoThread.scrollHeight;
}

// ═══ Send Message ═══
async function sendMessage() {
  const text = els.chatInput.value.trim();
  if (!text || isProcessing) return;

  const key = getApiKey();
  if (!key) {
    alert('Please set your API key in Settings first.');
    els.settingsModal.classList.remove('hidden');
    return;
  }

  isProcessing = true;
  els.sendBtn.disabled = true;
  els.chatInput.value = '';
  els.chatInput.style.height = 'auto';

  // 1. Show user message immediately (correct order)
  appendMessage('user', text);
  activatePipeNode(0, true);

  // 2. Show typing indicator while waiting
  showTyping();

  // 3. Clear previous activity
  els.activityLog.innerHTML = '';
  addActivity('user', text);

  try {
    const response = await fetch(`${getBase()}/mcp`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ session: 'web-' + Date.now(), input: text }),
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(`Server error ${response.status}: ${err}`);
    }

    const data = await response.json();

    // 4. Remove typing, show final answer
    removeTyping();

    const finalText = data.response || 'No response.';
    const conversation = data.conversation || [];
    const specialist = data.specialist || '';

    appendMessage('agent', finalText, 'Zonny');
    activatePipeNode(agents.length + 1, true);

    // 5. Populate activity feed from conversation transcript
    conversation.forEach(msg => {
      addActivity(msg.agent, msg.content.slice(0, 120));
      // Update agent status badge briefly
      setAgentStatus(msg.agent, 'done');
      // Store in agent logs
      if (!agentLogs[msg.agent]) agentLogs[msg.agent] = [];
      agentLogs[msg.agent].push(msg.content);
    });

    // 6. Populate Agent Conversation tab
    renderConversation(conversation, specialist, text);

    // 7. Update detail if an agent is selected
    if (selectedAgent && agentLogs[selectedAgent]) {
      renderDetailLog(selectedAgent);
    }

    // Specialist pipeline highlight
    if (specialist) {
      const aIdx = agents.findIndex(a => a.name === specialist);
      if (aIdx >= 0) activatePipeNode(aIdx + 1, true);
      setAgentStatus(specialist, 'done');
    }

  } catch (err) {
    removeTyping();
    appendMessage('agent', `Error: ${err.message}`);
    addActivity('system', `Error: ${err.message}`);
  } finally {
    isProcessing = false;
    els.sendBtn.disabled = false;
    resetAllStatuses();
  }
}

// ═══ Input auto-resize ═══
els.chatInput.addEventListener('input', () => {
  els.chatInput.style.height = 'auto';
  els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 120) + 'px';
});

els.chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
els.sendBtn.addEventListener('click', sendMessage);

// ═══ Settings ═══
els.settingsBtn.addEventListener('click', () => {
  els.apiKeyInput.value = getApiKey();
  els.serverUrlInput.value = getBase();
  els.settingsModal.classList.remove('hidden');
});
els.closeModal.addEventListener('click', () => els.settingsModal.classList.add('hidden'));
els.settingsModal.addEventListener('click', e => { if (e.target === els.settingsModal) els.settingsModal.classList.add('hidden'); });
els.saveKeyBtn.addEventListener('click', () => {
  localStorage.setItem('zonny_api_key', els.apiKeyInput.value.trim());
  loadAgents();
  els.settingsModal.classList.add('hidden');
});
els.saveUrlBtn.addEventListener('click', () => {
  localStorage.setItem('zonny_server', els.serverUrlInput.value.trim());
  checkServer();
  loadAgents();
  els.settingsModal.classList.add('hidden');
});

// ═══ Clear buttons ═══
els.clearActivity.addEventListener('click', () => {
  els.activityLog.innerHTML = '<p class="activity-hint">Agent activity will appear here during processing…</p>';
});
els.clearConvo.addEventListener('click', () => {
  els.convoThread.innerHTML = `
    <div class="convo-empty">
      <div class="welcome-icon">🤝</div>
      <h3>Agent Conversation</h3>
      <p>Full internal agent discussion will appear here after you chat.</p>
    </div>`;
  els.convoMeta.textContent = 'No conversation yet. Send a message in Chat.';
});

// ═══ File upload ═══
els.uploadBtn.addEventListener('click', () => els.fileInput.click());
els.fileInput.addEventListener('change', async () => {
  const file = els.fileInput.files[0];
  if (!file) return;
  addActivity('system', `Uploading ${file.name}…`);
  const form = new FormData();
  form.append('file', file);
  try {
    const r = await fetch(`${getBase()}/v1/upload`, {
      method: 'POST',
      headers: { 'Authorization': getApiKey() },
      body: form,
    });
    const data = await r.json();
    addActivity('system', `Uploaded: ${file.name} (${data.chunks || '?'} chunks)`);
  } catch (e) {
    addActivity('system', `Upload failed: ${e.message}`);
  }
  els.fileInput.value = '';
});

// ═══ Boot ═══
loadAgents();
