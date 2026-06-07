// Token 仪表盘模块 — sparkline + 缓存进度条 + 滑块 + 悬浮卡片
// ================================================================

import { addAssistantLog } from './chat.js';

// ================================================================
// 状态
// ================================================================

const MAX_BARS = 50;
const tokenBars = [];         // { total_tokens, cost, label, timestamp }
let accumulatedCost = 0;
let accumulatedTokens = 0;
let contextMaxTokens = 8000;  // 默认 8K，实际值从 SSE stats 事件同步
let compressThreshold = 60;   // 默认 60%
let sparklineData = [];       // 纯 token 数值，用于 canvas 绘制
let tooltipTimer = null;
let isDragging = false;

// ================================================================
// Canvas Sparkline 渲染
// ================================================================

function drawSparkline() {
  const canvas = document.getElementById('cs-sparkline');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);
  if (sparklineData.length < 2) {
    // 数据太少时画一条淡色基线
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    return;
  }

  const maxVal = Math.max(...sparklineData, 1);
  const minVal = Math.min(...sparklineData, 0);
  const range = maxVal - minVal || 1;
  const stepX = w / (sparklineData.length - 1);

  // 渐变填充
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, 'rgba(129, 140, 248, 0.4)');
  gradient.addColorStop(1, 'rgba(129, 140, 248, 0.02)');

  // 绘制填充区域
  ctx.beginPath();
  ctx.moveTo(0, h);
  for (let i = 0; i < sparklineData.length; i++) {
    const x = i * stepX;
    const y = h - ((sparklineData[i] - minVal) / range) * (h - 4) - 2;
    ctx.lineTo(x, y);
  }
  ctx.lineTo(w, h);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // 绘制折线
  ctx.beginPath();
  for (let i = 0; i < sparklineData.length; i++) {
    const x = i * stepX;
    const y = h - ((sparklineData[i] - minVal) / range) * (h - 4) - 2;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = 'rgba(129, 140, 248, 0.8)';
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.stroke();

  // 终点圆点
  const lastX = (sparklineData.length - 1) * stepX;
  const lastY = h - ((sparklineData[sparklineData.length - 1] - minVal) / range) * (h - 4) - 2;
  ctx.beginPath();
  ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(129, 140, 248, 1)';
  ctx.fill();
}

// ================================================================
// 缓存进度条 + 滑块
// ================================================================

function updateCacheBar() {
  const fill = document.getElementById('cs-cache-fill');
  const thumb = document.getElementById('cs-cache-thumb');
  const usedEl = document.getElementById('cs-used');
  const maxEl = document.getElementById('cs-max');
  if (!fill || !thumb) return;

  const maxCtx = contextMaxTokens || 8000;
  const used = Math.min(accumulatedTokens, maxCtx);
  const pct = maxCtx > 0 ? (used / maxCtx) * 100 : 0;
  const thresholdPct = compressThreshold;

  fill.style.width = Math.min(pct, 100) + '%';
  thumb.style.left = thresholdPct + '%';

  // 颜色变化
  fill.classList.remove('warm', 'hot');
  if (pct >= 90) fill.classList.add('hot');
  else if (pct >= thresholdPct * 0.85) fill.classList.add('warm');

  if (usedEl) usedEl.textContent = Math.round(used / 1000 * 10) / 10;
  if (maxEl) maxEl.textContent = Math.round(maxCtx / 1000);
}

function updateCostDisplay() {
  const el = document.getElementById('cs-cost-val');
  if (el) el.textContent = accumulatedCost.toFixed(4);
}

// ================================================================
// 添加一条 token bar 数据
// ================================================================

export function addTokenBar(data) {
  const total = data.total_tokens || 0;
  const cost = data.cost || 0;

  tokenBars.push({
    total_tokens: total,
    cost: cost,
    label: data.label || '',
    timestamp: Date.now(),
    prompt_tokens: data.prompt_tokens || 0,
    completion_tokens: data.completion_tokens || 0,
    cache_hit_tokens: data.cache_hit_tokens || 0,
    model: data.model || '',
  });

  if (tokenBars.length > MAX_BARS) tokenBars.shift();

  sparklineData = tokenBars.map(b => b.total_tokens);
  accumulatedCost += cost;
  accumulatedTokens += total;

  updateCostDisplay();
  drawSparkline();
  updateCacheBar();
}

