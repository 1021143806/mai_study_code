// 配置可视化编辑模块
import { editorView, activeTab } from './editor.js';
import { addAssistantLog } from './chat.js';

// ================================================================
// 状态
// ================================================================
let isConfigVisual = false;
let configSections = [];

window.__isConfigVisual = false;

// ================================================================
// 切换可视化/文本模式
// ================================================================

export function toggleConfigVisual() {
  const container = document.getElementById('config-visual');
  const editorEl = document.getElementById('editor-container');
  const btn = document.getElementById('config-viz-btn');
  if (!container || !editorEl || !btn) return;

  isConfigVisual = !isConfigVisual;
  window.__isConfigVisual = isConfigVisual;

  if (isConfigVisual) {
    btn.textContent = '文本编辑';
    editorEl.style.display = 'none';
    container.style.display = '';
    const toml = editorView ? editorView.state.doc.toString() : '';
    configSections = parseToml(toml);
    renderConfigForm(container, configSections);
  } else {
    btn.textContent = '可视化';
    container.style.display = 'none';
    editorEl.style.display = '';
    const newToml = tomlFromSections(configSections);
    if (editorView) {
      editorView.dispatch({
        changes: { from: 0, to: editorView.state.doc.length, insert: newToml }
      });
      activeTab.saved = false;
      // trigger updateTabs via the editor's update listener
    }
  }
}

// ================================================================
// TOML 解析
// ================================================================

function parseToml(toml) {
  const sections = [];
  let current = { name: '__root__', fields: [] };
  toml.split('\n').forEach(line => {
    const sectionMatch = line.match(/^\[([^\]]+)\]$/);
    if (sectionMatch) {
      if (current.fields.length > 0 || sections.length > 0) sections.push(current);
      current = { name: sectionMatch[1], fields: [] };
      return;
    }
    const kvMatch = line.match(/^(\w[\w.]*)\s*=\s*(.+)$/);
    if (kvMatch) {
      current.fields.push({ key: kvMatch[1], raw: line, value: kvMatch[2] });
    } else {
      const last = current.fields[current.fields.length - 1];
      if (last && line.trim()) last.value += '\n' + line.trimEnd();
    }
  });
  if (current.fields.length > 0) sections.push(current);
  return sections;
}

// ================================================================
// 表单渲染
// ================================================================

function renderConfigForm(container, sections) {
  container.innerHTML = `
  <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
    <span style="font-size:12px;font-weight:600;color:var(--text-secondary)">可视化配置</span>
    <span style="flex:1"></span>
    <button class="secondary" style="font-size:10px;padding:3px 10px" onclick="saveConfigVisual()">保存配置</button>
  </div>
  ${sections.map(section => `
    <div style="margin-bottom:16px;background:var(--glass-hover);border:1px solid var(--border-subtle);border-radius:var(--radius-md);padding:12px 16px">
      <h3 style="font-size:12px;font-weight:700;color:var(--text-accent);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px">${section.name === '__root__' ? '基础配置' : section.name}</h3>
      ${section.fields.map(f => renderField(f)).join('')}
    </div>
  `).join('')}`;
}

function renderField(field) {
  const val = field.value.replace(/^"|"$/g, '').replace(/^'|'$/g, '');
  const isBool = /^true$|^false$/i.test(field.value);
  const isNum = /^\d+\.?\d*$/.test(field.value);
  const label = field.key.split('.').pop() || field.key;
  const inputId = 'cfg-' + field.key.replace(/\./g, '-');

  if (isBool) {
    return `<div style="display:flex;align-items:center;justify-content:space-between;padding:3px 0">
      <label for="${inputId}" style="font-size:12px;color:var(--text-secondary)">${label}</label>
      <input type="checkbox" id="${inputId}" ${field.value === 'true' ? 'checked' : ''} style="accent-color:var(--accent)" onchange="updateConfigField('${field.key}', this.checked ? 'true' : 'false')">
    </div>`;
  }
  return `<div style="padding:3px 0">
    <label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:2px">${label}</label>
    <input type="${isNum ? 'number' : 'text'}" id="${inputId}" value="${escHtml(val)}" style="width:100%;font-size:11px;padding:4px 8px" onchange="updateConfigField('${field.key}', '${isNum ? '' : '"'}'+this.value+'${isNum ? '' : '"'}')">
  </div>`;
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ================================================================
// 字段更新 & TOML 导出
// ================================================================

export function updateConfigField(key, val) {
  for (const section of configSections) {
    const field = section.fields.find(f => f.key === key);
    if (field) { field.value = val; field.raw = key + ' = ' + val; return; }
  }
}

function tomlFromSections(sections) {
  return sections.map(s =>
    (s.name !== '__root__' ? '[' + s.name + ']\n' : '') +
    s.fields.map(f => f.raw).join('\n')
  ).join('\n') + '\n';
}

// ================================================================
// 保存配置到文件
// ================================================================

export async function saveConfigVisual() {
  const newToml = tomlFromSections(configSections);
  try {
    const resp = await fetch('/api/plugin-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: newToml })
    });
    const data = await resp.json();
    if (data.success) {
      addAssistantLog('配置已保存并触发重载', 'ok');
    } else {
      addAssistantLog('配置保存失败: ' + (data.error || ''), 'err');
    }
  } catch (e) {
    addAssistantLog('配置保存失败: ' + e.message, 'err');
  }
}
