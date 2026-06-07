// 编辑器模块 — Monaco Editor
// Monaco 通过 AMD require 加载，在 editor-bootstrap.js 中进行初始化
// 本模块提供编辑器状态管理、标签页、文件操作等 UI 逻辑

import { iconFile } from './icons.js';

// ================================================================
// 状态
// ================================================================
export let activeTab = { path: 'welcome.py', content: '# 欢迎使用麦麦学代码\n# 在此编写 Python 代码，点击 ▶ 运行\n\nprint("你好，守护者！")\n\n', saved: true };
export let openTabs = [activeTab];
export let currentLang = 'python';

export let renderSidebarCallback = null;

export function setRenderSidebarCallback(fn) {
  renderSidebarCallback = fn;
}

// ================================================================
// Monaco 编辑器实例管理
// ================================================================

let monacoEditor = null;
let monacoReady = false;
let pendingContent = null;  // 编辑器就绪前暂存的内容

export function onMonacoReady(editor) {
  monacoEditor = editor;
  monacoReady = true;
  if (pendingContent !== null) {
    editor.setValue(pendingContent);
    pendingContent = null;
  }
  updateTabs();
  updateStatusBar();
}

export function getEditor() {
  return monacoEditor;
}

function getContent() {
  if (!monacoEditor) return activeTab.content;
  return monacoEditor.getValue();
}

function setContent(text) {
  if (!monacoReady || !monacoEditor) {
    pendingContent = text;
    return;
  }
  const model = monacoEditor.getModel();
  if (model) {
    model.setValue(text);
  }
}

function getSelection() {
  if (!monacoEditor) return { line: 1, col: 1 };
  const pos = monacoEditor.getPosition();
  return { line: pos.lineNumber, col: pos.column };
}

// ================================================================
// 语言支持
// ================================================================

const EXT_TO_LANG = {
  '.py': 'python',
  '.md': 'markdown',
  '.json': 'json',
  '.toml': 'plaintext',
  '.txt': 'plaintext',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.js': 'javascript',
  '.ts': 'typescript',
  '.jsx': 'javascript',
  '.tsx': 'typescript',
  '.css': 'css',
  '.html': 'html',
  '.sh': 'shell',
  '.bash': 'shell',
  '.sql': 'sql',
  '.java': 'java',
  '.cpp': 'cpp',
  '.c': 'c',
  '.h': 'c',
  '.go': 'go',
  '.rs': 'rust',
  '.rb': 'ruby',
  '.php': 'php',
};

function detectLang(path) {
  for (const [ext, lang] of Object.entries(EXT_TO_LANG)) {
    if (path.endsWith(ext)) return lang;
  }
  return 'plaintext';
}

// ================================================================
// 标签页
// ================================================================

function updateTabs() {
  const el = document.getElementById('editor-tabs');
  if (!el) return;
  el.innerHTML = openTabs.map((t, i) =>
    `<div class="editor-tab${t.path === activeTab.path ? ' active' : ''}" onclick="window.switchToTab(${i})">
      <span>${t.saved ? '' : '● '}${t.path.split('/').pop()}</span>
      <span class="close" onclick="event.stopPropagation();window.closeTab(${i})">&times;</span>
    </div>`
  ).join('');
  if (renderSidebarCallback) renderSidebarCallback();
}

function updateStatusBar() {
  const sel = getSelection();
  document.getElementById('status-ln').textContent = sel.line;
  document.getElementById('status-col').textContent = sel.col;
  document.getElementById('status-lang').textContent = currentLang.charAt(0).toUpperCase() + currentLang.slice(1);
}

export function openFile(path, content) {
  const existing = openTabs.find(t => t.path === path);
  if (existing) {
    activeTab = existing;
    switchToTab(openTabs.indexOf(existing));
    // 仍然添加 recent
    addRecentFile(path);
    return;
  }
  openTabs.push({ path, content, saved: true });
  activeTab = openTabs[openTabs.length - 1];
  if (monacoEditor) {
    setContent(content);
    switchEditorLang(detectLang(path));
  }
  addRecentFile(path);
  // 可视化按钮：仅 config.toml 显示
  const vizBtn = document.getElementById('config-viz-btn');
  if (vizBtn) {
    vizBtn.style.display = path === 'config.toml' ? '' : 'none';
    if (path !== 'config.toml' && window.__isConfigVisual) window.toggleConfigVisual();
  }
  updateTabs();
}

