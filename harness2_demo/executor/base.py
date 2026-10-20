"""执行器接口（Protocol）：runner 只依赖这个接口，不依赖具体实现。

将来把规则执行器换成「真调模型的执行器」时，只要实现同一接口，
runner、编辑器、对照逻辑都不用改（里氏替换 / 依赖倒置）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ..domain import NewsItem
from ..harness import Harness


@dataclass(frozen=True)
class Briefing:
    """一期简报：被收录的条目 + 产出时所用的驾驭层版本号。"""

    items: tuple[NewsItem, ...]
    prompt_version: int

    def count_by_topic(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.topic] = counts.get(item.topic, 0) + 1
        return counts


class Executor(Protocol):
    """执行器：用给定驾驭层跑一期收集，产出简报。"""

    def run(self, harness: Harness, items: Sequence[NewsItem]) -> Briefing:
        ...
