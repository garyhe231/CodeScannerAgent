/* Code Scanner Agent — frontend */

// Load local repos into the dropdown on page load
async function loadLocalRepos() {
  try {
    const res = await fetch('/repos');
    const data = await res.json();
    const select = document.getElementById('repoSelect');
    data.repos.forEach(repo => {
      const opt = document.createElement('option');
      opt.value = repo.path;
      opt.textContent = repo.name;
      select.appendChild(opt);
    });
    // Pre-select if current session matches a known repo
    const currentPath = document.getElementById('repoPath').value;
    if (currentPath) {
      for (const opt of select.options) {
        if (opt.value === currentPath) { select.value = currentPath; break; }
      }
    }
  } catch (e) {
    console.warn('Could not load local repos:', e);
  }
}

function onRepoSelect() {
  const select = document.getElementById('repoSelect');
  if (select.value) {
    document.getElementById('repoPath').value = select.value;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadLocalRepos();
  document.getElementById('repoPath').addEventListener('input', () => {
    const select = document.getElementById('repoSelect');
    const typed = document.getElementById('repoPath').value;
    if (select.value && select.value !== typed) select.value = '';
  });
});

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

// Attachment state: array of processed file objects from /upload
let pendingAttachments = [];

async function handleFileAttach(event) {
  const files = Array.from(event.target.files);
  if (!files.length) return;

  const bar = document.getElementById('attachmentBar');
  bar.style.display = 'flex';

  for (const file of files) {
    // Show uploading chip
    const chipId = 'chip-' + Date.now() + '-' + Math.random().toString(36).slice(2);
    const chip = document.createElement('div');
    chip.className = 'attach-chip loading';
    chip.id = chipId;
    chip.innerHTML = `<span class="spinner"></span> ${escHtml(file.name)}`;
    bar.appendChild(chip);

    try {
      const fd = new FormData();
      fd.append('files', file);
      const res = await fetch('/upload', { method: 'POST', body: fd });
      const data = await res.json();
      const result = data.files[0];

      chip.classList.remove('loading');
      if (result.error) {
        chip.classList.add('error');
        chip.innerHTML = `&#10060; ${escHtml(file.name)} <span class="chip-remove" onclick="removeAttachment('${chipId}')">&#10005;</span>`;
      } else {
        chip.classList.add('ready');
        const icon = result.type === 'image' ? '&#128444;' : '&#128196;';
        chip.innerHTML = `${icon} ${escHtml(file.name)} <span class="chip-remove" onclick="removeAttachment('${chipId}')">&#10005;</span>`;
        pendingAttachments.push({ chipId, ...result });
      }
    } catch (e) {
      chip.classList.remove('loading');
      chip.classList.add('error');
      chip.innerHTML = `&#10060; ${escHtml(file.name)} <span class="chip-remove" onclick="removeAttachment('${chipId}')">&#10005;</span>`;
    }
  }
  // Reset file input so same file can be re-attached
  event.target.value = '';
}

function removeAttachment(chipId) {
  pendingAttachments = pendingAttachments.filter(a => a.chipId !== chipId);
  const chip = document.getElementById(chipId);
  if (chip) chip.remove();
  if (!pendingAttachments.length) {
    const bar = document.getElementById('attachmentBar');
    if (!bar.children.length) bar.style.display = 'none';
  }
}

async function askQuestion() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();
  if (!question && !pendingAttachments.length) return;

  const attachments = [...pendingAttachments];
  pendingAttachments = [];
  document.getElementById('attachmentBar').innerHTML = '';
  document.getElementById('attachmentBar').style.display = 'none';

  input.value = '';
  input.style.height = 'auto';

  appendUserMsg(question, attachments);
  const thinking = appendThinking();
  setStatus('asking');

  try {
    const fd = new FormData();
    fd.append('question', question || '(see attached files)');
    fd.append('attachments', JSON.stringify(attachments.map(a => ({
      filename: a.filename,
      type: a.type,
      content: a.content || null,
      image_data: a.image_data || null,
      media_type: a.media_type || null,
      error: a.error || null,
    }))));
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

function appendUserMsg(text, attachments) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  let attachHtml = '';
  if (attachments && attachments.length) {
    attachHtml = '<div class="msg-attachments">' +
      attachments.map(a => {
        const icon = a.type === 'image' ? '&#128444;' : '&#128196;';
        return `<span class="msg-attach-chip">${icon} ${escHtml(a.filename)}</span>`;
      }).join('') +
      '</div>';
  }
  el.innerHTML = `
    <div class="msg-label">You</div>
    ${attachHtml}
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
  document.getElementById('repoSelect').value = '';
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
  loadLocalRepos();
  document.getElementById('repoPath').addEventListener('input', () => {
    const select = document.getElementById('repoSelect');
    const typed = document.getElementById('repoPath').value;
    if (select.value && select.value !== typed) select.value = '';
  });
});
