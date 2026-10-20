"""Compose（拼装）：逐条探测编辑，按明确规则决定采纳哪些，拼出新版驾驭层。

采纳规则（写死在这里，全文唯一出处）：
  候选版相对当前版，违规总数严格下降，且合规事件收录不下降，才采纳。
后半句是护栏：防止出现「靠少收东西把违规刷下去」的假改进——
本演示里「来源只认官方」就是被这条规则挡下的过度收紧。
逐条贪心：采纳后当前版随之更新，下一条编辑在新当前版上探测。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..domain import Metrics, NewsItem
from ..editors.base import Edit
from ..harness import Harness
from .probe import ProbeRow, ProbeRunner


@dataclass(frozen=True)
class ComposeResult:
    harness: Harness  # 拼装后的新版驾驭层
    rows: tuple[ProbeRow, ...]  # 全部对照行（含被拒绝的）
    base_metrics: Metrics  # 拼装前指标
    final_metrics: Metrics  # 拼装后指标

    @property
    def adopted(self) -> list[Edit]:
        return [r.edit for r in self.rows if r.adopted]

    @property
    def rejected(self) -> list[ProbeRow]:
        return [r for r in self.rows if not r.adopted]


class Composer:
    def __init__(self, probe: ProbeRunner):
        self._probe = probe

    def compose(
        self, harness: Harness, edits: Sequence[Edit], corpus: Sequence[NewsItem]
    ) -> ComposeResult:
        current = harness
        current_metrics = self._probe.evaluate(current, corpus)
        base_metrics = current_metrics
        rows: list[ProbeRow] = []

        for edit in edits:
            candidate, m = self._probe.run_candidate(current, edit, corpus)
            adopted, reason = self._decide(current_metrics, m)
            rows.append(ProbeRow(edit, current_metrics, m, adopted, reason))
            if adopted:
                current, current_metrics = candidate, m

        if any(r.adopted for r in rows):
            clauses = [r.edit.prompt_clause for r in rows if r.adopted and r.edit.prompt_clause]
            current = current.with_prompt(current.prompt.extended(clauses))

        return ComposeResult(current, tuple(rows), base_metrics, current_metrics)

    @staticmethod
    def _decide(before: Metrics, after: Metrics) -> tuple[bool, str]:
        if after.compliant_groups < before.compliant_groups:
            return (
                False,
                f"拒绝：合规事件收录下降（{before.compliant_groups} → {after.compliant_groups}），"
                "违规下降是靠少收换来的，不算改进",
            )
        if after.total_violations >= before.total_violations:
            return (
                False,
                f"拒绝：违规总数没有下降（{before.total_violations} → {after.total_violations}），无增益",
            )
        return (
            True,
            f"采纳：违规总数 {before.total_violations} → {after.total_violations}，"
            f"合规事件收录保持 {after.compliant_groups}",
        )
