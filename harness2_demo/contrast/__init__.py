"""对照包：行为评估（Evaluator）、逐条探测（Probe）与拼装（Compose）。

live 侧另有 JudgeEvaluator（程序检查 + judge 模型判定）与 LiveMetrics。
"""

from .compose import ComposeResult, Composer
from .evaluator import BehaviorEvaluator, Evaluator
from .live_evaluator import (
    JudgedEntry,
    JudgeEvaluator,
    Judgement,
    LiveEvaluation,
    LiveMetrics,
    compute_metrics,
)
from .probe import ProbeRow, ProbeRunner

__all__ = [
    "BehaviorEvaluator",
    "ComposeResult",
    "Composer",
    "Evaluator",
    "JudgeEvaluator",
    "JudgedEntry",
    "Judgement",
    "LiveEvaluation",
    "LiveMetrics",
    "ProbeRow",
    "ProbeRunner",
    "compute_metrics",
]
