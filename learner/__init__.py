"""学习模块。

管理本地知识库，包括：
- Skill 文件：记录学到的技能和经验
- README：项目理解
- 笔记：踩坑记录和心得
"""

from .knowledge import KnowledgeBase, KnowledgeEntry

__all__ = ["KnowledgeBase", "KnowledgeEntry"]
