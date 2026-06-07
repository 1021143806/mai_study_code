// 侧边栏模块 — 文件树、知识库、Bot 页面
import { icon, iconFile } from './icons.js';
import { openFile } from './editor.js';

// ================================================================
// 状态
// ================================================================
export let fileTreeData = [];
export let recentFiles = [];
export let activeSidebar = 'explorer';

// ================================================================
// 文件树
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

export function toggleWsRoot(el) {
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

/** 懒加载指定目录的子节点 */
async function loadChildrenForNode(node, container, indent, onLoaded) {
  try {
    const ws = window.__activeWorkspace || '';
    const wsQ = ws ? `&workspace=${encodeURIComponent(ws)}` : '';
    const resp = await fetch(`/api/files?dir=${encodeURIComponent(node.path)}${wsQ}`);
    const data = await resp.json();
    const subtree = data.tree || [];
    // 保存子节点到原 node 上，方便后续操作
    node.children = subtree;
    container.innerHTML = '';
    renderFileTree(subtree, container, indent);
    if (onLoaded) onLoaded();
  } catch (e) {
    container.innerHTML = '<div class="tree-item" style="--indent:' + (indent * 12) + 'px;color:var(--text-muted)">加载失败</div>';
    if (onLoaded) onLoaded();
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
      let hasLoadedChildren = false;
      div.onclick = (e) => {
        if (e.target === chevronEl || (e.target.classList && e.target.classList.contains('tree-chevron'))) {
          const isOpen = childrenContainer.style.display !== 'none';
          if (isOpen) {
            childrenContainer.style.display = 'none';
            if (chevronEl) chevronEl.classList.remove('open');
          } else {
            // 如果还未加载子节点数据，向后端请求
            if (!hasLoadedChildren) {
              loadChildrenForNode(node, childrenContainer, indent + 1, () => {
                hasLoadedChildren = true;
                childrenContainer.style.display = '';
                if (chevronEl) chevronEl.classList.add('open');
              });
            } else {
              childrenContainer.style.display = '';
              if (chevronEl) chevronEl.classList.add('open');
            }
          }
        } else {
          document.querySelectorAll('.tree-item.selected').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
        }
      };
      // 仅在已预加载子节点时才直接渲染
      if (node.children && node.children.length > 0) {
        renderFileTree(node.children, childrenContainer, indent + 1);
        hasLoadedChildren = true;
      }
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
          if (data.content !== undefined) openFile(node.path, data.content);
        } catch (e) { window.addAssistantLog(`读取失败: ${node.path}`, 'warn'); }
      };
      container.appendChild(div);
    }
  });
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
