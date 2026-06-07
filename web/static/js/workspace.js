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
  const container = document.getElementById('ws-tabs');
  if (!container) return;
  container.innerHTML = workspaces.map(ws => {
    const isActive = ws.name === activeWorkspace;
    const userLabel = ws.type === 'ssh'
      ? (ws.username || 'root') + '@' + (ws.host || '?')
      : ws.type === 'local-root' ? 'root' : 'a1';
    return `<div class="ws-tab${isActive ? ' active' : ''}" onclick="switchWorkspace('${escHtml(ws.name)}')" title="${ws.type}">
      <span class="ws-dot"></span>
      <span>${escHtml(ws.name)}</span>
      <span class="ws-user">(${escHtml(userLabel)})</span>
    </div>`;
  }).join('');
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
      renderWsTabs();
      loadFileTree();
    }
  } catch (e) {}
}

// ================================================================
// 管理弹窗
// ================================================================

export function showWsDialog() {
  let ov = document.getElementById('ws-dialog-overlay');
  if (!ov) {
    const div = document.createElement('div');
    div.id = 'ws-dialog-overlay';
    div.className = 'overlay';
    div.onclick = function(e) { if (e.target === this) closeWsDialog(); };
    div.innerHTML = `
      <div class="overlay-box ws-dialog">
        <h2 style="font-size:16px;margin-bottom:12px">工作区管理</h2>
        <div id="ws-list"></div>
        <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border-subtle)">
          <h3 style="font-size:12px;margin-bottom:8px;color:var(--text-secondary)">添加工作区</h3>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
            <input id="ws-name" placeholder="名称" style="grid-column:1/3">
            <select id="ws-type">
              <option value="local-sandbox">本地沙箱 (a1)</option>
              <option value="local-root">本地 Root</option>
              <option value="ssh">SSH 远程</option>
            </select>
            <input id="ws-path" placeholder="路径 (默认 ~)" value="/home/a1">
          </div>
          <div id="ws-ssh-fields" style="display:none;margin-top:6px;grid-template-columns:1fr 1fr;gap:6px">
            <input id="ws-host" placeholder="主机地址">
            <input id="ws-port" placeholder="端口" value="22" type="number">
            <input id="ws-user" placeholder="用户名" value="root">
            <input id="ws-pass" placeholder="密码" type="password">
          </div>
          <button onclick="saveWsFromForm()" style="margin-top:8px;width:100%">添加</button>
        </div>
        <button onclick="closeWsDialog()" class="secondary" style="margin-top:8px;width:100%">关闭</button>
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
    const userLabel = ws.type === 'ssh'
      ? `${ws.username||'root'}@${ws.host||'?'}`
      : ws.type === 'local-root' ? 'root' : 'a1';
    const isActive = ws.name === activeWorkspace;
    return `<div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border-subtle)">
      <div>
        <strong>${escHtml(ws.name)}</strong>
        <span style="font-size:11px;color:var(--text-muted);margin-left:6px">${escHtml(userLabel)}</span>
        ${isActive ? '<span style="font-size:10px;color:var(--success);margin-left:6px">● 当前</span>' : ''}
      </div>
      <div style="display:flex;gap:4px">
        ${!isActive ? `<button class="secondary" style="font-size:10px;padding:2px 8px" onclick="switchWorkspace('${escHtml(ws.name)}')">切换</button>` : ''}
        <button class="danger" style="font-size:10px;padding:2px 8px" onclick="deleteWs('${escHtml(ws.name)}')">删除</button>
      </div>
    </div>`;
  }).join('');
}

// ================================================================
// CRUD
// ================================================================

export async function saveWsFromForm() {
  const name = document.getElementById('ws-name').value.trim();
  const type = document.getElementById('ws-type').value;
  if (!name) return;
  const config = { name, type };
  if (type === 'local-sandbox' || type === 'local-root') {
    config.path = document.getElementById('ws-path').value.trim() || '/home/a1';
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
