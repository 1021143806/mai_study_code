// UI 模块 — 不依赖 CodeMirror，作为普通 <script> 加载
// 所有 import/export 已移除，函数直接在同一作用域引用

// ================================================================
// 图标
// ================================================================
const ICONS = {
  folder: '<svg viewBox="0 0 24 24"><path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/><path d="M14 2v6h6"/></svg>',
  python: '<svg viewBox="0 0 24 24"><path d="M12 2c-4 0-5 1.5-5 4v3h5v1H7c-2.5 0-4.5 1.5-4.5 5s1.5 5 4.5 5h2v-4c0-2.5 2-4.5 4.5-4.5h4c2.5 0 4.5-2 4.5-4.5V6c0-2.5-2-4-5-4zm-3 3c.8 0 1.5.7 1.5 1.5S9.8 8 9 8s-1.5-.7-1.5-1.5S8.2 5 9 5z"/><path d="M15 22c4 0 5-1.5 5-4v-3h-5v-1h7c2.5 0 4.5-1.5 4.5-5s-2-5-4.5-5h-2v4c0 2.5-2 4.5-4.5 4.5h-4C8.5 12 6.5 14 6.5 16.5V18c0 2.5 2 4 5 4zm3-3c-.8 0-1.5-.7-1.5-1.5S17.2 16 18 16s1.5.7 1.5 1.5S18.8 19 18 19z"/></svg>',
  markdown: '<svg viewBox="0 0 24 24"><path d="M3 5h18v14H3V5z"/><path d="M8 15V9l3 3 3-3v6"/></svg>',
  brain: '<svg viewBox="0 0 24 24"><path d="M12 4a4 4 0 0 1 4 4c0 1.1-.5 2.1-1.2 2.8.7.5 1.2 1.3 1.2 2.2a3 3 0 0 1-3 3"/><path d="M12 4a4 4 0 0 0-4 4c0 1.1.5 2.1 1.2 2.8-.7.5-1.2 1.3-1.2 2.2a3 3 0 0 0 3 3"/><path d="M8 15a3 3 0 0 0 3 3h2a3 3 0 0 0 3-3"/><path d="M9 10h6"/></svg>',
  shell: '<svg viewBox="0 0 24 24"><polyline points="4 7 10 12 4 17"/><line x1="13" y1="17" x2="20" y2="17"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  tag: '<svg viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
  play: '<svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
  save: '<svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',
  chat: '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  close: '<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  chevron: '<svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>',
  refresh: '<svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
  about: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  folderOpen: '<svg viewBox="0 0 24 24"><path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v2H2V6z"/><path d="M2 10h20l-3 8H5l-3-8z"/></svg>',
  settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
};
function icon(name, cls) { cls = cls || ''; return '<span class="sf ' + cls + '">' + (ICONS[name] || '') + '</span>'; }
function iconFile(name) { if (!name) return icon('file'); if (name.endsWith('.py')) return icon('python'); if (name.endsWith('.md')) return icon('markdown'); return icon('file'); }

// ================================================================
// 全局状态
// ================================================================
let editorView = null;
let activeTab = { path: 'welcome.py', content: '# 欢迎使用麦麦学代码\n# 在此编写 Python 代码，点击 ▶ 运行\n\nprint("你好，守护者！")\n\n', saved: true };
let openTabs = [activeTab];
let currentLang = 'python';
let fileTreeData = [];
let recentFiles = [];
let activeSidebar = 'explorer';
let workspaces = [];
let activeWorkspace = '';
let chatHistory = [];
let sseConn = null;
let isConfigVisual = false;
let configSections = [];
let chatCwd = '';           // 当前相对目录（用户在 workspace 内的子目录）
let chatWsRoot = '';        // 工作区根目录完整路径
window.__activeWorkspace = '';
window.__activeSidebar = activeSidebar;
window.__openTabs = openTabs;
window.__activeTab = activeTab;
window.__isConfigVisual = false;

// 对话模块 — 右侧聊天面板 + SSE 连接

// ================================================================
// 状态
// ================================================================

// ================================================================
// 消息渲染
// ================================================================

function renderMsg(msg, isUser) {
  const div = document.createElement('div');
  div.className = `chat-msg ${isUser ? 'user' : 'assistant'}`;
  const time = new Date().toLocaleTimeString();
  let html = msg;
  if (!isUser) {
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\n/g, '<br>');
  }
  div.innerHTML = `<div class="msg-bubble">${isUser ? html.replace(/\n/g, '<br>') : html}</div><span class="msg-time">${time}</span>`;
  return div;
}

// 工具结果渲染为可视化卡片
function renderToolCard(tr, cwdInfo) {
  var icons = { read_file:'📖', write_file:'✏️', execute_code:'▶', change_dir:'📂', create_dir:'📁', list_dir:'📋' };
  var names = { read_file:'读取文件', write_file:'写入文件', execute_code:'执行代码', change_dir:'切换目录', create_dir:'创建目录', list_dir:'列出目录' };
  var icon = icons[tr.tool] || '🔧';
  var name = names[tr.tool] || tr.tool;
  var div = document.createElement('div');
  div.className = 'tool-card' + (tr.success ? ' tool-card-ok' : ' tool-card-err');

  var input = typeof tr.input === 'string' ? tr.input : JSON.stringify(tr.input);
  var output = typeof tr.output === 'string' ? tr.output : JSON.stringify(tr.output);
  var errMsg = tr.error || '';

  div.innerHTML = [
    '<div class="tool-card-header">' + icon + ' ' + name + '</div>',
    '<div class="tool-card-body">',
      input ? '<div class="tool-card-input">$ ' + escHtml(input) + '</div>' : '',
      output ? '<div class="tool-card-output">' + escHtml(output.substring(0, 1000)) + '</div>' : '',
      errMsg ? '<div class="tool-card-output" style="color:var(--danger)">' + escHtml(errMsg) + '</div>' : '',
    '</div>',
    cwdInfo ? '<div class="tool-card-cwd">📍 ' + escHtml(cwdInfo) + '</div>' : '',
  ].join('');
  return div;
}

