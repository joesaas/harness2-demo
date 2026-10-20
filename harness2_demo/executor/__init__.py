"""执行器包：按驾驭层配置对候选语料做筛选/整理，产出一期简报。

两种实现同一角色：RuleExecutor（离线规则）与 LlmExecutor（live 真模型）。
"""

from .base import Briefing, Executor
from .llm_executor import LiveBriefing, LlmExecutor, ModelRunRecord, SelectedEntry
from .rule_executor import RuleExecutor

__all__ = [
    "Briefing",
    "Executor",
    "LiveBriefing",
    "LlmExecutor",
    "ModelRunRecord",
    "RuleExecutor",
    "SelectedEntry",
]
