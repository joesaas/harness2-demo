"""编辑器接口与「编辑」数据：一类失败对应一类编辑提议。

Edit 是纯数据：改哪些 Guardrails 字段、同步进提示词的条款文本、
以及这条编辑被采纳（或被拒）后应沉淀成什么教训。编辑器只负责
「提议」，采不采由 Composer 按行为对照决定——提议与决策分离。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain import Metrics
from ..harness import Harness


@dataclass(frozen=True)
class Edit:
    name: str  # 机器名，如 "event_only"
    title: str  # 人类可读标题
    changes: dict  # Guardrails 字段名 -> 新值
    prompt_clause: str  # 采纳后同步写入提示词的条款（被拒则不写）
    lesson_text: str  # 采纳后写入改进库的教训
    lesson_text_on_reject: str | None = None  # 被拒时要沉淀的教训（如「不要过度收紧」）


class Editor(Protocol):
    """编辑器接口：看指标与当前驾驭层，提议零条或多条编辑。

    接口刻意最小（接口隔离）：编辑器不需要知道执行器、存储、CLI。
    规则编辑器与将来 LLM 编辑器实现同一接口，可互换（里氏替换）。
    """

    name: str

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        ...
