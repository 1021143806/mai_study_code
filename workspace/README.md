# 麦麦学习代码工作区

麦麦（MaiM）的学习与测试工作区，包含 Python 脚本实验和 Web 页面开发。

## 目录结构

```
workspace/
├── README.md              # 本文件
├── test_ide.py            # Python 测试脚本（打印、表格、进度条、彩色文字等）
└── web/
    ├── lib/
    │   └── codemirror.mjs # CodeMirror 编辑器库
    └── pages/
        └── index.html     # 麦麦的首页
```

## 文件说明

### `test_ide.py`
Python 功能测试脚本，涵盖：
- 基本打印输出
- 变量、列表、字典操作
- 格式化表格打印
- 星号金字塔图案
- 终端进度条动画
- ANSI 彩色文字

### `web/pages/index.html`
麦麦的 Web 首页，包含：
- 自定义 CSS 变量主题
- 导航链接（首页、关于、学习、项目、笔记）
- 功能介绍卡片（学习笔记、代码练习、项目展示、AI 助手）
- 底部版权信息

## 使用方式

### 运行 Python 测试
```bash
python test_ide.py
```

### 查看 Web 页面
在浏览器中打开 `web/pages/index.html`。

## 依赖

- Python 3.x（运行 test_ide.py）
- 现代浏览器（查看 Web 页面）
