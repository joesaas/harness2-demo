"""LLM 编辑器占位：与规则编辑器实现同一 Editor 接口，本演示不实现。

将来接入方式（接口已留好，runner 与 Composer 无需改动）：
  1. 把当前提示词全文、上一轮 Metrics、被误收 / 漏收的样本条目
     拼成上下文，交给一个 LLM 生成候选编辑（仍须产出 Edit 数据：
     changes 限定为 Guardrails 已知字段，prompt_clause 为条款文本）；
  2. 候选编辑照常走 Probe / Compose 的行为对照——LLM 只负责提议，
     采纳权仍在对照规则手里，这正是 Harness² 不依赖真值的关键：
     提议者可以换，对照与拼装的标准不变。

现在 propose 恒返回空列表：注册它不改变演示行为，仅证明接口可替换。
"""

from __future__ import annotations

from ..domain import Metrics
from ..harness import Harness
from .base import Edit


class LlmEditor:
    name = "llm"

    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        return []