function showLoading() {
  hideLoading();
  const div = document.createElement('div');
  div.className = 'chat-msg assistant msg-loading';
  div.id = 'chat-loading';
  div.innerHTML = '<div class="msg-bubble"><span class="dot-anim">●</span><span class="dot-anim">●</span><span class="dot-anim">●</span></div>';
  document.getElementById('chat-messages').appendChild(div);
  scrollChat();
}

function hideLoading() {
  const el = document.getElementById('chat-loading');
  if (el) el.remove();
}

function scrollChat() {
  const el = document.getElementById('chat-messages');
  if (el) el.scrollTop = el.scrollHeight;
}

// ================================================================
// 发送消息
// ================================================================

async function sendChatMsg() {
  const input = document.getElementById('chat-input-box');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  input.style.height = 'auto';

  chatHistory.push({ role: 'user', content: msg });
  const msgEl = renderMsg(msg, true);
  document.getElementById('chat-messages').appendChild(msgEl);
  scrollChat();
  showLoading();

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory, cwd: chatCwd, stream: true })
    });
    hideLoading();

    // 检查响应类型：流式或 JSON
    var ct = resp.headers.get('content-type') || '';
    if (ct.includes('text/event-stream')) {
      // 流式读取
      var fullText = '';
      var replyEl = null;
      var needsRefresh = false;
      var toolResults = [];
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      while (true) {
        var result = await reader.read();
        if (result.done) break;
        buffer += decoder.decode(result.value, { stream: true });
        var lines = buffer.split('\n');
        buffer = lines.pop() || '';
        var currentEvent = '';
        var currentData = '';

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (line.startsWith('event: ')) {
            currentEvent = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            currentData = line.substring(6).trim();
          } else if (line === '' && currentEvent && currentData) {
            if (currentEvent === 'text') {
              fullText += currentData;
              if (!replyEl) {
                replyEl = renderMsg('', false);
                document.getElementById('chat-messages').appendChild(replyEl);
              }
              replyEl.querySelector('.msg-bubble').innerHTML = fullText.replace(/\n/g, '<br>');
              scrollChat();
            } else if (currentEvent === 'tool') {
              try { var tr = JSON.parse(currentData);
                toolResults.push(tr);
                // 立即渲染工具卡片（在文本之前出现）
                var card = renderToolCard(tr, chatCwd || '');
                document.getElementById('chat-messages').appendChild(card);
                scrollChat();
                // 日志栏输出
                var logIcon = {read_file:'📖', write_file:'✏️', execute_code:'▶', change_dir:'📂', create_dir:'📁', list_dir:'📋'};
                var logType = tr.success ? 'ok' : 'err';
                logToPanel((logIcon[tr.tool] || '🔧') + ' ' + (tr.input || '').substring(0, 80) + (tr.success ? ' ✓' : ' ✗'), logType);
                if (tr.tool === 'write_file' || tr.tool === 'create_dir' || tr.tool === 'change_dir') needsRefresh = true;
              } catch (e) {}
            } else if (currentEvent === 'done') {
              try { var meta = JSON.parse(currentData); if (meta.cwd !== undefined) chatCwd = meta.cwd; updateChatPath(); } catch (e) {}
            }
            currentEvent = ''; currentData = '';
          }
        }
      }

      if (fullText) {
        chatHistory.push({ role: 'assistant', content: fullText });
        logToPanel('💬 ' + fullText.substring(0, 120) + (fullText.length > 120 ? '...' : ''), 'info');
      }
      if (needsRefresh && typeof loadFileTree === 'function') loadFileTree();
      scrollChat();
    } else {
      // 非流式回退（旧版 JSON 响应）
      var data = await resp.json();
      if (data.cwd !== undefined) chatCwd = data.cwd;
      if (data.ws_root) chatWsRoot = data.ws_root;
      updateChatPath();

      if (data.success && data.response) {
        chatHistory.push({ role: 'assistant', content: data.response });
        var replyEl = renderMsg(data.response, false);
        document.getElementById('chat-messages').appendChild(replyEl);
        var needsRefresh = false;
        if (data.tool_results) {
          for (var i = 0; i < data.tool_results.length; i++) {
            document.getElementById('chat-messages').appendChild(renderToolCard(data.tool_results[i], chatCwd || ''));
            if (data.tool_results[i].tool === 'write_file' || data.tool_results[i].tool === 'create_dir' || data.tool_results[i].tool === 'change_dir') needsRefresh = true;
          }
        }
        if (needsRefresh && typeof loadFileTree === 'function') loadFileTree();
      } else if (data.tool_results && data.tool_results.length > 0) {
        for (var i = 0; i < data.tool_results.length; i++) {
          document.getElementById('chat-messages').appendChild(renderToolCard(data.tool_results[i], chatCwd || ''));
        }
      } else {
        var errEl = renderMsg('抱歉，我暂时无法回复。' + (data.error ? ' (' + data.error + ')' : ''), false);
        document.getElementById('chat-messages').appendChild(errEl);
      }
      scrollChat();
    }
  } catch (e) {
    hideLoading();
    var errEl = renderMsg('请求失败: ' + e.message, false);
    document.getElementById('chat-messages').appendChild(errEl);
    scrollChat();
  }
}

