"""LLM 编辑器：live 模式的真实提议者，与规则编辑器同属 Editor 角色。

两个入口，分工明确：
- propose(metrics, harness)：Editor 协议入口。离线注册表里它保持
  占位行为（恒不提议）——离线 Metrics 是 fixture 口径，LLM 编辑器
  无从据此产出 Guardrails 编辑；注册它只为证明接口可替换。
- revise(prompt_text, metrics, examples)：live 流程的真实入口。
  把当前提示词全文、汇总行为指标、违规样例（标题 + judge 理由）
  发给编辑模型，收回「修订后的提示词全文 + 改动清单」。
  返回 JSON 解析失败或调用失败 -> 返回 None（本轮无编辑），
  只记事件、不崩流程——提议者可以失灵，编排不能。

与规则编辑器相同的不变量：它只有提议权。修订版必须在同一批
语料上重跑（Probe），由 Compose 按行为指标决定采纳与否。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contrast.live_evaluator import LiveMetrics
from ..domain import Metrics, ViolationExample
from ..harness import Harness
from ..llm import OpenRouterClient, OpenRouterError, extract_json
from .base import Edit

EDITOR_SYSTEM = (
    "你是一名提示词编辑。下面给你一份新闻收集提示词的当前全文、它上一轮"
    "运行的行为指标（违规收录多为 judge 模型判定，属估计）和违规样例。"
    "请修订提示词全文：目标是减少违规收录，同时尽量保住合规收录；"
    "不要改变任务本身与主题范围，不要虚构原文没有的栏目结构。"
    "只返回一个 JSON 对象，不要输出其它文字："
    "{\"prompt\": \"修订后的提示词全文\", \"changes\": [{\"section\": \"改了哪一节\", "
    "\"why\": \"为什么这样改\", \"metric\": \"对应哪个指标\"}]}"
)


@dataclass(frozen=True)
class PromptChange:
    section: str  # 改了哪一节
    why: str  # 为什么改
    metric: str  # 对应哪个行为指标


@dataclass(frozen=True)
class PromptRevision:
    """一次全文修订提议：新全文 + 改动清单（逐条说明依据）。"""

    new_prompt: str
    changes: tuple[PromptChange, ...]


class LlmEditor:
    name = "llm"

    def __init__(
        self,
        client: OpenRouterClient | None = None,
        model: str | None = None,
        *,
        max_tokens: int | None = 6000,
    ):
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    # -- Editor 协议入口（离线注册表占位，见模块 docstring） --------------
    def propose(self, metrics: Metrics, harness: Harness) -> list[Edit]:
        return []

    # -- live 入口 ------------------------------------------------------------
    def revise(
        self,
        prompt_text: str,
        metrics: LiveMetrics,
        examples: list[ViolationExample],
    ) -> PromptRevision | None:
        if self._client is None or self._model is None:
            return None
        metrics_text = (
            f"被选 {metrics.selected} 条；幻觉条目 {metrics.hallucinated}；"
            f"重复 {metrics.duplicates}；违规收录（judge 判 non-event）{metrics.violations}；"
            f"合规收录（judge 判 event）{metrics.compliant}；"
            f"judge 未判定 {metrics.judge_failed}"
        )
        examples_text = "\n".join(
            f"- [{ex.kind}] {ex.title} —— judge 理由：{ex.reason}" for ex in examples
        ) or "（无违规样例）"
        messages = [
            {"role": "system", "content": EDITOR_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"【行为指标】{metrics_text}\n\n【违规样例】\n{examples_text}\n\n"
                    f"【当前提示词全文】\n{prompt_text}"
                ),
            },
        ]
        try:
            text = self._client.chat(self._model, messages, max_tokens=self._max_tokens)
        except OpenRouterError:
            return None
        data = extract_json(text)
        if not isinstance(data, dict):
            return None
        new_prompt = data.get("prompt")
        if not isinstance(new_prompt, str) or not new_prompt.strip():
            return None
        changes: list[PromptChange] = []
        raw_changes = data.get("changes")
        if isinstance(raw_changes, list):
            for obj in raw_changes:
                if isinstance(obj, dict):
                    changes.append(
                        PromptChange(
                            section=str(obj.get("section") or ""),
                            why=str(obj.get("why") or ""),
                            metric=str(obj.get("metric") or ""),
                        )
                    )
        return PromptRevision(new_prompt=new_prompt.strip(), changes=tuple(changes))
