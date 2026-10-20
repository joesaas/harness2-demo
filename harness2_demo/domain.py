"""领域模型：候选新闻条目与行为指标。

本模块只放数据定义，不依赖任何其他模块（被所有模块依赖，自身零依赖）。
指标全部来自产出条目的「可观察属性」——内容类型、距今小时数、来源类别、
来源名、事件分组键——不使用真值打分，这正是 Harness² 行为对照的思想。
"""

from __future__ import annotations

from dataclasses import dataclass

# 业务口径：提示词只收录「技术 / 产品事件」，在本场景里落实为这两类。
EVENT_TYPES = frozenset({"技术事件", "治理提案"})

# 可识别来源类别：能说清是谁发布的。盘点站与未知来源不算可识别。
KNOWN_SOURCE_CATEGORIES = frozenset({"官方", "社交", "资讯"})

# 同事件多来源去重时保留哪一条：官方优先，其次资讯、社交。
SOURCE_RANK = {"官方": 0, "资讯": 1, "社交": 2, "盘点站": 3, "未知": 4}

# 业务窗口：最近 2 天。评估违规与否以这个业务口径为准，与驾驭层里
# 可被编辑的 window_hours（执行器实际用的窗口）是两回事。
BUSINESS_WINDOW_HOURS = 48


@dataclass(frozen=True)
class NewsItem:
    """一条候选新闻（fixture 语料的最小单元）。"""

    id: str
    title: str
    topic: str  # "defi" | "agent"
    content_type: str  # 技术事件 / 治理提案 / 数据盘点 / 趋势综述 / 融资 / 行情 / 营销软文 / 旧闻重发
    hours_ago: int  # 距今小时数（构造数据，非真实时间）
    source_category: str  # 官方 / 社交 / 资讯 / 盘点站 / 未知
    source_name: str  # 具名来源；匿名来源为空字符串
    event_group: str  # 同一事件的多个来源共用同一个分组键

    @property
    def is_event(self) -> bool:
        return self.content_type in EVENT_TYPES

    @property
    def source_identifiable(self) -> bool:
        """来源可识别：类别可识别且有具名发布者。"""
        return (
            self.source_category in KNOWN_SOURCE_CATEGORIES
            and bool(self.source_name.strip())
        )

    @property
    def ground_truth_compliant(self) -> bool:
        """按业务口径，这条是否「本应被收录」。

        只用于评估行为指标（合规收录数），执行器本身看不到这个标记——
        执行器只能按驾驭层规则筛选，这正是要演示的差距所在。
        """
        return (
            self.is_event
            and self.hours_ago <= BUSINESS_WINDOW_HOURS
            and self.source_identifiable
        )


@dataclass(frozen=True)
class Metrics:
    """一期简报的行为指标：全部由被收录条目的可观察属性算出。"""

    included: int = 0  # 实际收录条数
    compliant_groups: int = 0  # 收录到的合规事件数（按事件组去重计数）
    corpus_compliant_groups: int = 0  # 语料里合规事件总数（按事件组计数）
    non_event: int = 0  # 违规：收录了非事件类型（数据盘点 / 趋势 / 融资 / 行情等）
    out_of_window: int = 0  # 违规：收录了业务窗口（48h）之外的条目
    duplicates: int = 0  # 违规：同事件重复收录的冗余条数
    source_problem: int = 0  # 违规：收录了来源不可识别的条目
    anonymous: int = 0  # 来源问题细分：来源名为空（匿名）
    pandian: int = 0  # 来源问题细分：来自盘点站

    @property
    def total_violations(self) -> int:
        return self.non_event + self.out_of_window + self.duplicates + self.source_problem

    @property
    def missed_compliant(self) -> int:
        """漏收的合规事件数（按事件组）。"""
        return self.corpus_compliant_groups - self.compliant_groups