function clearChat() {
  chatHistory = [];
  document.getElementById('chat-messages').innerHTML = '';
  // 保存清空后的状态
  saveChatHistory();
}

// 加载/保存聊天记录
function loadChatHistory() {
  var wsName = activeWorkspace || 'default';
  fetch('/api/chat/history?workspace=' + encodeURIComponent(wsName))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.messages && data.messages.length > 0) {
        chatHistory = data.messages;
        if (data.cwd !== undefined) chatCwd = data.cwd || '';
        updateChatPath();
        // 渲染历史消息
        var container = document.getElementById('chat-messages');
        if (container) container.innerHTML = '';
        for (var i = 0; i < chatHistory.length; i++) {
          var m = chatHistory[i];
          if (m.role === 'user') {
            container.appendChild(renderMsg(m.content, true));
          } else if (m.role === 'assistant') {
            container.appendChild(renderMsg(m.content, false));
          }
        }
        scrollChat();
      }
    })
    .catch(function() {});
}

function saveChatHistory() {
  // 由后端自动保存，无需前端操作
}

// 更新对话面板中的工作目录显示
function updateChatPath() {
  var el = document.getElementById('chat-cwd');
  if (!el) return;
  var displayPath = chatCwd ? chatCwd : (activeWorkspace || '工作区');
  var fullPath = chatWsRoot ? (chatCwd ? chatWsRoot + '/' + chatCwd : chatWsRoot) : '';
  el.textContent = displayPath;
  el.title = fullPath || displayPath;
  // 头部紧凑路径
  var short = document.getElementById('chat-path');
  if (short) {
    short.textContent = displayPath.split('/').pop() || displayPath;
    short.title = fullPath || displayPath;
  }
}

// ================================================================
// SSE 连接
// ================================================================

function connectSSE() {
  const es = new EventSource('/api/stream');
  sseConn = es;

  es.addEventListener('stats', (e) => {
    try {
      var stats = JSON.parse(e.data);
      var chatDot = document.getElementById('conn-dot-chat');
      var chatStatus = document.getElementById('conn-status-chat');
      if (chatDot) chatDot.style.background = 'var(--success)';
      if (chatStatus) chatStatus.textContent = '已连接';

      // 更新对话面板统计数据
      var ctx = stats.context || {};
      var cache = stats.cache || {};
      var sb = stats.sandbox || {};
      var used = ctx.context_tokens_estimate || 0;
      var max = ctx.context_max_tokens || 8000;
      document.getElementById('st-ctx-used').textContent = used >= 1000 ? (used/1000).toFixed(1)+'K' : used;
      document.getElementById('st-ctx-max').textContent = max >= 1000 ? (max/1000).toFixed(0)+'K' : max;
      document.getElementById('st-cache').textContent = cache.active_entries || 0;
      document.getElementById('st-cache-max').textContent = cache.max_entries || 500;
      var hits = cache.total_hits || 0;
      var active = cache.active_entries || 0;
      if (hits > 0) {
        document.getElementById('st-hit-row').style.display = '';
        document.getElementById('st-hit').textContent = Math.round(hits / Math.max(active, 1));
      }
      document.getElementById('st-exec').textContent = (sb.success || 0) + (sb.failed || 0);
    } catch (err) {}
  });

  es.addEventListener('log', (e) => {
    try {
      const event = JSON.parse(e.data);
      const msg = event.data?.message || '';
      if (msg) {
        window.addAssistantLog('📢 ' + msg);
      }
    } catch (err) {}
  });

  es.onerror = () => {
    const chatDot = document.getElementById('conn-dot-chat');
    const chatStatus = document.getElementById('conn-status-chat');
    if (chatDot) chatDot.style.background = 'var(--danger)';
    if (chatStatus) chatStatus.textContent = '断开';
  };
}

// ================================================================
// 兼容日志（供 editor.js、sidebar.js 使用）
// ================================================================

function addAssistantLog(msg, type) {
  // 输出到右侧对话面板（仅显示错误、警告、保存成功）
  if (type === 'err' || type === 'warn' || (type === 'ok' && msg.includes('保存'))) {
    const msgEl = renderMsg('📎 ' + msg, false);
    document.getElementById('chat-messages').appendChild(msgEl);
    scrollChat();
  }
  // 输出到底部日志面板（所有消息）
  if (window.logToPanel) {
    window.logToPanel(msg, type || 'info');
  }
}
// 侧边栏模块 — 文件树、知识库、Bot 页面

// ================================================================
// 状态
// ================================================================

// ================================================================
// 文件树
// ================================================================

async function loadFileTree() {
  try {
    const ws = window.__activeWorkspace || '';
    const wsParam = ws ? `?workspace=${encodeURIComponent(ws)}` : '';
    const [filesResp, wsResp] = await Promise.all([
      fetch('/api/files' + wsParam),
      fetch(`/api/workspaces/${encodeURIComponent(ws)}`).catch(() => null),
    ]);
    const data = await filesResp.json();
    fileTreeData = data.tree || [];
    const root = document.getElementById('file-tree');
    if (!root) return;
    const wsName = ws || '工作区';
    // 解析工作区路径
    let wsPath = '';
    if (wsResp && wsResp.ok) {
      const wsData = await wsResp.json();
      wsPath = wsData.path || '';
    }
    root.innerHTML = `<div class="tree-item" style="--indent:0" onclick="toggleWsRoot(this)">
      <span class="tree-chevron" style="font-size:9px;width:14px;text-align:center;flex-shrink:0;opacity:0.4">▶</span>
      <span class="tree-icon">${icon('folder')}</span>
      <span>${escHtml(wsName)}</span>
    </div>
    <div id="ws-root-children" style="display:none"></div>
    <div style="padding:2px 20px;font-size:10px;color:var(--text-muted);line-height:1.5">
      ${wsPath ? `📍 ${friendlyPath(wsPath)}` : ''}
    </div>`;
  } catch (e) { document.getElementById('file-tree').innerHTML = '加载失败'; }
}

