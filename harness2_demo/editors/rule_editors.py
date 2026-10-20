"""规则驱动编辑器组：每个编辑器只盯一类可观察失败（单一职责）。

映射关系就是这份提示词真实迭代史的提炼：
  v1 宽松 -> 收了数据盘点等 -> 补「只收事件」（EventTypeEditor）
  旧闻混入 -> 收紧窗口到 48h（WindowEditor）
  同事件多家重复 -> 开去重（DedupEditor）
  盘点站内容混入 -> 有编辑器提议「只认官方」（OfficialOnlySourceEditor，
    本演示中它会被 Compose 以「合规收录下降」拒绝，演示过度收紧的代价）
  来源不可识别 -> 改分级来源（TieredSourceEditor）
  匿名社交来源 -> 要求具名（NamedSourceEditor，第二期任务才触发）
新增一类失败处理 = 新增一个编辑器类并注册，runner 不用改（开闭原则）。
"""

from __future__ import annotations

from ..domain import Metrics
from ..harness import Harness
from .base import Edit


class EventTypeEditor:
    name = "event_type"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        if metrics.non_event == 0 or harness.guardrails.event_only:
            return []
        return [
            Edit(
                name="event_only",
                title="开启「只收事件」：非技术/产品事件一律不收",
                changes={"event_only": True},
                prompt_clause="只收录技术 / 产品事件：新协议、新版本、协议升级、治理提案、开源项目发布；数据盘点、趋势综述、融资、行情一律不收",
                lesson_text="只收事件类型能拦下数据盘点、趋势综述、融资与行情条目——它们伪装成「动态」，实则不是事件",
            )
        ]


class WindowEditor:
    name = "window"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        if metrics.out_of_window == 0 or harness.guardrails.window_hours <= 48:
            return []
        return [
            Edit(
                name="window_48",
                title="执行窗口收紧到 48 小时",
                changes={"window_hours": 48},
                prompt_clause="只收录最近 48 小时内发布的动态，窗口外的旧闻不收",
                lesson_text="窗口必须与业务口径（48 小时）对齐，宽松窗口会把旧闻当新闻放进来",
            )
        ]


class DedupEditor:
    name = "dedup"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        if metrics.duplicates == 0 or harness.guardrails.dedup:
            return []
        return [
            Edit(
                name="dedup",
                title="开启同事件去重：多来源只保留一条（官方优先）",
                changes={"dedup": True},
                prompt_clause="同一事件被多个来源报道时只保留一条，以官方来源为准",
                lesson_text="同一事件的多来源报道必须按事件合并去重，否则简报会被同一件事刷屏",
            )
        ]


class OfficialOnlySourceEditor:
    """保守编辑器：见盘点站混入就提议「来源只认官方」。

    它代表真实迭代中很容易出现的一种过度反应。提议本身没错，
    错在代价——本演示里它会被行为对照拒绝，拒绝证据会写进改进库。
    """

    name = "official_only"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        if metrics.pandian == 0 or harness.guardrails.source_policy != "all":
            return []
        return [
            Edit(
                name="source_official_only",
                title="来源收紧为「仅官方」（保守提议）",
                changes={"source_policy": "official_only"},
                prompt_clause="来源只认官方渠道",
                lesson_text="来源只认官方可以清零来源问题",
                lesson_text_on_reject="来源不能一刀切只认官方：大量合规事件只有社交 / 资讯来源，只认官方会成片漏收",
            )
        ]


class TieredSourceEditor:
    name = "tiered_source"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        if metrics.source_problem == 0 or harness.guardrails.source_policy != "all":
            return []
        return [
            Edit(
                name="source_tiered",
                title="来源改分级：官方 / 社交 / 资讯可收，盘点站与未知不收",
                changes={"source_policy": "tiered"},
                prompt_clause="来源分级：官方源、社交平台、资讯平台都可收录；盘点站与来源不明的条目不收",
                lesson_text="来源按可识别性分级（官方 / 社交 / 资讯可收，盘点站与未知不收），既拦下来源问题、又不误伤只有社交 / 资讯来源的合规事件",
            )
        ]


class NamedSourceEditor:
    name = "named_source"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        if metrics.anonymous == 0 or harness.guardrails.require_named_source:
            return []
        return [
            Edit(
                name="require_named_source",
                title="要求具名来源：匿名账号发布的内容不算可识别来源",
                changes={"require_named_source": True},
                prompt_clause="社交平台来源必须有具名发布者（官方账号、具名研究者 / 开发者），匿名账号的内容不收",
                lesson_text="社交来源必须有具名发布者：类别对了但发布者匿名，同样无法溯源、无法担责",
            )
        ]


def default_editors() -> list:
    """演示用的编辑器注册表（组合根在 CLI 层组装，顺序即探测顺序）。"""
    return [
        EventTypeEditor(),
        WindowEditor(),
        DedupEditor(),
        OfficialOnlySourceEditor(),
        TieredSourceEditor(),
        NamedSourceEditor(),
    ]
