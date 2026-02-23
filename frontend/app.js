/**
 * Zonny Web UI — app.js
 * 
 * Handles:
 *   - API key management (localStorage)
 *   - Agent roster loading + status updates
 *   - SSE streaming from /stream endpoint
 *   - Chat message rendering (markdown-lite)
 *   - Pipeline visualization
 *   - Agent detail sidebar
 *   - Document upload to /v1/upload
 */

'use strict';

// ─── State ───────────────────────────────────────────────────────────────────
const state = {
  apiKey: localStorage.getItem('zonny_api_key') || '',
  session: `session-${Date.now()}`,
  agents: [],           // [{name, model, description, status, priority}]
  selectedAgent: null,  // agent name
  activeStream: null,   // EventSource
  agentLogs: {},        // {name: [logEntry, ...]}
  lastDocId: null,
};

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const els = {
  agentList:        $('agent-list'),
  chatThread:       $('chat-thread'),
  activityLog:      $('activity-log'),
  messageInput:     $('message-input'),
  sendBtn:          $('send-btn'),
  settingsBtn:      $('settings-btn'),
  settingsModal:    $('settings-modal'),
  apiKeyInput:      $('api-key-input'),
  saveKeyBtn:       $('save-key-btn'),
  closeSettingsBtn: $('close-settings-btn'),
  connectionStatus: $('connection-status'),
  fileUploadBtn:    $('file-upload-btn'),
  clearActivityBtn: $('clear-activity-btn'),
  pipelineTrack:    document.querySelector('.pipeline-track'),
  detailEmpty:      $('detail-empty'),
  detailContent:    $('detail-content'),
  detailAvatar:     $('detail-avatar'),
  detailName:       $('detail-name'),
  detailModel:      $('detail-model'),
  detailTask:       $('detail-task'),
  detailStatus:     $('detail-status'),
  detailTools:      $('detail-tools'),
  detailLog:        $('detail-log'),
};

// ─── API Helpers ─────────────────────────────────────────────────────────────
const apiHeaders = () => ({
  'Authorization': state.apiKey,
  'Content-Type': 'application/json',
});

async function apiFetch(path, opts = {}) {
  return fetch(path, {
    ...opts,
    headers: { ...(opts.headers || {}), Authorization: state.apiKey },
  });
}

// ─── Agent Roster ─────────────────────────────────────────────────────────────
async function loadAgents() {
  if (!state.apiKey) {
    els.agentList.innerHTML = '<p style="color:var(--text-muted);font-size:12px;padding:8px">Set an API key in settings to load agents.</p>';
    return;
  }
  try {
    const res = await apiFetch('/agents/status');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.agents = data.agents || [];
    renderAgentRoster();
    buildPipeline();
    setConnectionStatus('ok');
  } catch (e) {
    setConnectionStatus('err');
    console.error('Failed to load agents:', e);
  }
}

function renderAgentRoster() {
  els.agentList.innerHTML = '';
  state.agents.forEach(agent => {
    const card = document.createElement('div');
    card.className = `agent-card ${agent.name === state.selectedAgent ? 'selected' : ''}`;
    card.dataset.name = agent.name;
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.innerHTML = `
      <div class="agent-card-top">
        <span class="agent-card-name">${formatAgentName(agent.name)}</span>
        <span class="agent-badge badge-${agent.status || 'idle'}">${agent.status || 'idle'}</span>
      </div>
      <div class="agent-model">${agent.model || ''}</div>
      <div class="agent-progress"><div class="agent-progress-bar"></div></div>
    `;
    card.addEventListener('click', () => selectAgent(agent.name));
    card.addEventListener('keydown', e => { if (e.key === 'Enter') selectAgent(agent.name); });
    els.agentList.appendChild(card);
  });
}

function updateAgentStatus(agentName, status) {
  const agent = state.agents.find(a => a.name === agentName);
  if (agent) agent.status = status;

  const card = els.agentList.querySelector(`[data-name="${agentName}"]`);
  if (!card) return;
  card.className = `agent-card ${agentName === state.selectedAgent ? 'selected' : ''} ${status === 'idle' ? '' : status}`;
  const badge = card.querySelector('.agent-badge');
  if (badge) {
    badge.className = `agent-badge badge-${status}`;
    badge.textContent = status;
  }

  // Update pipeline node
  const pipeNode = document.querySelector(`.pipeline-node[data-node="${agentName}"]`);
  if (pipeNode) {
    pipeNode.className = `pipeline-node ${status === 'active' ? 'active' : status === 'idle' ? '' : 'done'}`;
  }
}