// ================================================================
// 手动压缩
// ================================================================

export async function compressCache() {
  const btn = document.getElementById('cs-compress-btn');
  if (btn) btn.textContent = '⋯';
  try {
    const resp = await fetch('/api/token/compress', { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      addAssistantLog('🧹 上下文已压缩，释放 ' + (data.freed || '?') + ' tok', 'ok');
      // 重置累计 token（模拟压缩后水位下降）
      if (data.remaining !== undefined) {
        accumulatedTokens = data.remaining;
      } else {
        accumulatedTokens = Math.max(0, accumulatedTokens - (data.freed || 0));
      }
      updateCacheBar();
    } else {
      addAssistantLog('压缩失败: ' + (data.error || '未知错误'), 'err');
    }
  } catch (e) {
    addAssistantLog('压缩请求失败: ' + e.message, 'err');
  }
  if (btn) btn.textContent = '↻';
}

// ================================================================
// 悬浮卡片
// ================================================================

function showTooltip(html) {
  const tip = document.getElementById('cs-tooltip');
  const body = document.getElementById('cs-tooltip-body');
  if (!tip || !body) return;
  body.innerHTML = html;
  tip.style.display = 'block';
}

function hideTooltip() {
  const tip = document.getElementById('cs-tooltip');
  if (tip) tip.style.display = 'none';
}

// ================================================================
// SSE 事件监听
// ================================================================

export function onTokenBarEvent(data) {
  if (data && data.total_tokens !== undefined) {
    addTokenBar(data);
  }
}

/**
 * 从 SSE stats 事件同步上下文最大 token 数。
 * 每次 stats 推送时由 chat.js 调用。
 */
export function updateContextMax(maxTokens) {
  if (maxTokens && maxTokens > 0) {
    contextMaxTokens = maxTokens;
    updateCacheBar();
  }
}

// ================================================================
// 初始化：绑定交互事件
// ================================================================

export function initTokenChart() {
  const canvas = document.getElementById('cs-sparkline');
  const cacheBar = document.getElementById('cs-cache-bar');
  const thumb = document.getElementById('cs-cache-thumb');
  const compressBtn = document.getElementById('cs-compress-btn');

  // sparkline hover 显示操作列表
  if (canvas) {
    canvas.addEventListener('mouseenter', () => {
      clearTimeout(tooltipTimer);
      if (tokenBars.length === 0) {
        showTooltip('<div class="tt-title">暂无数据</div>');
        return;
      }
      const rows = tokenBars.slice(-10).reverse().map(b => {
        const time = new Date(b.timestamp).toLocaleTimeString();
        const label = b.label || '操作';
        return `<div class="tt-row"><span>${time} ${label}</span><span class="tt-val">${b.total_tokens} tok</span></div>`;
      }).join('');
      const total = tokenBars.reduce((s, b) => s + b.total_tokens, 0);
      const hitRate = tokenBars.length > 0
        ? Math.round(tokenBars.reduce((s, b) => s + (b.cache_hit_tokens || 0), 0) / Math.max(total, 1) * 100)
        : 0;
      const sandboxExec = document.getElementById('st-exec');
      const execCount = sandboxExec ? sandboxExec.textContent : '?';
      showTooltip(`
        <div class="tt-title">最近操作 (${tokenBars.length} 条)</div>
        ${rows}
        <hr class="tt-sep">
        <div class="tt-row"><span>累计 Token</span><span class="tt-val">${total.toLocaleString()}</span></div>
        <div class="tt-row"><span>今日费用</span><span class="tt-val">¥${accumulatedCost.toFixed(4)}</span></div>
        <div class="tt-row"><span>缓存命中</span><span class="tt-val">${hitRate}%</span></div>
        <div class="tt-row"><span>沙箱执行</span><span class="tt-val">${execCount} 次</span></div>
      `);
    });
    canvas.addEventListener('mouseleave', () => {
      tooltipTimer = setTimeout(hideTooltip, 200);
    });
  }

    // 缓存进度条 hover 显示缓存状态
  if (cacheBar) {
    cacheBar.addEventListener('mouseenter', () => {
      clearTimeout(tooltipTimer);
      const maxCtx = contextMaxTokens || 8000;
      const used = Math.min(accumulatedTokens, maxCtx);
      const pct = maxCtx > 0 ? Math.round((used / maxCtx) * 100) : 0;
      const threshold = compressThreshold;
      const lastCompress = localStorage.getItem('lastCompressTime');
      const compressStr = lastCompress ? Math.round((Date.now() - parseInt(lastCompress)) / 60000) + ' 分钟前' : '从未';
      showTooltip(`
        <div class="tt-title">上下文缓存</div>
        <div class="tt-row"><span>已用</span><span class="tt-val">${used.toLocaleString()} tok (${pct}%)</span></div>
        <div class="tt-row" style="cursor:pointer" onclick="promptEditMaxTokens()"><span>上限</span><span class="tt-val">${maxCtx.toLocaleString()} tok ✏️</span></div>
        <div class="tt-row"><span>自动压缩阈值</span><span class="tt-val">${threshold}% (${Math.round(maxCtx * threshold / 100).toLocaleString()} tok)</span></div>
        <div class="tt-row"><span>上次压缩</span><span class="tt-val">${compressStr}</span></div>
        <hr class="tt-sep">
        <div class="tt-row" style="cursor:pointer;color:var(--text-muted);font-size:10px" onclick="promptEditMaxTokens()">⚙️ 点击修改上限</div>
      `);
    });
    cacheBar.addEventListener('mouseleave', () => {
      tooltipTimer = setTimeout(hideTooltip, 200);
    });

    // 滑块拖动
    if (thumb) {
      thumb.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        isDragging = true;
        thumb.classList.add('dragging');
        document.body.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';
      });
    }

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const rect = cacheBar.getBoundingClientRect();
      let pct = ((e.clientX - rect.left) / rect.width) * 100;
      pct = Math.max(10, Math.min(95, pct));
      compressThreshold = Math.round(pct);
      updateCacheBar();
      // 显示临时数值
      const maxCtx = contextMaxTokens || 8000;
      const tokVal = Math.round(maxCtx * compressThreshold / 100);
      showTooltip(`
        <div class="tt-title">拖动调整阈值</div>
        <div class="tt-row"><span>触发压缩</span><span class="tt-val">${compressThreshold}%</span></div>
        <div class="tt-row"><span>对应 token</span><span class="tt-val">${tokVal.toLocaleString()} tok</span></div>
      `);
    });

    document.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        if (thumb) thumb.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        localStorage.setItem('compressThreshold', compressThreshold.toString());
        setTimeout(hideTooltip, 1500);
      }
    });
  }

  // 压缩按钮
  if (compressBtn) {
    compressBtn.addEventListener('click', compressCache);
  }

  // 从 localStorage 恢复阈值
  try {
    const saved = localStorage.getItem('compressThreshold');
    if (saved) compressThreshold = Math.max(10, Math.min(95, parseInt(saved)));
  } catch (e) {}

  // 初绘
  drawSparkline();
  updateCacheBar();
  updateCostDisplay();
}

