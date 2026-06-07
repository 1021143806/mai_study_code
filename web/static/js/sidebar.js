// 侧边栏模块 — 文件树、知识库、Bot 页面
import { icon, iconFile } from './icons.js';
import { openFile } from './editor.js';

// ================================================================
// 状态
// ================================================================
export let fileTreeData = [];
export let recentFiles = [];
export let activeSidebar = 'explorer';

// 已展开目录路径集合（用于维持展开状态）
const expandedPaths = new Set();

// ================================================================
// 文件树 — 加载根节点
// ================================================================

export async function loadFileTree() {
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
    let wsPath = '';
    if (wsResp && wsResp.ok) {
      const wsData = await wsResp.json();
      wsPath = wsData.path || '';
    }
    root.innerHTML = `
      <div class="tree-item" style="--indent:0" onclick="window.__toggleWsRoot(this)">
        <span class="tree-chevron" style="font-size:9px;width:14px;text-align:center;flex-shrink:0;opacity:0.4">▶</span>
        <span class="tree-icon">${icon('folder')}</span>
        <span>${escHtml(wsName)}</span>
      </div>
      <div id="ws-root-children" style="display:none"></div>
      <div style="padding:2px 20px 4px;font-size:10px;color:var(--text-muted);line-height:1.5">
        ${wsPath ? `📍 ${friendlyPath(wsPath)}` : ''}
      </div>`;
  } catch (e) {
    const el = document.getElementById('file-tree');
    if (el) el.innerHTML = '<div style="padding:12px 16px;font-size:12px;color:var(--text-muted)">加载失败</div>';
  }
}

function friendlyPath(p) {
  if (p.includes('MaiBot/plugins/mai_study_code/workspace')) {
    return '插件内部目录 <code style="font-size:10px;background:var(--glass-hover);padding:1px 4px;border-radius:3px">workspace/</code>';
  }
  if (p === '/') return '系统根目录 <code style="font-size:10px;background:var(--glass-hover);padding:1px 4px;border-radius:3px">/</code>';
  return p;
}

// ================================================================
// 展开/收起根节点（暴露到 window 供 onclick 使用）
// ================================================================

window.__toggleWsRoot = function(el) {
  const children = document.getElementById('ws-root-children');
  const chevron = el.querySelector('.tree-chevron');
  if (children.style.display !== 'none') {
    children.style.display = 'none';
    if (chevron) chevron.classList.remove('open');
  } else {
    children.style.display = '';
    if (chevron) chevron.classList.add('open');
    if (!children.hasChildNodes() || children.children.length === 0) {
      renderFileTree(fileTreeData, children, 0, '');
    }
  }
};

// ================================================================
// 懒加载子目录
// ================================================================

async function loadChildrenForNode(node, container, indent, parentPath, onLoaded) {
  try {
    const ws = window.__activeWorkspace || '';
    const wsQ = ws ? `&workspace=${encodeURIComponent(ws)}` : '';
    const resp = await fetch(`/api/files?dir=${encodeURIComponent(node.path)}${wsQ}`);
    const data = await resp.json();
    const subtree = data.tree || [];
    node.children = subtree;

    // 显示加载指示器的轻量闪烁
    container.innerHTML = '';
    renderFileTree(subtree, container, indent, parentPath + node.path + '/');
    if (onLoaded) onLoaded();
  } catch (e) {
    container.innerHTML = '<div class="tree-item" style="--indent:' + indent + ';color:var(--text-muted);font-style:italic">加载失败</div>';
    if (onLoaded) onLoaded();
  }
}

// ================================================================
// 渲染文件树节点
// ================================================================

