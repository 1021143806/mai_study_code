// 应用入口 — 导入所有模块，绑定 window 函数，初始化

import { createEditor, switchEditorLang, openFile, closeTab, switchToTab, runCode, saveFile, openFileByName, setRenderSidebarCallback } from './editor.js';
import { loadFileTree, renderSidebar, switchSidebar, addRecentFile, toggleWsRoot } from './sidebar.js';
import { connectSSE, sendChatMsg, clearChat, addAssistantLog } from './chat.js';
import { loadWorkspaces, switchWorkspace, showWsDialog, closeWsDialog, saveWsFromForm, deleteWs, testWsConn } from './workspace.js';
import { toggleConfigVisual, updateConfigField, saveConfigVisual } from './config.js';

// ================================================================
// 暴露给 HTML onclick 的函数
// ================================================================

// 编辑器
window.setEditorLang = switchEditorLang;
window.switchToTab = switchToTab;
window.closeTab = closeTab;
window.openFile = openFile;
window.openFileByName = openFileByName;
window.runCode = runCode;
window.saveFile = saveFile;

// 侧边栏
window.refreshFileTree = loadFileTree;
window.toggleWsRoot = toggleWsRoot;

// 对话
window.sendChatMsg = sendChatMsg;
window.clearChat = clearChat;
window.addAssistantLog = addAssistantLog;

// 工作区
window.switchWorkspace = switchWorkspace;
window.showWsDialog = showWsDialog;
window.closeWsDialog = closeWsDialog;
window.saveWsFromForm = saveWsFromForm;
window.deleteWs = deleteWs;
window.testWsConn = testWsConn;

// 配置可视化
window.toggleConfigVisual = toggleConfigVisual;
window.updateConfigField = updateConfigField;
window.saveConfigVisual = saveConfigVisual;

// 页面切换（监控、我的页面）
window.switchPage = function(name) {
  const isEditor = name === 'editor';
  document.getElementById('editor-panel').style.display = isEditor ? '' : 'none';
  // 取消所有 nav-tab 的 active 状态
  document.querySelectorAll('#nav-tabs .nav-tab').forEach(t => t.classList.remove('active'));
  // 激活对应的页面 tab
  const tab = document.querySelector(`[data-page="${name}"]`);
  if (tab) tab.classList.add('active');
};

// 关于弹窗
window.toggleAbout = function() {
  const ov = document.getElementById('about-overlay');
  if (ov) ov.style.display = ov.style.display === 'none' || !ov.style.display ? '' : 'none';
};

// 重载插件
window.reloadPlugin = async function() {
  const btn = document.getElementById('reload-btn');
  if (!btn) return;
  btn.classList.add('loading');
  btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>';
  try {
    const resp = await fetch('/api/reload', { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg></span>';
      setTimeout(() => { btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>'; btn.classList.remove('loading'); }, 2000);
    } else {
      btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>';
      btn.classList.remove('loading');
      setTimeout(() => { btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>'; }, 3000);
    }
  } catch (e) {
    btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>';
    btn.classList.remove('loading');
    setTimeout(() => { btn.innerHTML = '<span class="sf"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></span>'; }, 3000);
  }
};

// ================================================================
// 活动栏点击处理
// ================================================================

document.getElementById('activitybar').addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn');
  if (!btn) return;
  const name = btn.dataset.sidebar;

  // 齿轮图标：打开插件配置
  if (name === 'config') {
    try {
      const resp = await fetch('/api/plugin-config');
      const data = await resp.json();
      if (data.content !== undefined) {
        openFile('config.toml', data.content);
      }
    } catch (err) {}
    return;
  }

  if (name === window.__activeSidebar && !document.getElementById('sidebar').classList.contains('collapsed')) {
    document.getElementById('sidebar').classList.add('collapsed');
    document.querySelectorAll('#activitybar .btn').forEach(b => b.classList.remove('active'));
  } else {
    switchSidebar(name);
  }
});

// ================================================================
// 聊天输入框自动调整
// ================================================================

document.getElementById('chat-input-box').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// ================================================================
// 键盘快捷键
// ================================================================

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
    e.preventDefault();
    document.getElementById('sidebar').classList.toggle('collapsed');
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'j') {
    e.preventDefault();
    document.getElementById('assistant-panel').classList.toggle('collapsed');
  }
});

// ================================================================
// 共享状态桥接（模块间通信）
// ================================================================

// sidebar 渲染需要知道 editor 的 openTabs 和 activeTab
// sidebar.js 通过 window.__openTabs / window.__activeTab 读取
// editor.js 通过 setRenderSidebarCallback 设置回调

import { openTabs, activeTab } from './editor.js';
window.__openTabs = openTabs;
window.__activeTab = activeTab;

import { activeSidebar } from './sidebar.js';
window.__activeSidebar = activeSidebar;

// 注册 sidebar 渲染回调
setRenderSidebarCallback(() => {
  window.__openTabs = openTabs;
  window.__activeTab = activeTab;
  renderSidebar();
});

// ================================================================
// 时钟
// ================================================================

function updateClock() {
  const el = document.getElementById('status-time');
  if (el) el.textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);

// ================================================================
// 底部日志面板
// ================================================================

window.logToPanel = function(msg, type) {
  const el = document.getElementById('log-content');
  if (!el) return;
  const now = new Date().toLocaleTimeString();
  const div = document.createElement('div');
  div.style.cssText = 'padding:1px 0;border-bottom:1px solid var(--border-subtle)';
  const color = type === 'err' ? 'var(--danger)' : type === 'warn' ? 'var(--warning)' : type === 'ok' ? 'var(--success)' : 'var(--text-secondary)';
  div.innerHTML = `<span style="color:var(--text-muted);margin-right:6px;font-size:10px">[${now}]</span><span style="color:${color}">${msg}</span>`;
  el.appendChild(div);
  // 保留最多 200 条
  while (el.children.length > 200) el.removeChild(el.firstChild);
  el.scrollTop = el.scrollHeight;
};

window.toggleLogPanel = function() {
  const panel = document.getElementById('log-panel');
  const toggle = document.getElementById('log-toggle');
  if (!panel) return;
  const isOpen = panel.style.height !== '0px' && panel.style.height !== '0' && panel.style.height !== '';
  if (isOpen) {
    panel.style.height = '0';
    if (toggle) toggle.textContent = '📋 日志';
  } else {
    panel.style.height = '180px';
    if (toggle) toggle.textContent = '📋 收起';
  }
};

window.clearLogPanel = function() {
  const el = document.getElementById('log-content');
  if (el) el.innerHTML = '';
};

// 重写 addAssistantLog 也输出到底部日志
const _origLog = window.addAssistantLog;
window.addAssistantLog = function(msg, type) {
  if (_origLog) _origLog(msg, type);
  window.logToPanel(msg, type || 'info');
};

// ================================================================
// 初始化
// ================================================================

createEditor();
connectSSE();
updateClock();
// 先加载工作区，再加载文件树（工作区决定目录）
loadWorkspaces().then(() => loadFileTree());
