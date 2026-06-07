// Monaco Editor 启动引导
// 加载 Monaco AMD loader，然后初始化编辑器
// 完成后设置 window.monaco 并触发 app.js 中的初始化

const MONACO_BASE = '/monaco';

(function() {
  var script = document.createElement('script');
  script.src = MONACO_BASE + '/vs/loader.js';
  script.onload = function() {
    // 配置 require baseUrl
    require.config({
      baseUrl: MONACO_BASE + '/vs',
      paths: { 'vs': MONACO_BASE + '/vs' }
    });
    // 加载编辑器主模块
    require(['vs/editor/editor.main'], function() {
      // Monaco 已就绪，设置为全局变量，app.js 会检测并使用它
      window.__monacoReady = true;
      // 触发一个自定义事件通知 app.js
      document.dispatchEvent(new Event('monaco-ready'));
    });
  };
  script.onerror = function() {
    console.error('Monaco loader.js 加载失败');
    window.__monacoReady = false;
    document.dispatchEvent(new Event('monaco-ready'));
  };
  document.head.appendChild(script);
})();
