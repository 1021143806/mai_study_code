"""知识库管理模块。

管理本地知识库，包括：
- Skill 文件：记录学到的技能和经验
- README：项目理解
- 笔记：踩坑记录和心得
"""

from typing import Any, Dict, List, Optional

import json
import os
import time


class KnowledgeEntry:
    """知识条目。"""

    def __init__(
        self,
        title: str,
        content: str,
        category: str = "note",
        tags: Optional[List[str]] = None,
    ) -> None:
        self.title = title
        self.content = content
        self.category = category  # skill, readme, note
        self.tags = tags or []
        self.created_at = time.time()
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        """从字典创建。"""
        entry = cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            category=data.get("category", "note"),
            tags=data.get("tags", []),
        )
        entry.created_at = data.get("created_at", time.time())
        entry.updated_at = data.get("updated_at", time.time())
        return entry


class KnowledgeBase:
    """本地知识库。

    管理 Skill、README 和笔记的持久化存储。
    知识库文件存储在插件目录下的 knowledge/ 文件夹中。
    """

    def __init__(self, base_dir: str) -> None:
        """初始化知识库。

        Args:
            base_dir: 知识库根目录。
        """
        self._base_dir = base_dir
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保目录结构存在。"""
        for category in ("skill", "readme", "note"):
            os.makedirs(os.path.join(self._base_dir, category), exist_ok=True)

    def add_entry(self, entry: KnowledgeEntry) -> str:
        """添加知识条目。

        Args:
            entry: 知识条目。

        Returns:
            str: 条目 ID（文件名）。
        """
        entry_id = self._make_id(entry.title)
        self._entries[entry_id] = entry
        self._save_entry(entry_id, entry)
        return entry_id

    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """获取知识条目。

        Args:
            entry_id: 条目 ID。

        Returns:
            Optional[KnowledgeEntry]: 知识条目。
        """
        if entry_id in self._entries:
            return self._entries[entry_id]

        # 尝试从文件加载
        entry = self._load_entry(entry_id)
        if entry:
            self._entries[entry_id] = entry
        return entry

    def search(self, query: str, category: Optional[str] = None) -> List[KnowledgeEntry]:
        """搜索知识条目。

        Args:
            query: 搜索关键词。
            category: 限定分类。

        Returns:
            List[KnowledgeEntry]: 匹配的条目列表。
        """
        results = []
        query_lower = query.lower()

        for entry_id, entry in self._entries.items():
            if category and entry.category != category:
                continue
            if (
                query_lower in entry.title.lower()
                or query_lower in entry.content.lower()
                or any(query_lower in tag.lower() for tag in entry.tags)
            ):
                results.append(entry)

        return results

    def list_entries(self, category: Optional[str] = None) -> List[KnowledgeEntry]:
        """列出知识条目。

        Args:
            category: 限定分类。

        Returns:
            List[KnowledgeEntry]: 条目列表。
        """
        if category:
            return [e for e in self._entries.values() if e.category == category]
        return list(self._entries.values())

    def update_entry(self, entry_id: str, content: str) -> bool:
        """更新知识条目内容。

        Args:
            entry_id: 条目 ID。
            content: 新内容。

        Returns:
            bool: 是否成功。
        """
        entry = self.get_entry(entry_id)
        if entry is None:
            return False
        entry.content = content
        entry.updated_at = time.time()
        self._save_entry(entry_id, entry)
        return True

    def delete_entry(self, entry_id: str) -> bool:
        """删除知识条目。

        Args:
            entry_id: 条目 ID。

        Returns:
            bool: 是否成功。
        """
        if entry_id in self._entries:
            del self._entries[entry_id]

        filepath = self._get_filepath(entry_id)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计。

        Returns:
            Dict[str, Any]: 统计信息。
        """
        categories = {"skill": 0, "readme": 0, "note": 0}
        for entry in self._entries.values():
            if entry.category in categories:
                categories[entry.category] += 1

        return {
            "total_entries": len(self._entries),
            "by_category": categories,
        }

    def _make_id(self, title: str) -> str:
        """生成条目 ID。

        Args:
            title: 标题。

        Returns:
            str: 安全的文件名 ID。
        """
        # 简单处理：替换非法字符
        safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)
        safe = safe.strip().replace(" ", "_").lower()
        return safe or f"entry_{int(time.time())}"

    def _get_filepath(self, entry_id: str) -> str:
        """获取条目文件路径。

        Args:
            entry_id: 条目 ID。

        Returns:
            str: 文件路径。
        """
        entry = self._entries.get(entry_id)
        category = entry.category if entry else "note"
        return os.path.join(self._base_dir, category, f"{entry_id}.json")

    def _save_entry(self, entry_id: str, entry: KnowledgeEntry) -> None:
        """保存条目到文件。

        Args:
            entry_id: 条目 ID。
            entry: 知识条目。
        """
        filepath = self._get_filepath(entry_id)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """从文件加载条目。

        Args:
            entry_id: 条目 ID。

        Returns:
            Optional[KnowledgeEntry]: 知识条目。
        """
        # 尝试在所有分类目录中查找
        for category in ("skill", "readme", "note"):
            filepath = os.path.join(self._base_dir, category, f"{entry_id}.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return KnowledgeEntry.from_dict(data)
                except (json.JSONDecodeError, KeyError):
                    pass
        return None
