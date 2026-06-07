// CodeMirror 编辑器引导
// 只从 codemirror 综合包导入，不额外加载子包以避免版本冲突
import { EditorView, basicSetup } from 'codemirror';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';

try {
  const container = document.getElementById('editor-container');
  if (!container) throw new Error('editor-container 不存在');

  const doc = (window.__activeTab && window.__activeTab.content) || '';

  // 不导入 EditorState，直接用 EditorView 构造
  window.editorView = new EditorView({
    doc: doc,
    extensions: [
      basicSetup || [],
      EditorView.editable.of(true),
      EditorView.theme({
        '.cm-content': {
          '&::before': {
            content: doc ? '"在此编写代码..."' : 'none',
            color: 'rgba(255,255,255,0.2)',
            fontStyle: 'italic'
          }
        }
      }),
      EditorView.updateListener.of(update => {
        if (update.docChanged && window.__activeTab) { window.__activeTab.saved = false; }
        const pos = update.state.selection.main.head;
        const line = update.state.doc.lineAt(pos);
        document.getElementById('status-ln').textContent = line.number;
        document.getElementById('status-col').textContent = pos - line.from + 1;
      }),
      python(),
      oneDark,
    ],
    parent: container,
  });

  window.logToPanel('编辑器已就绪', 'ok');
} catch (e) {
  window.logToPanel('编辑器加载失败: ' + e.message, 'err');
  console.error('CodeMirror Error:', e);
}