/** 添加文件到最近打开列表（更新 sidebar） */
function addRecentFile(path) {
  // 通过 window 调用 sidebar 的 addRecentFile
  if (window.__addRecentFile) {
    window.__addRecentFile(path);
  }
}

export function closeTab(index) {
  if (openTabs.length <= 1) return;
  const wasActive = openTabs[index].path === activeTab.path;
  openTabs.splice(index, 1);
  if (wasActive) {
    activeTab = openTabs[Math.min(index, openTabs.length - 1)];
    setContent(activeTab.content);
    switchEditorLang(detectLang(activeTab.path));
  }
  updateTabs();
}

export function switchToTab(index) {
  if (activeTab.path === openTabs[index].path) return;
  // 保存当前内容
  if (monacoEditor && !activeTab.saved) {
    activeTab.content = getContent();
  }
  activeTab = openTabs[index];
  setContent(activeTab.content);
  switchEditorLang(detectLang(activeTab.path));
  updateTabs();
}

// ================================================================
// 语言切换
// ================================================================

export function switchEditorLang(lang) {
  currentLang = lang;
  const langEl = document.getElementById('editor-lang');
  if (langEl) langEl.value = lang;
  document.getElementById('status-lang').textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
  if (!monacoEditor || !window.monaco) return;
  const model = monacoEditor.getModel();
  if (model) {
    window.monaco.editor.setModelLanguage(model, lang);
  }
}

// ================================================================
// 代码执行
// ================================================================

export async function runCode() {
  if (!monacoEditor) return;
  const code = getContent();
  if (!code.trim()) { window.addAssistantLog('代码为空', 'warn'); return; }
  window.addAssistantLog(`执行: ${code.split('\n')[0].substring(0, 60)}...`, 'info');
  const out = document.getElementById('editor-output');
  out.style.display = 'block';
  out.className = '';
  out.textContent = '执行中...';
  try {
    const resp = await fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    const data = await resp.json();
    if (data.success) {
      out.textContent = data.stdout || '(无输出)';
      window.addAssistantLog(`执行成功 ${data.execution_time_ms}ms`, 'ok');
    } else {
      out.textContent = data.stderr || data.error || '未知错误';
      out.className = 'err';
      window.addAssistantLog(`执行失败: ${(data.error || data.stderr || '').substring(0, 80)}`, 'err');
    }
  } catch (e) {
    out.textContent = `请求失败: ${e.message}`;
    out.className = 'err';
    window.addAssistantLog(`请求失败: ${e.message}`, 'err');
  }
}

export async function saveFile() {
  if (!monacoEditor) return;
  activeTab.content = getContent();
  try {
    const body = { path: activeTab.path, content: activeTab.content };
    if (window.__activeWorkspace) body.workspace = window.__activeWorkspace;
    const resp = await fetch('/api/file/write', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (data.success !== false && !data.error) {
      activeTab.saved = true; updateTabs();
      window.addAssistantLog(`已保存: ${activeTab.path}`, 'ok');
    } else {
      window.addAssistantLog(`保存失败: ${data.error || '未知错误'}`, 'err');
    }
  } catch (e) { window.addAssistantLog(`保存异常: ${e.message}`, 'err'); }
}

// ================================================================
// 侧边栏打开文件
// ================================================================

export function openFileByName(path) {
  const ws = window.__activeWorkspace || '';
  const wsQ = ws ? '&workspace=' + encodeURIComponent(ws) : '';
  fetch(`/api/file?path=${encodeURIComponent(path)}${wsQ}`)
    .then(r => r.json())
    .then(data => { if (data.content !== undefined) openFile(path, data.content); })
    .catch(() => {});
}