// ================================================================
// 修改上下文上限（鼠标点击触发）
// ================================================================

export function promptEditMaxTokens() {
  const current = contextMaxTokens || 8000;
  const input = prompt(`输入新的上下文最大 token 数（当前: ${current.toLocaleString()}）\n范围: 512 ~ 1,048,576`, current.toString());
  if (input === null) return; // 取消

  const val = parseInt(input);
  if (isNaN(val) || val < 512 || val > 1048576) {
    alert('无效值，请输入 512 ~ 1,048,576 之间的整数');
    return;
  }

  // 先更新本地状态，让界面立即响应
  contextMaxTokens = val;
  updateCacheBar();

  // 异步写入后端配置
  fetch('/api/token/max-tokens', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ max_tokens: val }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        addAssistantLog(`⚙️ 上下文上限已更新为 ${data.max_tokens.toLocaleString()} tok`, 'ok');
      } else {
        addAssistantLog(`上限修改失败: ${data.error || '未知错误'}`, 'err');
        // 回滚
        contextMaxTokens = current;
        updateCacheBar();
      }
    })
    .catch(e => {
      addAssistantLog(`上限修改请求失败: ${e.message}`, 'err');
      contextMaxTokens = current;
      updateCacheBar();
    });
}

// ================================================================
// 清除仪表盘数据
// ================================================================

export function clearTokenChart() {
  tokenBars.length = 0;
  sparklineData = [];
  accumulatedCost = 0;
  accumulatedTokens = 0;
  drawSparkline();
  updateCacheBar();
  updateCostDisplay();
}
