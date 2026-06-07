// 编辑器模块 — CodeMirror 6 管理
import { EditorView, basicSetup } from 'codemirror';
import { EditorState } from '@codemirror/state';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import { keymap } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { iconFile } from './icons.js';

// ================================================================
// 状态
// ================================================================
export let editorView = null;
export let activeTab = { path: 'welcome.py', content: '# 欢迎使用麦麦学代码\n# 在此编写 Python 代码，点击 ▶ 运行\n\nprint("你好，守护者！")\n\n', saved: true };
export let openTabs = [activeTab];
export let currentLang = 'python';

// 在 HTML onclick 中使用的函数需要导出到 window，通过 app.js 处理
export let renderSidebarCallback = null;

export function setRenderSidebarCallback(fn) {
  renderSidebarCallback = fn;
}

// ================================================================
// 编辑器创建
// ================================================================

export function createEditor() {
  const container = document.getElementById('editor-container');
  const ext = [
    basicSetup || [],
    keymap.of(defaultKeymap),
    history(),
    keymap.of(historyKeymap),
    EditorView.editable.of(true),
    placeholder('在此编写代码...'),
    EditorView.updateListener.of(update => {
      if (update.docChanged) { activeTab.saved = false; updateTabs(); }
      const pos = update.state.selection.main.head;
      const line = update.state.doc.lineAt(pos);
      document.getElementById('status-ln').textContent = line.number;
      document.getElementById('status-col').textContent = pos - line.from + 1;
    }),
  ];
  if (currentLang === 'python') ext.push(python());
  ext.push(oneDark);
  const state = EditorState.create({ doc: activeTab.content, extensions: ext });
  editorView = new EditorView({ state, parent: container });
  updateTabs();
}

function placeholder(text) {
  return EditorView.theme({
    '.cm-content': {
      '&::before': {
        content: text ? `"${text}"` : 'none',
        color: 'rgba(255,255,255,0.2)',
        fontStyle: 'italic'
      }
    }
  });
}

// ================================================================
// 语言切换
// ================================================================

export function switchEditorLang(lang) {
  currentLang = lang;
  const langEl = document.getElementById('editor-lang');
  if (langEl) langEl.value = lang;
  document.getElementById('status-lang').textContent = lang;
  if (!editorView) return;
  const doc = editorView.state.doc.toString();
  editorView.destroy();
  const container = document.getElementById('editor-container');
  const ext = [
    basicSetup || [],
    keymap.of(defaultKeymap),
    history(),
    keymap.of(historyKeymap),
    EditorView.editable.of(true),
    placeholder('在此编写代码...'),
    EditorView.updateListener.of(update => {
      if (update.docChanged) { activeTab.saved = false; updateTabs(); }
      const pos = update.state.selection.main.head;
      const line = update.state.doc.lineAt(pos);
      document.getElementById('status-ln').textContent = line.number;
      document.getElementById('status-col').textContent = pos - line.from + 1;
    }),
  ];
  if (lang === 'python') ext.push(python());
  ext.push(oneDark);
  const state = EditorState.create({ doc, extensions: ext });
  editorView = new EditorView({ state, parent: container });
}

// ================================================================
// 标签页
// ================================================================

function updateTabs() {
  document.getElementById('editor-tabs').innerHTML = openTabs.map((t, i) =>
    `<div class="editor-tab${t.path === activeTab.path ? ' active' : ''}" onclick="switchToTab(${i})">
      <span>${t.saved ? '' : '● '}${t.path.split('/').pop()}</span>
      <span class="close" onclick="event.stopPropagation();closeTab(${i})">&times;</span>
    </div>`
  ).join('');
  if (renderSidebarCallback) renderSidebarCallback();
}

export function openFile(path, content) {
  const existing = openTabs.find(t => t.path === path);
  if (existing) { activeTab = existing; switchToTab(openTabs.indexOf(existing)); return; }
  openTabs.push({ path, content, saved: true });
  activeTab = openTabs[openTabs.length - 1];
  if (editorView) editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: content } });
  // 可视化按钮：仅 config.toml 显示
  const vizBtn = document.getElementById('config-viz-btn');
  if (vizBtn) {
    vizBtn.style.display = path === 'config.toml' ? '' : 'none';
    if (path !== 'config.toml' && window.__isConfigVisual) window.toggleConfigVisual();
  }
  updateTabs();
  if (path.endsWith('.py')) switchEditorLang('python');
  else if (path.endsWith('.md')) switchEditorLang('markdown');
  else if (path.endsWith('.json')) switchEditorLang('json');
  else if (path.endsWith('.toml') || path.endsWith('.txt')) switchEditorLang('text');
}

export function closeTab(index) {
  if (openTabs.length <= 1) return;
  const wasActive = openTabs[index].path === activeTab.path;
  openTabs.splice(index, 1);
  if (wasActive) {
    activeTab = openTabs[Math.min(index, openTabs.length - 1)];
    if (editorView) editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: activeTab.content } });
  }
  updateTabs();
}

export function switchToTab(index) {
  if (activeTab.path === openTabs[index].path) return;
  if (editorView && !activeTab.saved) activeTab.content = editorView.state.doc.toString();
  activeTab = openTabs[index];
  if (editorView) editorView.dispatch({ changes: { from: 0, to: editorView.state.doc.length, insert: activeTab.content } });
  updateTabs();
  const p = activeTab.path;
  if (p.endsWith('.py')) switchEditorLang('python');
  else if (p.endsWith('.md')) switchEditorLang('markdown');
  else if (p.endsWith('.json')) switchEditorLang('json');
  else switchEditorLang('text');
}

// ================================================================
// 代码执行
// ================================================================

export async function runCode() {
  if (!editorView) return;
  const code = editorView.state.doc.toString();
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
  if (!editorView) return;
  activeTab.content = editorView.state.doc.toString();
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
// 侧边栏渲染（需配合 sidebar.js）
// ================================================================

export function openFileByName(path) {
  const ws = window.__activeWorkspace || '';
  const wsQ = ws ? '&workspace=' + encodeURIComponent(ws) : '';
  fetch(`/api/file?path=${encodeURIComponent(path)}${wsQ}`)
    .then(r => r.json())
    .then(data => { if (data.content !== undefined) openFile(path, data.content); })
    .catch(() => {});
}
