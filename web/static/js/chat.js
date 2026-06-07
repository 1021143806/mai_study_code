// 对话模块 — 右侧聊天面板 + SSE 连接

// ================================================================
// 状态
// ================================================================
export let chatHistory = [];
export let sseConn = null;

// ================================================================
// 消息渲染
// ================================================================

export function renderMsg(msg, isUser) {
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

export async function sendChatMsg() {
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
      body: JSON.stringify({ messages: chatHistory })
    });
    const data = await resp.json();
    hideLoading();

    if (data.success && data.response) {
      chatHistory.push({ role: 'assistant', content: data.response });
      const replyEl = renderMsg(data.response, false);
      document.getElementById('chat-messages').appendChild(replyEl);
    } else {
      const errEl = renderMsg('抱歉，我暂时无法回复。' + (data.error ? ' (' + data.error + ')' : ''), false);
      document.getElementById('chat-messages').appendChild(errEl);
    }
    scrollChat();
  } catch (e) {
    hideLoading();
    const errEl = renderMsg('请求失败: ' + e.message, false);
    document.getElementById('chat-messages').appendChild(errEl);
    scrollChat();
  }
}

export function clearChat() {
  chatHistory = [];
  document.getElementById('chat-messages').innerHTML = '';
}

// ================================================================
// SSE 连接
// ================================================================

export function connectSSE() {
  const es = new EventSource('/api/stream');
  sseConn = es;

  es.addEventListener('stats', (e) => {
    try {
      const stats = JSON.parse(e.data);
      const chatDot = document.getElementById('conn-dot-chat');
      const chatStatus = document.getElementById('conn-status-chat');
      if (chatDot) chatDot.style.background = 'var(--success)';
      if (chatStatus) chatStatus.textContent = '已连接';

      // 从 stats 同步 token 数据
      if (stats.context) {
        const usedEl = document.getElementById('st-ctx-used');
        const maxEl = document.getElementById('st-ctx-max');
        if (usedEl) usedEl.textContent = stats.context.context_tokens_estimate || 0;
        // 同步 context_max_tokens 到 token 仪表盘
        if (stats.context.context_max_tokens && window.updateContextMax) {
          window.updateContextMax(stats.context.context_max_tokens);
        }
      }
      const execEl = document.getElementById('st-exec');
      if (execEl && stats.sandbox) execEl.textContent = stats.sandbox.total || 0;
      const cacheEl = document.getElementById('st-cache');
      if (cacheEl && stats.cache) cacheEl.textContent = stats.cache.active_entries || 0;
      const hitEl = document.getElementById('st-hit');
      if (hitEl && stats.cache) hitEl.textContent = stats.cache.total_hits || 0;
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

  es.addEventListener('token_bar', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (window.onTokenBarEvent) {
        window.onTokenBarEvent(data);
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

export function addAssistantLog(msg, type) {
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
