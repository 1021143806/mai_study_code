// 工作区模块 — 顶部标签 + 管理弹窗
import { icon, iconFile } from './icons.js';
import { loadFileTree } from './sidebar.js';

// ================================================================
// 状态
// ================================================================
export let workspaces = [];
export let activeWorkspace = '';

// ================================================================
// 工作区加载与渲染
// ================================================================

export async function loadWorkspaces() {
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

export function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ================================================================
// 切换工作区
// ================================================================

export async function switchWorkspace(name) {
  if (name === activeWorkspace) return;
  try {
    const resp = await fetch(`/api/workspaces/${encodeURIComponent(name)}/activate`, { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      activeWorkspace = name;
      window.__activeWorkspace = name;
      // 显示编辑器面板
      document.getElementById('editor-panel').style.display = '';
      renderWsTabs();
      loadFileTree();
    }
  } catch (e) {}
}

// ================================================================
// 管理弹窗 — 卡片式布局
// ================================================================

export function showWsDialog() {
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

export function closeWsDialog() {
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
        <button class="secondary" style="font-size:10px;padding:3px 8px" onclick="testWsConn('${escHtml(ws.name)}', this)" title="测试连接">🔍</button>
        <button class="danger" style="font-size:10px;padding:3px 8px" onclick="deleteWs('${escHtml(ws.name)}')">删除</button>
      </div>
    </div>`;
  }).join('');
}

// ================================================================
// CRUD
// ================================================================

export async function testWsConn(name, btn) {
  const orig = btn.textContent;
  btn.textContent = '⏳';
  btn.disabled = true;
  try {
    const resp = await fetch(`/api/workspaces/${encodeURIComponent(name)}/test`, { method: 'POST' });
    const data = await resp.json();
    btn.textContent = data.success ? '✅' : '❌';
    setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 1500);
  } catch (e) {
    btn.textContent = '❌';
    setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 1500);
  }
}

export async function saveWsFromForm() {
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
    }
  } catch (e) {}
}

export async function deleteWs(name) {
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
    }
  } catch (e) {}
}
