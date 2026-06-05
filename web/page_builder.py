"""页面生成器。

管理 Bot 自写页面：扫描目录、提取标题、生成默认页面。
"""

from typing import Any, Dict, List

import os
import re


class PageBuilder:
    """Bot 页面管理器。

    负责扫描 workspace/web/pages/ 目录，提取页面元数据。
    """

    def __init__(self, workspace_dir: str) -> None:
        """初始化页面生成器。

        Args:
            workspace_dir: 工作区根目录。
        """
        self._web_dir = os.path.join(workspace_dir, "web")
        self._pages_dir = os.path.join(self._web_dir, "pages")
        os.makedirs(self._pages_dir, exist_ok=True)

    def list_pages(self) -> List[Dict[str, Any]]:
        """列出所有 Bot 自写页面。

        Returns:
            List[Dict]: 页面列表，每项包含 name, title, path。
        """
        pages = []
        if not os.path.isdir(self._pages_dir):
            return pages

        for filename in sorted(os.listdir(self._pages_dir)):
            if not filename.endswith(".html"):
                continue
            filepath = os.path.join(self._pages_dir, filename)
            if not os.path.isfile(filepath):
                continue
            name = filename[:-5]  # 去掉 .html
            title = self._extract_title(filepath) or name
            pages.append({
                "name": name,
                "title": title,
                "path": filename,
            })
        return pages

    @staticmethod
    def _extract_title(filepath: str) -> str:
        """从 HTML 文件中提取 <title> 内容。

        Args:
            filepath: HTML 文件路径。

        Returns:
            str: 标题文本，提取失败返回空字符串。
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read(4096)  # 只读前 4KB
            match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return ""

    def get_page_content(self, name: str) -> str:
        """获取指定页面的 HTML 内容。

        Args:
            name: 页面名称（不含 .html）。

        Returns:
            str: HTML 内容。

        Raises:
            FileNotFoundError: 页面不存在。
        """
        filepath = os.path.join(self._pages_dir, f"{name}.html")
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"页面不存在: {name}")
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def ensure_default_pages(self) -> None:
        """确保默认页面存在（如果 pages 目录为空则创建）。"""
        if not os.listdir(self._pages_dir):
            index_path = os.path.join(self._pages_dir, "index.html")
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(self._default_index_html())

    @staticmethod
    def _default_index_html() -> str:
        """默认 Bot 首页 HTML。"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>麦麦的首页</title>
    <link rel="stylesheet" href="/static/theme.css">
    <style>
        body {
            font-family: var(--font-sans);
            background: var(--bg-primary);
            color: var(--text-primary);
            max-width: 800px;
            margin: 0 auto;
            padding: var(--spacing-lg);
        }
        h1 { color: var(--color-info); }
        .card {
            background: var(--bg-card);
            border-radius: var(--border-radius);
            padding: var(--spacing-md);
            margin: var(--spacing-md) 0;
            box-shadow: var(--shadow-card);
        }
        a { color: var(--color-info); }
    </style>
</head>
<body>
    <nav style="margin-bottom:var(--spacing-lg)">
        <a href="/">← 监控面板</a>
    </nav>
    <h1>🐚 欢迎来到麦麦的页面</h1>
    <div class="card">
        <p>这是麦麦自己写的首页！</p>
        <p>麦麦可以通过聊天来修改这个页面，添加任何想要的内容。</p>
    </div>
    <div class="card">
        <h3>麦麦能做什么？</h3>
        <ul>
            <li>写代码并在沙箱中执行</li>
            <li>管理知识库，记住学到的东西</li>
            <li>操作文件，帮你管理项目</li>
            <li>执行 Shell 命令（root 权限）</li>
        </ul>
    </div>
</body>
</html>"""
