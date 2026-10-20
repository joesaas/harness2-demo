"""Probe（探测）：把一条候选编辑先单独应用到当前驾驭层，跑同一任务看行为变化。

探测不改动当前驾驭层——候选版是临时构造的新对象，跑完即弃，
是否采纳由 Composer 决定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..domain import Metrics, NewsItem
from ..editors.base import Edit
from ..executor.base import Executor
from ..harness import Harness
from .evaluator import Evaluator


@dataclass(frozen=True)
class ProbeRow:
    """对照表的一行：一条编辑在当前版上的探测结果。"""

    edit: Edit
    before: Metrics
    after: Metrics
    adopted: bool
    reason: str  # 采纳 / 拒绝的人类可读理由（拒绝时尤其要写清证据）


class ProbeRunner:
    """只依赖 Executor 与 Evaluator 两个抽象（依赖倒置）。"""

    def __init__(self, executor: Executor, evaluator: Evaluator):
        self._executor = executor
        self._evaluator = evaluator

    def run_candidate(
        self, harness: Harness, edit: Edit, corpus: Sequence[NewsItem]
    ) -> tuple[Harness, Metrics]:
        candidate = harness.apply_changes(edit.changes)
        metrics = self._evaluator.evaluate(corpus, self._executor.run(candidate, corpus))
        return candidate, metrics

    def evaluate(self, harness: Harness, corpus: Sequence[NewsItem]) -> Metrics:
        return self._evaluator.evaluate(corpus, self._executor.run(harness, corpus))
