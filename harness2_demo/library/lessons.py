"""教训（Lesson）与存储接口：驾驭级递归的载体。

一条教训不只是文本——它带三样东西：
- text：给人看的经验表述；
- evidence：产生它的行为证据（哪期任务、哪个指标从几变到几），
  没有证据的教训不许进库，这是 Harness²「有证据的教训」的要求；
- effect：机器可应用的规则改动（Guardrails 字段 -> 值）。
  effect 为空的教训是「负教训」（记录不要做什么），应用时跳过，
  但保留在库里供人检视。靠 effect，下一个任务才能把教训变成配置，
  而不是只把文本读一遍。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Lesson:
    id: str  # 如 "L1"，全库递增
    text: str
    evidence: str
    source_task: str  # 产生它的任务名
    created_at: str  # ISO 时间字符串（由注入的时钟产生，保证测试可确定）
    effect: dict  # Guardrails 改动；空 dict 表示负教训

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "evidence": self.evidence,
            "source_task": self.source_task,
            "created_at": self.created_at,
            "effect": self.effect,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Lesson":
        return cls(
            id=d["id"],
            text=d["text"],
            evidence=d["evidence"],
            source_task=d["source_task"],
            created_at=d["created_at"],
            effect=dict(d.get("effect") or {}),
        )


class LessonStore(Protocol):
    """改进库存储接口：runner 只依赖 load / save 两个动作。

    JSON 文件是一种实现；换成数据库或远程服务时 runner 不用改。
    """

    def load(self) -> list[Lesson]:
        ...

    def save(self, lessons: list[Lesson]) -> None:
        ...
