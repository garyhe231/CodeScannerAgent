/* Code Scanner Agent — frontend */

marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
  gfm: true,
});

function renderMd(text) {
  return marked.parse(text || '');
}

function setStatus(state) {
  const badge = document.getElementById('statusBadge');
  const map = {
    idle:    { cls: 'badge-idle',    label: 'Idle' },
    loading: { cls: 'badge-loading', label: 'Scanning...' },
    ready:   { cls: 'badge-ready',   label: 'Ready' },
    asking:  { cls: 'badge-loading', label: 'Thinking...' },
    error:   { cls: 'badge-error',   label: 'Error' },
  };
  const s = map[state] || map.idle;
  badge.className = 'badge ' + s.cls;
  badge.textContent = s.label;
}

async function scanRepo() {
  const path = document.getElementById('repoPath').value.trim();
  if (!path) { alert('Please enter a repository path.'); return; }

  const btn = document.getElementById('scanBtn');
  const btnText = document.getElementById('scanBtnText');
  btn.disabled = true;
  btnText.innerHTML = '<span class="spinner"></span> Scanning...';
  setStatus('loading');

  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('summaryPanel').style.display = 'none';
  document.getElementById('chatSection').style.display = 'none';
  document.getElementById('treeSection').style.display = 'none';

  try {
    const fd = new FormData();
    fd.append('repo_path', path);
    const res = await fetch('/scan', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok) {
      setStatus('error');
      alert('Error: ' + (data.detail || 'Unknown error'));
      return;
    }

    showSession(data.file_count, data.file_tree, path, data.summary);
    setStatus('ready');
  } catch (e) {
    setStatus('error');
    alert('Request failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Scan Repository';
  }
}

function showSession(fileCount, fileTree, repoPath, summary) {
  document.getElementById('repoLabel').textContent = repoPath;
  document.getElementById('fileCount').textContent = fileCount;
  document.getElementById('fileTree').textContent = fileTree;
  document.getElementById('treeSection').style.display = 'flex';
  document.getElementById('treeSection').style.flexDirection = 'column';

  if (summary) {
    document.getElementById('summaryContent').innerHTML = renderMd(summary);
    document.getElementById('summaryPanel').style.display = 'block';
    // Re-run hljs on the freshly inserted code blocks
    document.querySelectorAll('#summaryContent pre code').forEach(el => hljs.highlightElement(el));
  }

  document.getElementById('chatSection').style.display = 'flex';
  document.getElementById('emptyState').style.display = 'none';
}

function restoreSession(fileCount, fileTree, repoPath, summary) {
  showSession(fileCount, fileTree, repoPath, summary);
  setStatus('ready');
}

async function askQuestion() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  input.style.height = 'auto';

  appendUserMsg(question);
  const thinking = appendThinking();
  setStatus('asking');

  try {
    const fd = new FormData();
    fd.append('question', question);
    const res = await fetch('/ask', { method: 'POST', body: fd });
    const data = await res.json();

    thinking.remove();

    if (!res.ok) {
      appendAssistantMsg('**Error:** ' + (data.detail || 'Unknown error'));
      setStatus('error');
    } else {
      appendAssistantMsg(data.answer);
      setStatus('ready');
    }
  } catch (e) {
    thinking.remove();
    appendAssistantMsg('**Request failed:** ' + e.message);
    setStatus('error');
  }
}

function appendUserMsg(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  el.innerHTML = `
    <div class="msg-label">You</div>
    <div class="msg-bubble">${escHtml(text)}</div>
  `;
  getChatMessages().appendChild(el);
  scrollChat();
}

function appendAssistantMsg(markdown) {
  const el = document.createElement('div');
  el.className = 'msg msg-assistant';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble markdown-body';
  bubble.innerHTML = renderMd(markdown);
  bubble.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = 'Agent';

  el.appendChild(label);
  el.appendChild(bubble);
  getChatMessages().appendChild(el);
  scrollChat();
}

function appendThinking() {
  const el = document.createElement('div');
  el.className = 'msg msg-assistant';
  el.innerHTML = `
    <div class="msg-label">Agent</div>
    <div class="thinking">
      <div class="dot"></div><div class="dot"></div><div class="dot"></div>
      Thinking...
    </div>
  `;
  getChatMessages().appendChild(el);
  scrollChat();
  return el;
}

function getChatMessages() {
  return document.getElementById('chatMessages');
}

function scrollChat() {
  const el = getChatMessages();
  el.scrollTop = el.scrollHeight;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function clearSession() {
  await fetch('/clear', { method: 'POST' });
  document.getElementById('repoPath').value = '';
  document.getElementById('repoLabel').textContent = 'No repository loaded';
  document.getElementById('summaryPanel').style.display = 'none';
  document.getElementById('chatSection').style.display = 'none';
  document.getElementById('treeSection').style.display = 'none';
  document.getElementById('chatMessages').innerHTML = '';
  document.getElementById('emptyState').style.display = 'flex';
  setStatus('idle');
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    askQuestion();
  }
}

// Auto-resize textarea
document.addEventListener('DOMContentLoaded', () => {
  const ta = document.getElementById('questionInput');
  if (ta) {
    ta.addEventListener('input', () => {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    });
  }
});
