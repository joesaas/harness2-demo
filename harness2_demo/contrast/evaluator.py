"""行为评估器：只看产出条目的可观察属性算指标，不做真值打分。

这是 Harness² 任务级递归的关键设定：开放世界里没有标准答案，
但「收进来的条目是不是数据盘点、是不是窗口外的旧闻、同一事件
有没有重复收」都是可直接观察的行为事实，足以指导编辑取舍。
"""

from __future__ import annotations

from typing import Protocol, Sequence

from ..domain import BUSINESS_WINDOW_HOURS, EVENT_TYPES, Metrics, NewsItem
from ..executor.base import Briefing


class Evaluator(Protocol):
    """评估器接口：给语料与简报，算行为指标。"""

    def evaluate(self, corpus: Sequence[NewsItem], briefing: Briefing) -> Metrics:
        ...


class BehaviorEvaluator:
    """Evaluator 的行为对照实现。"""

    def evaluate(self, corpus: Sequence[NewsItem], briefing: Briefing) -> Metrics:
        included = briefing.items
        corpus_groups = {it.event_group for it in corpus if it.ground_truth_compliant}
        included_compliant_groups = {
            it.event_group for it in included if it.ground_truth_compliant
        }
        return Metrics(
            included=len(included),
            compliant_groups=len(included_compliant_groups),
            corpus_compliant_groups=len(corpus_groups),
            non_event=sum(1 for it in included if it.content_type not in EVENT_TYPES),
            out_of_window=sum(
                1 for it in included if it.hours_ago > BUSINESS_WINDOW_HOURS
            ),
            duplicates=len(included) - len({it.event_group for it in included}),
            source_problem=sum(1 for it in included if not it.source_identifiable),
            anonymous=sum(1 for it in included if not it.source_name.strip()),
            pandian=sum(1 for it in included if it.source_category == "盘点站"),
        )