function renderFileTree(tree, container, indent, parentDir) {
  if (!indent && indent !== 0) indent = 0;
  container.innerHTML = '';

  if (!tree || tree.length === 0) {
    container.innerHTML = `<div class="tree-item" style="--indent:${indent};color:var(--text-muted);font-style:italic;cursor:default">空目录</div>`;
    return;
  }

  tree.forEach(node => {
    const fullPath = parentDir ? parentDir + node.name : node.path || node.name;
    const div = document.createElement('div');
    div.className = 'tree-item';
    div.dataset.path = fullPath;
    div.style.setProperty('--indent', indent);

    const isOpen = expandedPaths.has(fullPath);
    const svgIcon = node.is_dir
      ? (isOpen ? icon('folder-open') : icon('folder'))
      : iconFile(node.name);

    if (node.is_dir) {
      const childrenContainer = document.createElement('div');
      childrenContainer.style.display = isOpen ? '' : 'none';
      let hasLoadedChildren = false;

      // 只有需要展开时才构建 chevron
      const chevronHtml = `<span class="tree-chevron ${isOpen ? 'open' : ''}">${icon('chevron', 'sf-sm')}</span>`;
      div.innerHTML = `${chevronHtml}<span class="tree-icon">${svgIcon}</span><span>${node.name}</span>`;

      const chevronEl = div.querySelector('.tree-chevron');

      div.onclick = (e) => {
        // 判断是否点击了 chevron
        const isChevron = e.target === chevronEl
          || (e.target.classList && e.target.classList.contains('tree-chevron'))
          || (e.target.closest && e.target.closest('.tree-chevron'));

        if (isChevron) {
          e.stopPropagation();
          const currentlyOpen = childrenContainer.style.display !== 'none';

          if (currentlyOpen) {
            childrenContainer.style.display = 'none';
            if (chevronEl) chevronEl.classList.remove('open');
            // 更新文件夹图标为闭合
            const iconSpan = div.querySelector('.tree-icon');
            if (iconSpan) iconSpan.innerHTML = icon('folder');
            expandedPaths.delete(fullPath);
          } else {
            if (!hasLoadedChildren) {
              loadChildrenForNode(node, childrenContainer, indent + 1, parentDir ? parentDir : (node.path ? node.path.substring(0, node.path.length - node.name.length) : ''), () => {
                hasLoadedChildren = true;
                childrenContainer.style.display = '';
                if (chevronEl) chevronEl.classList.add('open');
                const iconSpan = div.querySelector('.tree-icon');
                if (iconSpan) iconSpan.innerHTML = icon('folder-open');
                expandedPaths.add(fullPath);
              });
            } else {
              childrenContainer.style.display = '';
              if (chevronEl) chevronEl.classList.add('open');
              const iconSpan = div.querySelector('.tree-icon');
              if (iconSpan) iconSpan.innerHTML = icon('folder-open');
              expandedPaths.add(fullPath);
            }
          }
        } else {
          // 选中节点
          document.querySelectorAll('.tree-item.selected').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
        }
      };

      // 右键菜单
      div.oncontextmenu = (e) => {
        e.preventDefault();
        e.stopPropagation();
        showContextMenu(e.clientX, e.clientY, fullPath, node, div, container, indent, parentDir);
      };

      // 如果之前已展开，预加载 children
      if (isOpen && node.children && node.children.length > 0) {
        renderFileTree(node.children, childrenContainer, indent + 1, fullPath + '/');
        hasLoadedChildren = true;
      }

      container.appendChild(div);
      container.appendChild(childrenContainer);
    } else {
      // 文件节点
      div.innerHTML = `<span class="tree-chevron" style="visibility:hidden">${icon('chevron', 'sf-sm')}</span><span class="tree-icon">${svgIcon}</span><span>${node.name}</span>`;

      div.onclick = async () => {
        document.querySelectorAll('.tree-item.selected').forEach(el => el.classList.remove('selected'));
        div.classList.add('selected');
        try {
          const ws = window.__activeWorkspace || '';
          const wsQ = ws ? `&workspace=${encodeURIComponent(ws)}` : '';
          const resp = await fetch(`/api/file?path=${encodeURIComponent(node.path)}${wsQ}`);
          const data = await resp.json();
          if (data.content !== undefined) openFile(node.path, data.content);
        } catch (e) { window.addAssistantLog(`读取失败: ${node.path}`, 'warn'); }
      };

      // 右键菜单
      div.oncontextmenu = (e) => {
        e.preventDefault();
        e.stopPropagation();
        showContextMenu(e.clientX, e.clientY, fullPath, node, div, container, indent, parentDir);
      };

      container.appendChild(div);
    }
  });
}

// ================================================================
// 右键菜单
// ================================================================

let contextMenuEl = null;

function showContextMenu(x, y, fullPath, node, itemDiv, parentContainer, indent, parentDir) {
  removeContextMenu();

  const isDir = node.is_dir;
  const menu = document.createElement('div');
  menu.className = 'context-menu';
  menu.style.cssText = `left:${Math.min(x, window.innerWidth - 180)}px;top:${Math.min(y, window.innerHeight - 200)}px`;

  const items = [];

  if (isDir) {
    items.push({ label: '📁 新建文件', action: () => promptCreate(fullPath, false) });
    items.push({ label: '📂 新建文件夹', action: () => promptCreate(fullPath, true) });
    items.push({ label: '✏️ 重命名', action: () => promptRename(fullPath, node, itemDiv) });
    items.push({ type: 'sep' });
    items.push({ label: '🗑️ 删除目录', action: () => confirmDelete(fullPath, node, itemDiv, parentContainer), danger: true });
  } else {
    items.push({ label: '✏️ 重命名', action: () => promptRename(fullPath, node, itemDiv) });
    items.push({ type: 'sep' });
    items.push({ label: '🗑️ 删除文件', action: () => confirmDelete(fullPath, node, itemDiv, parentContainer), danger: true });
  }

  items.forEach(item => {
    if (item.type === 'sep') {
      const sep = document.createElement('div');
      sep.className = 'context-menu-sep';
      menu.appendChild(sep);
      return;
    }
    const btn = document.createElement('div');
    btn.className = 'context-menu-item' + (item.danger ? ' danger' : '');
    btn.textContent = item.label;
    btn.onclick = () => { removeContextMenu(); item.action(); };
    menu.appendChild(btn);
  });

  contextMenuEl = menu;
  document.body.appendChild(menu);

  // 点击其他地方关闭
  setTimeout(() => {
    document.addEventListener('click', removeContextMenu, { once: true });
  }, 0);
}

