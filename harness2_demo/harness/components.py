"""驾驭层组件：Harness² 的八类可编辑组件在本场景的落地。

对应关系（详见 README 对应表）：
- system prompt  -> PromptComponent（版本化文本，被编辑器改、随任务携带）
- guardrails     -> Guardrails（收录 / 排除规则开关组，执行器真正执行的规则）
- skills         -> SkillsComponent（运行时侧重表，影响简报排序）
- memory         -> Harness.lessons（本轮加载的改进库教训快照；存储在 library 模块）
- 其余四类（tool guidance / subagents / scripts / plugins）在本场景以
  Guardrails 的规则项与执行器实现承载，README 里有逐项说明。

设计要点：所有组件都是不可变数据（frozen dataclass），修改一律通过
dataclasses.replace 生成新对象——驾驭层的每次演进都是一个新版本，
旧版本不被原地改写，便于对照与回滚。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class Guardrails:
    """收录 / 排除规则开关组：提示词规则的机器可读孪生。

    执行器只读这一组开关执行筛选；编辑器改的也是这一组开关，
    同时把对应的自然语言条款同步进 PromptComponent。
    """

    event_only: bool = False  # 只收事件类型（技术事件 / 治理提案）
    window_hours: int = 168  # 执行窗口（小时）；出厂值一周，故意宽松
    source_policy: str = "all"  # all | official_only | tiered（分级）
    dedup: bool = False  # 同事件多来源是否去重合并
    require_named_source: bool = False  # 社交等来源是否必须有具名发布者
    max_per_topic: int = 20  # 每主题条数上限

    def describe(self) -> str:
        policy = {
            "all": "来源不限",
            "official_only": "来源仅官方",
            "tiered": "来源分级（官方/社交/资讯可收，盘点站/未知不收）",
        }[self.source_policy]
        return (
            f"只收事件={'开' if self.event_only else '关'}，"
            f"窗口={self.window_hours}h，{policy}，"
            f"去重={'开' if self.dedup else '关'}，"
            f"要求具名来源={'开' if self.require_named_source else '关'}，"
            f"每主题上限={self.max_per_topic}"
        )


@dataclass(frozen=True)
class PromptComponent:
    """版本化提示词正文：基础任务句 + 一组规则条款。

    版本号只在 Compose 采纳编辑、或改进库教训被应用时递增，
    与 Guardrails 的变化一一对应（同一组编辑同步改两处）。
    """

    version: int = 1
    clauses: tuple[str, ...] = ()

    def render(self) -> str:
        lines = [f"（提示词 v{self.version}）收集最近 2 天 AI Agent 与 Web3 DeFi 协议的技术 / 产品动态："]
        lines += [f"{i}. {c}" for i, c in enumerate(self.clauses, start=1)]
        return "\n".join(lines)

    def extended(self, new_clauses: list[str]) -> "PromptComponent":
        """采纳编辑后生成新版本：版本号 +1，条款追加。"""
        return replace(
            self,
            version=self.version + 1,
            clauses=self.clauses + tuple(new_clauses),
        )


# 各运行时的侧重来源类别（沿用提示词 v5 的运行时侧重表）。
_DEFAULT_FOCUS: dict[str, tuple[str, ...]] = {
    "grok": ("社交",),  # Grok Bot 侧重 X 平台牛人动态
    "gemini": ("官方", "资讯"),  # Gemini 侧重官方长文与治理提案
    "chatgpt": ("资讯",),  # ChatGPT 侧重综合新闻面
    "muse": ("官方",),  # Muse 侧重 GitHub 与技术源
}


@dataclass(frozen=True)
class SkillsComponent:
    """运行时侧重表（对应 Harness² 的 skills 组件）。

    执行器用它决定简报内的排序优先：侧重类别的条目排在前面。
    本演示中它只参与执行（排序），不被编辑器修改。
    """

    focus: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: MappingProxyType(dict(_DEFAULT_FOCUS))
    )

    def preferred_categories(self, runtime: str) -> tuple[str, ...]:
        return self.focus.get(runtime, ())


@dataclass(frozen=True)
class Harness:
    """一版完整的驾驭层：提示词 + 规则 + 侧重表 + 已加载的教训快照。

    对外只暴露整体替换式的方法（apply_changes / with_prompt / with_lessons），
    调用方不需要知道内部字段结构（迪米特法则）。
    """

    prompt: PromptComponent
    guardrails: Guardrails
    skills: SkillsComponent = field(default_factory=SkillsComponent)
    runtime: str = "muse"
    lessons: tuple = ()  # tuple[Lesson, ...]，避免与 library 模块循环导入故不标注类型

    def apply_changes(self, changes: dict) -> "Harness":
        """按字段名把一组规则改动应用到 Guardrails，返回新 Harness。"""
        return replace(self, guardrails=replace(self.guardrails, **changes))

    def with_prompt(self, prompt: PromptComponent) -> "Harness":
        return replace(self, prompt=prompt)

    def with_lessons(self, lessons: tuple) -> "Harness":
        return replace(self, lessons=lessons)

    def describe(self) -> str:
        return f"prompt v{self.prompt.version}；{self.guardrails.describe()}"
