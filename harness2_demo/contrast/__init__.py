"""对照包：行为评估（Evaluator）、逐条探测（Probe）与拼装（Compose）。"""

from .compose import ComposeResult, Composer
from .evaluator import BehaviorEvaluator, Evaluator
from .probe import ProbeRow, ProbeRunner

__all__ = [
    "BehaviorEvaluator",
    "ComposeResult",
    "Composer",
    "Evaluator",
    "ProbeRow",
    "ProbeRunner",
]