function selectAgent(name) {
  state.selectedAgent = name;
  // Update card selection
  document.querySelectorAll('.agent-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.name === name);
  });
  const agent = state.agents.find(a => a.name === name);
  if (!agent) return;
  els.detailEmpty.classList.add('hidden');
  els.detailContent.classList.remove('hidden');
  els.detailAvatar.textContent = formatAgentName(agent.name)[0].toUpperCase();
  els.detailName.textContent = formatAgentName(agent.name);
  els.detailModel.textContent = agent.model || 'unknown';
  els.detailStatus.textContent = agent.status || 'idle';
  els.detailTask.textContent = agent.currentTask || '—';

  // Tools from manifest description
  els.detailTools.innerHTML = '';
  if (agent.description) {
    const tools = agent.description.match(/\w+/g)?.slice(0, 5) || [];
    tools.forEach(t => {
      const li = document.createElement('li');
      li.textContent = t;
      els.detailTools.appendChild(li);
    });
  }

  // Activity log
  const logs = state.agentLogs[name] || [];
  els.detailLog.innerHTML = logs.slice(-8).map(l => `<li>${escapeHtml(l)}</li>`).join('') || '<li>No activity yet</li>';
}

// ─── Pipeline ─────────────────────────────────────────────────────────────────
function buildPipeline() {
  const track = els.pipelineTrack;
  // Remove dynamically inserted nodes (keep #pipe-user and #pipe-final)
  track.querySelectorAll('.pipeline-node:not(#pipe-user):not(#pipe-final)').forEach(n => n.remove());

  const finalNode = $('pipe-final');
  state.agents.forEach(agent => {
    const node = document.createElement('div');
    node.className = 'pipeline-node';
    node.dataset.node = agent.name;
    node.innerHTML = `<div class="node-dot"></div><span class="node-label">${formatAgentName(agent.name)}</span>`;
    track.insertBefore(node, finalNode);
  });
}

// ─── Chat ─────────────────────────────────────────────────────────────────────
function appendMessage(role, content, agentName = null) {
  // Remove welcome message
  const welcome = els.chatThread.querySelector('.welcome-msg');
  if (welcome) welcome.remove();

  const msg = document.createElement('div');
  msg.className = `chat-msg ${role}`;
  const avatar = role === 'user' ? '👤' : (agentName ? formatAgentName(agentName)[0] : '⬡');
  msg.innerHTML = `
    <div class="chat-avatar">${avatar}</div>
    <div>
      <div class="chat-bubble">${markdownLite(content)}</div>
      ${agentName ? `<div class="bubble-meta">${formatAgentName(agentName)}</div>` : ''}
    </div>
  `;
  els.chatThread.appendChild(msg);
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}

// ─── Activity Feed ───────────────────────────────────────────────────────────
function appendActivity(agentName, text) {
  const empty = els.activityLog.querySelector('.activity-empty');
  if (empty) empty.remove();

  const item = document.createElement('div');
  item.className = 'activity-item';
  item.innerHTML = `
    <div class="activity-dot"></div>
    <div>
      <span class="activity-agent">${formatAgentName(agentName)}</span>
      <span class="activity-text"> — ${escapeHtml(text.slice(0, 120))}${text.length > 120 ? '…' : ''}</span>
    </div>
  `;
  els.activityLog.appendChild(item);
  els.activityLog.scrollTop = els.activityLog.scrollHeight;

  // Log to detail panel
  if (!state.agentLogs[agentName]) state.agentLogs[agentName] = [];
  state.agentLogs[agentName].push(text.slice(0, 80));
  if (state.agentLogs[agentName].length > 20) state.agentLogs[agentName].shift();

  // Refresh detail if this agent is selected
  if (state.selectedAgent === agentName) {
    const logs = state.agentLogs[agentName];
    els.detailLog.innerHTML = logs.slice(-8).map(l => `<li>${escapeHtml(l)}</li>`).join('');
  }
}