function friendlyPath(p) {
  // 友好的路径显示
  if (p.includes('MaiBot/plugins/mai_study_code/workspace')) {
    return '插件内部目录 <code style="font-size:10px;background:var(--glass-hover);padding:1px 4px;border-radius:3px">workspace/</code>';
  }
  if (p === '/') return '系统根目录 <code style="font-size:10px;background:var(--glass-hover);padding:1px 4px;border-radius:3px">/</code>';
  return p;
}

function toggleWsRoot(el) {
  const children = document.getElementById('ws-root-children');
  const chevron = el.querySelector('.tree-chevron');
  if (children.style.display !== 'none') {
    children.style.display = 'none';
    if (chevron) chevron.classList.remove('open');
  } else {
    children.style.display = '';
    if (chevron) chevron.classList.add('open');
    if (!children.hasChildNodes() || children.children.length === 0) {
      renderFileTree(fileTreeData, children, 0);
    }
  }
}

function renderFileTree(tree, container, indent) {
  if (!indent) { indent = 0; container.innerHTML = ''; }
  tree.forEach(node => {
    const div = document.createElement('div');
    div.className = 'tree-item';
    div.style.setProperty('--indent', indent);
    const iconHtml = node.is_dir ? icon('folder') : iconFile(node.name);
    const chevron = node.is_dir ? `<span class="tree-chevron">${icon('chevron', 'sf-sm')}</span>` : '';
    div.innerHTML = `${chevron}<span class="tree-icon">${iconHtml}</span><span>${node.name}</span>`;

    if (node.is_dir) {
      const chevronEl = div.querySelector('.tree-chevron');
      const childrenContainer = document.createElement('div');
      childrenContainer.style.display = 'none';
      div.onclick = (e) => {
        if (e.target === chevronEl || (e.target.classList && e.target.classList.contains('tree-chevron'))) {
          const isOpen = childrenContainer.style.display !== 'none';
          childrenContainer.style.display = isOpen ? 'none' : '';
          if (chevronEl) chevronEl.classList.toggle('open', !isOpen);
        } else {
          document.querySelectorAll('.tree-item.selected').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
        }
      };
      renderFileTree(node.children || [], childrenContainer, indent + 1);
      container.appendChild(div);
      container.appendChild(childrenContainer);
    } else {
      div.onclick = async () => {
        document.querySelectorAll('.tree-item.selected').forEach(el => el.classList.remove('selected'));
        div.classList.add('selected');
        try {
          const ws = window.__activeWorkspace || '';
          const wsQ = ws ? `&workspace=${encodeURIComponent(ws)}` : '';
          const resp = await fetch(`/api/file?path=${encodeURIComponent(node.path)}${wsQ}`);
          const data = await resp.json();
          if (data.content !== undefined && window.openFile) {
            window.openFile(node.path, data.content);
            logToPanel('打开: ' + node.path, 'ok');
          }
        } catch (e) { window.addAssistantLog(`读取失败: ${node.path}`, 'warn'); }
      };
      container.appendChild(div);
    }
  });
}

// ================================================================
// 侧边栏渲染（已打开、最近打开）
// ================================================================

function renderSidebar() {
  const openEl = document.getElementById('open-files');
  if (openEl) {
    const tabs = (window.__openTabs || []).filter(t => t.path !== 'welcome.py');
    openEl.innerHTML = tabs.length === 0
      ? '<div class="tree-item" style="--indent:0;color:var(--text-muted)">暂无打开的文件</div>'
      : tabs.map(t => {
          const idx = (window.__openTabs || []).indexOf(t);
          return `<div class="tree-item${t.path === (window.__activeTab || {}).path ? ' selected' : ''}" style="--indent:0" onclick="switchToTab(${idx})"><span class="tree-icon">${iconFile(t.path)}</span>${t.path.split('/').pop()}</div>`;
        }).join('');
  }
  const recentEl = document.getElementById('recent-files');
  if (recentEl) {
    recentEl.innerHTML = recentFiles.length === 0
      ? '<div class="tree-item" style="--indent:0;color:var(--text-muted)">无</div>'
      : recentFiles.slice(0, 10).map(f =>
          `<div class="tree-item" style="--indent:0" onclick="openFileByName('${escHtml(f)}')"><span class="tree-icon">${iconFile(f)}</span>${f.split('/').pop()}</div>`
        ).join('');
  }
}

function addRecentFile(path) {
  recentFiles = [path, ...recentFiles.filter(f => f !== path)];
}

// ================================================================
// 侧边栏切换
// ================================================================