function removeContextMenu() {
  if (contextMenuEl) {
    contextMenuEl.remove();
    contextMenuEl = null;
  }
}

// ================================================================
// 文件操作：新建、重命名、删除
// ================================================================

function promptCreate(parentPath, isDir) {
  const label = isDir ? '新建文件夹' : '新建文件';
  const name = prompt(`${label}\n路径: ${parentPath || '(根目录)'}\n\n输入名称:`);
  if (!name || !name.trim()) return;
  executeCreate(parentPath, name.trim(), isDir);
}

async function executeCreate(parentPath, name, isDir) {
  const ws = window.__activeWorkspace || '';
  const body = { parent: parentPath, name, is_dir: isDir };
  if (ws) body.workspace = ws;
  try {
    const resp = await fetch('/api/file/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (data.success) {
      window.addAssistantLog(`已创建: ${parentPath ? parentPath + '/' : ''}${name}`, 'ok');
      refreshTree();
    } else {
      window.addAssistantLog(`创建失败: ${data.error || '未知错误'}`, 'err');
    }
  } catch (e) {
    window.addAssistantLog(`创建异常: ${e.message}`, 'err');
  }
}

function promptRename(fullPath, node, itemDiv) {
  const oldName = node.name;
  const newName = prompt('重命名:\n' + fullPath + '\n\n新名称:', oldName);
  if (!newName || !newName.trim() || newName.trim() === oldName) return;
  renameNode(fullPath, oldName, newName.trim());
}

async function renameNode(fullPath, oldName, newName) {
  const ws = window.__activeWorkspace || '';
  const body = { path: fullPath, name: newName };
  if (ws) body.workspace = ws;
  try {
    const resp = await fetch('/api/file/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (data.success) {
      window.addAssistantLog(`已重命名: ${oldName} → ${newName}`, 'ok');
      refreshTree();
    } else {
      window.addAssistantLog(`重命名失败: ${data.error || '未知错误'}`, 'err');
    }
  } catch (e) {
    window.addAssistantLog(`重命名异常: ${e.message}`, 'err');
  }
}

function confirmDelete(fullPath, node, itemDiv, parentContainer) {
  const type = node.is_dir ? '目录' : '文件';
  if (!confirm(`确定删除${type}「${node.name}」吗？\n路径: ${fullPath}\n\n此操作不可撤销。`)) return;
  deleteNode(fullPath);
}

async function deleteNode(fullPath) {
  const ws = window.__activeWorkspace || '';
  const body = { path: fullPath };
  if (ws) body.workspace = ws;
  try {
    const resp = await fetch('/api/file/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (data.success) {
      window.addAssistantLog(`已删除: ${fullPath}`, 'ok');
      // 从展开状态中清理
      expandedPaths.delete(fullPath);
      refreshTree();
    } else {
      window.addAssistantLog(`删除失败: ${data.error || '未知错误'}`, 'err');
    }
  } catch (e) {
    window.addAssistantLog(`删除异常: ${e.message}`, 'err');
  }
}

// ================================================================
// 刷新文件树（保持展开状态）
// ================================================================

export function refreshTree() {
  loadFileTree();
}

// ================================================================
// 侧边栏渲染（已打开、最近打开）
// ================================================================

export function renderSidebar() {
  const openEl = document.getElementById('open-files');
  if (openEl) {
    const tabs = (window.__openTabs || []).filter(t => t.path !== 'welcome.py');
    openEl.innerHTML = tabs.length === 0
      ? '<div class="tree-item" style="--indent:0;color:var(--text-muted)">暂无打开的文件</div>'
      : tabs.map(t => {
          const idx = (window.__openTabs || []).indexOf(t);
          return `<div class="tree-item${t.path === (window.__activeTab || {}).path ? ' selected' : ''}" style="--indent:0" onclick="window.switchToTab(${idx})"><span class="tree-icon">${iconFile(t.path)}</span>${t.path.split('/').pop()}</div>`;
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

export function addRecentFile(path) {
  recentFiles = [path, ...recentFiles.filter(f => f !== path)];
}

// ================================================================
// 侧边栏切换
// ================================================================

export function switchSidebar(name) {
  activeSidebar = name;
  document.querySelectorAll('#activitybar .btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`[data-sidebar="${name}"]`);
  if (btn) btn.classList.add('active');
  ['panel-explorer', 'panel-knowledge', 'panel-pages-list'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  const panelMap = { explorer: 'panel-explorer', knowledge: 'panel-knowledge', 'pages-list': 'panel-pages-list' };
  const panel = document.getElementById(panelMap[name]);
  if (panel) panel.style.display = '';
  const titles = { explorer: '资源管理器', knowledge: '知识库', 'pages-list': 'Bot 页面' };
  const titleEl = document.getElementById('sidebar-title');
  if (titleEl) titleEl.textContent = titles[name] || '资源管理器';
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.remove('collapsed');
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