// ─── Send Message ─────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = els.messageInput.value.trim();
  if (!text || !state.apiKey) return;

  if (!state.apiKey) {
    showToast('⚠️ Please set your API key in Settings first!');
    $('settings-modal').classList.remove('hidden');
    return;
  }

  appendMessage('user', text);
  els.messageInput.value = '';
  resizeTextarea();
  setInputDisabled(true);

  // Reset agent statuses
  state.agents.forEach(a => updateAgentStatus(a.name, 'idle'));
  $('pipe-user').className = 'pipeline-node active';

  let finalResponse = '';

  // Open SSE stream
  const url = new URL('/stream', window.location.href);
  url.searchParams.set('task', text);
  url.searchParams.set('session', state.session);

  // SSE via fetch (to include auth header)
  try {
    const res = await apiFetch(url.toString(), { method: 'GET' });
    if (!res.ok) throw new Error(`Stream error: ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(line.slice(6));
          handleStreamEvent(event);
          if (event.type === 'message') finalResponse = event.content;
        } catch { /* skip parse errors */ }
      }
    }
  } catch (err) {
    console.error('Stream failed, falling back to /mcp:', err);
    // Fallback: direct /mcp call
    try {
      const res = await apiFetch('/mcp', {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ session: state.session, input: text }),
      });
      const data = await res.json();
      finalResponse = data.response || 'No response.';
    } catch (e2) {
      finalResponse = `❌ Error: ${e2.message}`;
    }
  }

  if (finalResponse) {
    appendMessage('agent', finalResponse, 'Zonny');
    $('pipe-final').className = 'pipeline-node done';
  }

  state.agents.forEach(a => updateAgentStatus(a.name, 'idle'));
  setInputDisabled(false);
  els.messageInput.focus();
}

function handleStreamEvent(event) {
  if (!event || !event.type) return;

  switch (event.type) {
    case 'message':
      if (event.agent && event.agent !== 'system') {
        updateAgentStatus(event.agent, 'active');
        appendActivity(event.agent, event.content || '');
      }
      break;
    case 'thinking':
      if (event.agent) updateAgentStatus(event.agent, 'thinking');
      break;
    case 'complete':
    case 'done':
      state.agents.forEach(a => updateAgentStatus(a.name, 'idle'));
      $('pipe-final').className = 'pipeline-node done';
      break;
    case 'error':
      appendActivity('system', `Error: ${event.content}`);
      break;
  }
}

// ─── Document Upload ──────────────────────────────────────────────────────────
els.fileUploadBtn.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  showToast(`📎 Uploading ${file.name}...`);

  const form = new FormData();
  form.append('file', file);
  form.append('conversation_id', state.session);

  try {
    const res = await fetch('/v1/upload', {
      method: 'POST',
      headers: { Authorization: state.apiKey },
      body: form,
    });
    const data = await res.json();
    state.lastDocId = data.document_id;
    showToast(`✅ Uploaded: ${file.name}`);
    appendActivity('system', `Document uploaded: ${file.name} (ID: ${data.document_id.slice(0,8)}...)`);
  } catch (err) {
    showToast(`❌ Upload failed: ${err.message}`);
  }
  e.target.value = '';
});

// ─── Settings Modal ───────────────────────────────────────────────────────────
els.settingsBtn.addEventListener('click', () => {
  els.apiKeyInput.value = state.apiKey;
  els.settingsModal.classList.remove('hidden');
});

els.closeSettingsBtn.addEventListener('click', () => els.settingsModal.classList.add('hidden'));
els.settingsModal.querySelector('.modal-backdrop').addEventListener('click', () => els.settingsModal.classList.add('hidden'));

els.saveKeyBtn.addEventListener('click', () => {
  const key = els.apiKeyInput.value.trim();
  state.apiKey = key;
  localStorage.setItem('zonny_api_key', key);
  els.settingsModal.classList.add('hidden');
  loadAgents();
  showToast('✅ API key saved');
});

// ─── Input Handling ───────────────────────────────────────────────────────────
els.messageInput.addEventListener('input', () => {
  resizeTextarea();
  els.sendBtn.disabled = !els.messageInput.value.trim() || !state.apiKey;
});

els.messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!els.sendBtn.disabled) sendMessage();
  }
});

els.sendBtn.addEventListener('click', sendMessage);

els.clearActivityBtn.addEventListener('click', () => {
  els.activityLog.innerHTML = '<p class="activity-empty">Agent activity will appear here during processing...</p>';
  state.agentLogs = {};
});

function resizeTextarea() {
  const t = els.messageInput;
  t.style.height = 'auto';
  t.style.height = Math.min(t.scrollHeight, 120) + 'px';
}

function setInputDisabled(disabled) {
  els.messageInput.disabled = disabled;
  els.sendBtn.disabled = disabled;
}

// ─── UI Helpers ───────────────────────────────────────────────────────────────
function setConnectionStatus(status) {
  els.connectionStatus.className = `status-dot ${status}`;
  els.connectionStatus.title = status === 'ok' ? 'Connected' : 'Connection error';
}

function formatAgentName(name) {
  return name.replace(/_agent$/, '').replace(/_/g, ' ')
    .split(' ').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function markdownLite(text) {
  // Very lightweight markdown: code blocks, inline code, bold, italic, line breaks
  return escapeHtml(text)
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

function showToast(msg) {
  const toast = document.createElement('div');
  toast.className = 'upload-toast';
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
function init() {
  // Pre-fill API key if set
  if (state.apiKey) {
    els.sendBtn.disabled = false;
    loadAgents();
  } else {
    // Show settings modal on first load
    setTimeout(() => els.settingsModal.classList.remove('hidden'), 600);
  }
}

init();
