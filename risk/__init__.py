"""风险识别模块。

对代码操作进行风险评估，分为四个等级：
- CRITICAL: 系统级破坏
- HIGH: 数据风险
- MEDIUM: 配置风险
- LOW: 普通操作
"""

from .analyzer import RiskAnalyzer, RiskLevel, RiskResult, analyze_risk

__all__ = ["RiskAnalyzer", "RiskLevel", "RiskResult", "analyze_risk"]