function switchSidebar(name) {
  activeSidebar = name;
  document.querySelectorAll('#activitybar .btn').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.querySelector('[data-sidebar="' + name + '"]');
  if (btn) btn.classList.add('active');
  ['panel-explorer', 'panel-knowledge', 'panel-pages-list'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  var panelMap = { explorer: 'panel-explorer', knowledge: 'panel-knowledge', 'pages-list': 'panel-pages-list' };
  var panel = document.getElementById(panelMap[name]);
  if (panel) panel.style.display = '';
  var titles = { explorer: '资源管理器', knowledge: '知识库', 'pages-list': 'Bot 页面' };
  var titleEl = document.getElementById('sidebar-title');
  if (titleEl) titleEl.textContent = titles[name] || '资源管理器';
  var sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.remove('collapsed');
  logToPanel('侧栏: ' + (titles[name] || name), 'info');
  if (name === 'knowledge') loadKnowledge();
  if (name === 'pages-list') loadPages();
}

// ================================================================
// 知识库 & Bot 页面
// ================================================================

async function loadKnowledge() {
  const el = document.getElementById('knowledge-tree');
  if (!el) return;
  try {
    const resp = await fetch('/api/knowledge');
    const data = await resp.json();
    const total = data.total || data.total_entries || 0;
    const categories = data.categories || 0;
    el.innerHTML = `<div class="tree-item" style="--indent:0"><span class="tree-icon">${icon('book')}</span>总条目: ${total}</div><div class="tree-item" style="--indent:0"><span class="tree-icon">${icon('tag')}</span>分类: ${categories}</div>`;
  } catch (e) { el.innerHTML = '<div class="tree-item">加载失败</div>'; }
}

async function loadPages() {
  const el = document.getElementById('pages-tree');
  if (!el) return;
  try {
    const resp = await fetch('/api/pages');
    const data = await resp.json();
    const pages = data.pages || [];
    el.innerHTML = pages.length === 0
      ? '<div class="tree-item">暂无页面</div>'
      : pages.map(p => `<div class="tree-item" style="--indent:0;cursor:pointer" onclick="window.open('/pages/${p.name}', '_blank')"><span class="tree-icon">${icon('file')}</span>${p.title}</div>`).join('');
  } catch (e) { el.innerHTML = '<div class="tree-item">加载失败</div>'; }
}

// ================================================================
// 工具函数
// ================================================================

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
// 工作区模块 — 顶部标签 + 管理弹窗

// ================================================================
// 状态
// ================================================================
// ================================================================
// 工作区加载与渲染
// ================================================================

async function loadWorkspaces() {
  try {
    const resp = await fetch('/api/workspaces');
    const data = await resp.json();
    workspaces = data.workspaces || [];
    activeWorkspace = data.active || '';
    window.__activeWorkspace = activeWorkspace;
    renderWsTabs();
  } catch (e) {}
}

function renderWsTabs() {
  const container = document.getElementById('nav-tabs');
  if (!container) return;
  // 移除旧的 workspace tab 元素
  container.querySelectorAll('[data-ws]').forEach(el => el.remove());
  // 在第一个固定 tab 前插入工作区 tab
  const firstFixed = container.querySelector('[data-page]');
  workspaces.forEach(ws => {
    const isActive = ws.name === activeWorkspace;
    const div = document.createElement('div');
    div.className = 'nav-tab' + (isActive ? ' active' : '');
    div.dataset.ws = ws.name;
    div.textContent = ws.name;
    div.onclick = () => switchWorkspace(ws.name);
    const userLabel = ws.type === 'ssh'
      ? (ws.username || 'root') + '@' + (ws.host || '?')
      : ws.type === 'local-root' ? 'root' : 'a1';
    div.title = ws.type + ': ' + userLabel;
    container.insertBefore(div, firstFixed);
  });
}


// ================================================================
// 切换工作区
// ================================================================

async function switchWorkspace(name) {
  if (name === activeWorkspace) return;
  try {
    var resp = await fetch('/api/workspaces/' + encodeURIComponent(name) + '/activate', { method: 'POST' });
    var data = await resp.json();
    if (data.success) {
      activeWorkspace = name;
      window.__activeWorkspace = name;
      document.getElementById('editor-panel').style.display = '';
      renderWsTabs();
      loadFileTree();
      logToPanel('切换到工作区: ' + name, 'ok');
      loadChatHistory();
    }
  } catch (e) {}
}

// ================================================================
// 管理弹窗 — 卡片式布局
// ================================================================

function showWsDialog() {
  let ov = document.getElementById('ws-dialog-overlay');
  if (!ov) {
    const div = document.createElement('div');
    div.id = 'ws-dialog-overlay';
    div.className = 'overlay';
    div.onclick = function(e) { if (e.target === this) closeWsDialog(); };
    div.innerHTML = `
      <div class="overlay-box ws-dialog" style="max-width:560px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
          <h2 style="font-size:16px;font-weight:700">工作区管理</h2>
          <button onclick="closeWsDialog()" class="secondary" style="font-size:11px;padding:4px 12px">完成</button>
        </div>
        <div id="ws-list" style="display:flex;flex-direction:column;gap:8px;margin-bottom:12px"></div>

        <!-- 添加工作区 — 折叠卡片 -->
        <details style="background:var(--glass-hover);border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:8px 12px">
          <summary style="font-size:12px;font-weight:600;color:var(--text-secondary);cursor:pointer;user-select:none">+ 添加工作区</summary>
          <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:6px">
            <input id="ws-name" placeholder="名称" style="grid-column:1/3">
            <select id="ws-type">
              <option value="local-sandbox">本地沙箱</option>
              <option value="local-root">本地 Root</option>
              <option value="ssh">SSH 远程</option>
            </select>
            <input id="ws-path" placeholder="路径" value="workspace/">
          </div>
          <div id="ws-ssh-fields" style="display:none;margin-top:6px;grid-template-columns:1fr 1fr;gap:6px">
            <input id="ws-host" placeholder="主机地址">
            <input id="ws-port" placeholder="端口" value="22" type="number">
            <input id="ws-user" placeholder="用户名" value="root">
            <input id="ws-pass" placeholder="密码" type="password">
          </div>
          <button onclick="saveWsFromForm()" style="margin-top:8px;width:100%">添加</button>
        </details>
      </div>`;
    document.body.appendChild(div);

    div.querySelector('#ws-type').onchange = function() {
      const sshFields = document.getElementById('ws-ssh-fields');
      if (sshFields) sshFields.style.display = this.value === 'ssh' ? 'grid' : 'none';
    };
  }
  ov.style.display = 'flex';
  renderWsList();
}

function closeWsDialog() {
  const ov = document.getElementById('ws-dialog-overlay');
  if (ov) ov.style.display = 'none';
}

function renderWsList() {
  const el = document.getElementById('ws-list');
  if (!el) return;
  el.innerHTML = workspaces.map(ws => {
    const isActive = ws.name === activeWorkspace;
    const isSsh = ws.type === 'ssh';
    const userLabel = isSsh ? `${ws.username||'root'}@${ws.host||'?'}` : (ws.type === 'local-root' ? 'root' : 'a1');
    const pathInfo = isSsh ? `${(ws.host||'?')}:${ws.port||22}` : (ws.path || '/');
    const typeIcon = isSsh ? '🌐' : (ws.type === 'local-root' ? '⚡' : '💻');

    return `<div style="background:var(--glass-hover);border:1px solid ${isActive ? 'var(--accent)' : 'var(--border-subtle)'};border-radius:var(--radius-md);padding:12px 14px;display:flex;align-items:center;gap:12px;transition:all 0.2s">
      <div style="font-size:22px;width:36px;text-align:center;flex-shrink:0">${typeIcon}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:6px">
          <strong style="font-size:13px">${escHtml(ws.name)}</strong>
          <span style="font-size:10px;background:var(--glass-active);padding:1px 6px;border-radius:4px;color:var(--text-muted)">${ws.type === 'local-sandbox' ? '沙箱' : ws.type === 'local-root' ? 'Root' : 'SSH'}</span>
          ${isActive ? '<span style="font-size:10px;color:var(--success)">● 当前</span>' : ''}
        </div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${escHtml(pathInfo)} · ${escHtml(userLabel)}</div>
      </div>
      <div style="display:flex;gap:4px;flex-shrink:0">
        ${!isActive ? `<button class="secondary" style="font-size:10px;padding:3px 10px" onclick="switchWorkspace('${escHtml(ws.name)}')">切换</button>` : ''}
        <button class="secondary" style="font-size:10px;padding:3px 8px" onclick="editWs('${escHtml(ws.name)}')">编辑</button>
        <button class="secondary" style="font-size:10px;padding:3px 8px" onclick="testWsConn('${escHtml(ws.name)}', this)" title="测试连接">测试</button>
        <button class="danger" style="font-size:10px;padding:3px 8px" onclick="deleteWs('${escHtml(ws.name)}')">删除</button>
      </div>
    </div>`;
  }).join('');
}

// ================================================================
// CRUD
// ================================================================

async function testWsConn(name, btn) {
  const orig = btn.textContent;
  btn.textContent = '⏳';
  btn.disabled = true;
  logToPanel('测试连接: ' + name, 'info');
  try {
    const resp = await fetch(`/api/workspaces/${encodeURIComponent(name)}/test`, { method: 'POST' });
    const data = await resp.json();
    btn.textContent = data.success ? '✅' : '❌';
    logToPanel(data.success ? '连接成功: ' + name : '连接失败: ' + name, data.success ? 'ok' : 'err');
    setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
  } catch (e) {
    btn.textContent = '❌';
    logToPanel('连接测试异常: ' + name, 'err');
    setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
  }
}

function editWs(name) {
  // 找到工作区数据
  var ws = null;
  for (var i = 0; i < workspaces.length; i++) {
    if (workspaces[i].name === name) { ws = workspaces[i]; break; }
  }
  if (!ws) return;
  // 展开添加表单并填充数据
  var details = document.querySelector('#ws-dialog-overlay details');
  if (details) details.open = true;
  var nameInput = document.getElementById('ws-name');
  var typeSelect = document.getElementById('ws-type');
  var pathInput = document.getElementById('ws-path');
  var hostInput = document.getElementById('ws-host');
  var portInput = document.getElementById('ws-port');
  var userInput = document.getElementById('ws-user');
  
  if (nameInput) nameInput.value = ws.name;
  if (typeSelect) typeSelect.value = ws.type;
  if (pathInput) pathInput.value = ws.path || '';
  if (hostInput) hostInput.value = ws.host || '';
  if (portInput) portInput.value = ws.port || 22;
  if (userInput) userInput.value = ws.username || 'root';
  
  // 显示 SSH 字段
  var sshFields = document.getElementById('ws-ssh-fields');
  if (sshFields) sshFields.style.display = ws.type === 'ssh' ? 'grid' : 'none';
  
  logToPanel('编辑工作区: ' + name, 'info');
}

async function saveWsFromForm() {
  const name = document.getElementById('ws-name').value.trim();
  const type = document.getElementById('ws-type').value;
  if (!name) return;
  const config = { name, type };
  if (type === 'local-sandbox' || type === 'local-root') {
    config.path = document.getElementById('ws-path').value.trim() || 'workspace/';
    if (type === 'local-root') config.password = document.getElementById('ws-pass').value || '';
  } else {
    config.host = document.getElementById('ws-host').value.trim();
    config.port = parseInt(document.getElementById('ws-port').value) || 22;
    config.username = document.getElementById('ws-user').value.trim() || 'root';
    config.password = document.getElementById('ws-pass').value || '';
    config.path = document.getElementById('ws-path').value.trim() || '/root';
  }
  try {
    const resp = await fetch('/api/workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    const data = await resp.json();
    if (data.success) {
      await loadWorkspaces();
      renderWsList();
      document.getElementById('ws-name').value = '';
      logToPanel('工作区已保存: ' + name, 'ok');
    } else {
      logToPanel('工作区保存失败: ' + (data.message || ''), 'err');
    }
  } catch (e) {}
}

async function deleteWs(name) {
  if (!confirm(`删除工作区「${name}」？`)) return;
  try {
    const resp = await fetch(`/api/workspaces/${encodeURIComponent(name)}`, { method: 'DELETE' });
    const data = await resp.json();
    if (data.success) {
      const wasActive = activeWorkspace === name;
      await loadWorkspaces();
      if (wasActive) {
        renderWsTabs();
      }
      loadFileTree();
      if (document.getElementById('ws-list')) renderWsList();
      logToPanel('工作区已删除: ' + name, 'ok');
    } else {
      logToPanel('删除失败: ' + name, 'err');
    }
  } catch (e) {}
}

// ================================================================
// 编辑器桩函数（当 CodeMirror 未加载时使用）
// ================================================================
window.setEditorLang = function(lang) {
  currentLang = lang;
  var el = document.getElementById('editor-lang');
  if (el) el.value = lang;
  document.getElementById('status-lang').textContent = lang;
};
window.switchToTab = function(index) {
  if (!openTabs[index]) return;
  if (window.editorView && !activeTab.saved) activeTab.content = window.editorView.state.doc.toString();
  activeTab = openTabs[index];
  if (window.editorView) window.editorView.dispatch({ changes: { from: 0, to: window.editorView.state.doc.length, insert: activeTab.content } });
  renderWsTabs();
  var p = activeTab.path;
  if (p.endsWith('.py')) window.setEditorLang('python');
  else if (p.endsWith('.md')) window.setEditorLang('markdown');
  else if (p.endsWith('.json')) window.setEditorLang('json');
  else window.setEditorLang('text');
};
window.closeTab = function(index) {
  if (openTabs.length <= 1) return;
  var wasActive = openTabs[index].path === activeTab.path;
  openTabs.splice(index, 1);
  if (wasActive) {
    activeTab = openTabs[Math.min(index, openTabs.length - 1)];
    if (window.editorView) window.editorView.dispatch({ changes: { from: 0, to: window.editorView.state.doc.length, insert: activeTab.content } });
  }
};
window.openFile = function(path, content) {
  var existing = openTabs.find(function(t) { return t.path === path; });
  if (existing) { activeTab = existing; window.switchToTab(openTabs.indexOf(existing)); return; }
  openTabs.push({ path: path, content: content, saved: true });
  activeTab = openTabs[openTabs.length - 1];
  if (window.editorView) window.editorView.dispatch({ changes: { from: 0, to: window.editorView.state.doc.length, insert: content } });
  recentFiles = [path].concat(recentFiles.filter(function(f) { return f !== path; }));
  renderSidebar();
};
window.openFileByName = function(path) {
  var wsQ = activeWorkspace ? '&workspace=' + encodeURIComponent(activeWorkspace) : '';
  fetch('/api/file?path=' + encodeURIComponent(path) + wsQ)
    .then(function(r) { return r.json(); })
    .then(function(data) { if (data.content !== undefined) window.openFile(path, data.content); })
    .catch(function() {});
};
window.runCode = async function() {
  if (!window.editorView) { logToPanel('编辑器尚未加载', 'warn'); return; }
  var code = window.editorView.state.doc.toString();
  if (!code.trim()) { logToPanel('代码为空', 'warn'); return; }
  logToPanel('执行: ' + code.split('\n')[0].substring(0, 60) + '...', 'info');
  var out = document.getElementById('editor-output');
  if (!out) return;
  out.style.display = 'block'; out.className = ''; out.textContent = '执行中...';
  try {
    var resp = await fetch('/api/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: code }) });
    var data = await resp.json();
    if (data.success) { out.textContent = data.stdout || '(无输出)'; logToPanel('执行成功 ' + data.execution_time_ms + 'ms', 'ok'); }
    else { out.textContent = data.stderr || data.error || '未知错误'; out.className = 'err'; logToPanel('执行失败', 'err'); }
  } catch (e) { out.textContent = '请求失败: ' + e.message; out.className = 'err'; logToPanel('请求失败: ' + e.message, 'err'); }
};
window.saveFile = async function() {
  if (!window.editorView) return;
  activeTab.content = window.editorView.state.doc.toString();
  try {
    var body = { path: activeTab.path, content: activeTab.content };
    if (activeWorkspace) body.workspace = activeWorkspace;
    var resp = await fetch('/api/file/write', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    var data = await resp.json();
    if (data.success !== false && !data.error) { activeTab.saved = true; logToPanel('已保存: ' + activeTab.path, 'ok'); }
    else { logToPanel('保存失败: ' + (data.error || '未知错误'), 'err'); }
  } catch (e) { logToPanel('保存异常: ' + e.message, 'err'); }
};

// ================================================================
// 暴露给 HTML onclick 的函数
// ================================================================
window.refreshFileTree = loadFileTree;
window.toggleWsRoot = toggleWsRoot;
window.sendChatMsg = sendChatMsg;
window.clearChat = clearChat;
window.addAssistantLog = addAssistantLog;
window.switchWorkspace = switchWorkspace;
window.showWsDialog = showWsDialog;
window.closeWsDialog = closeWsDialog;
window.saveWsFromForm = saveWsFromForm;
window.deleteWs = deleteWs;
window.testWsConn = testWsConn;
window.editWs = editWs;
window.toggleConfigVisual = function() { logToPanel('配置编辑器仅在编辑器模块加载后可用', 'info'); };
window.updateConfigField = function() {};
window.saveConfigVisual = function() {};

// 页面切换
window.switchPage = function(name) {
  var panel = document.getElementById('editor-panel');
  if (panel) panel.style.display = name === 'editor' ? '' : 'none';
  document.querySelectorAll('#nav-tabs .nav-tab').forEach(function(t) { t.classList.remove('active'); });
  var tab = document.querySelector('[data-page="' + name + '"]');
  if (tab) tab.classList.add('active');
};

// 关于弹窗
window.toggleAbout = function() {
  var ov = document.getElementById('about-overlay');
  if (ov) ov.style.display = ov.style.display === 'none' || !ov.style.display ? '' : 'none';
};

// 重载插件
window.reloadPlugin = async function() {
  var btn = document.getElementById('reload-btn');
  if (!btn) return;
  btn.classList.add('loading');
  btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>';
  try {
    var resp = await fetch('/api/reload', { method: 'POST' });
    var data = await resp.json();
    if (data.success) {
      btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg></span>';
      setTimeout(function() { btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>'; btn.classList.remove('loading'); }, 2000);
    } else {
      btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>';
      btn.classList.remove('loading');
      setTimeout(function() { btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>'; }, 3000);
    }
  } catch (e) {
    btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>';
    btn.classList.remove('loading');
    setTimeout(function() { btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>'; }, 3000);
  }
};

// ================================================================
// 活动栏点击
// ================================================================
document.getElementById('activitybar').addEventListener('click', async function(e) {
  var btn = e.target.closest('.btn');
  if (!btn) return;
  var name = btn.dataset.sidebar;
  if (name === 'config') {
    try {
      var resp = await fetch('/api/plugin-config');
      var data = await resp.json();
      if (data.content !== undefined && window.openFile) window.openFile('config.toml', data.content);
    } catch (err) {}
    return;
  }
  if (name === activeSidebar && !document.getElementById('sidebar').classList.contains('collapsed')) {
    document.getElementById('sidebar').classList.add('collapsed');
    document.querySelectorAll('#activitybar .btn').forEach(function(b) { b.classList.remove('active'); });
  } else {
    switchSidebar(name);
  }
});

// ================================================================
// 聊天输入框自动调整
// ================================================================
var chatInput = document.getElementById('chat-input-box');
if (chatInput) {
  chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  });
}

// ================================================================
// 底部日志面板 - 垂直拖拽
// ================================================================
(function() {
  var handle = document.querySelector('#log-panel .resize-handle');
  if (!handle) return;
  var panel = document.getElementById('log-panel');
  var dragging = false, startY, startH;
  handle.addEventListener('mousedown', function(e) {
    dragging = true; startY = e.clientY; startH = panel.offsetHeight;
    handle.classList.add('dragging');
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    var newH = Math.max(40, Math.min(500, startH + (startY - e.clientY)));
    panel.style.height = newH + 'px';
  });
  document.addEventListener('mouseup', function() {
    if (!dragging) return;
    dragging = false; handle.classList.remove('dragging');
    document.body.style.cursor = ''; document.body.style.userSelect = '';
  });
})();

// ================================================================
// 键盘快捷键
// ================================================================
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') { e.preventDefault(); var s = document.getElementById('sidebar'); if (s) s.classList.toggle('collapsed'); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'j') { e.preventDefault(); var p = document.getElementById('assistant-panel'); if (p) p.classList.toggle('collapsed'); }
});

// ================================================================
// 底部日志面板控制
// ================================================================
window.logToPanel = function(msg, type) {
  var el = document.getElementById('log-content');
  if (!el) return;
  var now = new Date().toLocaleTimeString();
  var div = document.createElement('div');
  div.style.cssText = 'padding:1px 0;border-bottom:1px solid var(--border-subtle)';
  var color = type === 'err' ? 'var(--danger)' : type === 'warn' ? 'var(--warning)' : type === 'ok' ? 'var(--success)' : 'var(--text-secondary)';
  div.innerHTML = '<span style="color:var(--text-muted);margin-right:6px;font-size:10px">[' + now + ']</span><span style="color:' + color + '">' + msg + '</span>';
  el.appendChild(div);
  while (el.children.length > 500) el.removeChild(el.firstChild);
  el.scrollTop = el.scrollHeight;
  var count = document.getElementById('log-count');
  if (count) count.textContent = el.children.length + ' 条';
};
window.clearLogPanel = function() {
  var el = document.getElementById('log-content');
  if (el) { el.innerHTML = ''; var c = document.getElementById('log-count'); if (c) c.textContent = '0 条'; }
};

// ================================================================
// 时钟
// ================================================================
function updateClock() { var el = document.getElementById('status-time'); if (el) el.textContent = new Date().toLocaleTimeString(); }
setInterval(updateClock, 1000);

// ================================================================
// 初始化
// ================================================================
connectSSE();
updateClock();
loadWorkspaces().then(function() { loadFileTree(); });
loadChatHistory();

// 加载权限等级并获取工作目录
fetch('/api/level').then(function(r) { return r.json(); }).then(function(data) {
  var badge = document.getElementById('level-badge');
  if (badge) badge.textContent = data.name || data.level || '';
}).catch(function() {});

// 加载工作区路径
fetch('/api/workspaces').then(function(r) { return r.json(); }).then(function(data) {
  var active = data.active || '';
  for (var i = 0; i < data.workspaces.length; i++) {
    if (data.workspaces[i].name === active && data.workspaces[i].path) {
      chatWsRoot = data.workspaces[i].path;
      chatCwd = '';
      updateChatPath();
      break;
    }
  }
}).catch(function() {});

logToPanel('UI 已加载' + (typeof createEditor !== 'undefined' ? '，等待编辑器就绪' : ''), 'ok');
