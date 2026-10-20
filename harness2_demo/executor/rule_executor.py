"""规则执行器：按 Guardrails 对候选语料做确定性筛选 / 去重 / 排序。

纯规则、无随机、无外部依赖：同一驾驭层 + 同一语料永远产出同一简报，
这是行为对照（probe）能成立的前提。
"""

from __future__ import annotations

from typing import Sequence

from ..domain import EVENT_TYPES, SOURCE_RANK, NewsItem
from ..harness import Harness
from .base import Briefing

# 来源分级（tiered）策略下允许的类别：能识别主体的一、二、三级来源。
_TIERED_ALLOWED = frozenset({"官方", "社交", "资讯"})


class RuleExecutor:
    """Executor 的规则实现。"""

    def run(self, harness: Harness, items: Sequence[NewsItem]) -> Briefing:
        g = harness.guardrails
        kept = [it for it in items if self._passes(it, g)]
        if g.dedup:
            kept = self._dedup(kept)
        kept = self._sort(kept, harness)
        kept = self._cap_per_topic(kept, g.max_per_topic)
        return Briefing(items=tuple(kept), prompt_version=harness.prompt.version)

    # ---- 筛选 ------------------------------------------------------------
    def _passes(self, item: NewsItem, g) -> bool:
        if g.event_only and item.content_type not in EVENT_TYPES:
            return False
        if item.hours_ago > g.window_hours:
            return False
        if g.source_policy == "official_only" and item.source_category != "官方":
            return False
        if g.source_policy == "tiered" and item.source_category not in _TIERED_ALLOWED:
            return False
        if g.require_named_source and not item.source_name.strip():
            return False
        return True

    # ---- 去重 ------------------------------------------------------------
    def _dedup(self, items: list[NewsItem]) -> list[NewsItem]:
        """同事件只保留一条：来源等级高者优先，其次更新者，再其次 id 小者。"""
        best: dict[str, NewsItem] = {}
        for it in items:
            cur = best.get(it.event_group)
            if cur is None or self._dedup_key(it) < self._dedup_key(cur):
                best[it.event_group] = it
        return list(best.values())

    @staticmethod
    def _dedup_key(item: NewsItem):
        return (SOURCE_RANK[item.source_category], item.hours_ago, item.id)

    # ---- 排序 ------------------------------------------------------------
    def _sort(self, items: list[NewsItem], harness: Harness) -> list[NewsItem]:
        """简报内排序：先按主题（defi 在前），主题内侧重来源优先、再按新近程度。

        侧重表来自 SkillsComponent——这是 skills 组件参与执行的地方。
        """
        preferred = harness.skills.preferred_categories(harness.runtime)
        topic_order = {"defi": 0, "agent": 1}

        def key(it: NewsItem):
            return (
                topic_order.get(it.topic, 9),
                0 if it.source_category in preferred else 1,
                it.hours_ago,
                it.id,
            )

        return sorted(items, key=key)

    # ---- 条数上限 ----------------------------------------------------------
    @staticmethod
    def _cap_per_topic(items: list[NewsItem], cap: int) -> list[NewsItem]:
        counts: dict[str, int] = {}
        out: list[NewsItem] = []
        for it in items:
            if counts.get(it.topic, 0) >= cap:
                continue
            counts[it.topic] = counts.get(it.topic, 0) + 1
            out.append(it)
        return out
