"""真实执行器 LlmExecutor：同一份提示词，三个模型各整理一期简报。

它与 RuleExecutor 是同一「执行器」角色的两种实现：一边是规则对
fixture 的确定性筛选，一边是真模型对真实语料的整理——编排层
（runner）看到的都是「驾驭层 + 候选 -> 简报」。live 侧的数据类型
是 CandidateItem / LiveBriefing（候选没有内容类型、产出是模型
生成的条目），故不与离线 Briefing 共用类，但契约形状一致。

调用方式：对每个模型发一次 chat——system = 当前驾驭层提示词全文
+ 该运行时的侧重说明 + 输出格式约束；user = 候选条目 JSON 列表。
要求模型只返回 JSON 数组。解析容错：提取失败 / 模型报错都记为
该模型的执行失败事件，单模型翻车不拖垮整期。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from ..domain import CandidateItem
from ..harness import Harness
from ..llm import ModelSet, OpenRouterClient, OpenRouterError, extract_json

# 运行时侧重说明：沿用提示词 v5 的侧重表（grok 盯社交、gemini 盯
# 官方长文、chatgpt 盯综合新闻面），执行时拼在 system 末尾。
FOCUS_NOTES: dict[str, str] = {
    "grok": "本运行时（Grok）侧重 X 平台与社交来源：核心人物（项目创始人、研究员、头部开发者）关于产品与技术的动态发言优先，并注明发言人身份；不收行情喊单与情绪帖。",
    "gemini": "本运行时（Gemini）侧重深度检索官方长文来源：协议治理提案、官方博客、研究论文与文档更新优先。",
    "chatgpt": "本运行时（ChatGPT）侧重综合新闻面：主流媒体与资讯平台报道的产品发布与大公司动态优先。",
}

OUTPUT_SPEC = (
    "【输出格式（强制）】只返回一个 JSON 数组，不要输出任何其它文字或解释。"
    "数组每项字段：title（条目标题，照抄候选）、topic（\"defi\" 或 \"agent\"）、"
    "one_liner（一句话说清发生了什么）、detail（2-3 句细节）、"
    "link（候选条目的链接，必须逐字照抄）、date（发布日期，知道则填，不知道填空字符串）。"
    "只能从给定候选条目中选择，不得编造候选之外的条目或链接。"
)


@dataclass(frozen=True)
class SelectedEntry:
    """模型选出的一条简报条目。candidate 为按 link 匹配回的候选；
    匹配不到（模型编造或改写了链接）为 None——这是幻觉指标的抓手。"""

    title: str
    topic: str
    one_liner: str
    detail: str
    link: str
    date: str
    model_alias: str
    candidate: CandidateItem | None


@dataclass(frozen=True)
class ModelRunRecord:
    """一次模型执行留痕：编辑器与报告都看它（哪个模型、多久、成败）。"""

    alias: str
    model: str
    elapsed_s: float
    raw_chars: int  # 原始返回长度（字符）
    status: str  # ok | parse_failed | error
    error: str = ""


@dataclass(frozen=True)
class LiveBriefing:
    """一期 live 简报：每模型一份 + 按 link 去重的合并视图 + 全部留痕。"""

    by_model: dict[str, tuple[SelectedEntry, ...]]
    merged: tuple[SelectedEntry, ...]
    records: tuple[ModelRunRecord, ...]
    prompt_version: int

    def entries_of(self, alias: str) -> tuple[SelectedEntry, ...]:
        return self.by_model.get(alias, ())


class LlmExecutor:
    """Executor 角色的 live 实现。client 可注入（测试用假 client）。"""

    def __init__(
        self,
        client: OpenRouterClient,
        models: ModelSet,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_tokens: int | None = 4096,
    ):
        self._client = client
        self._models = models
        self._clock = clock
        self._max_tokens = max_tokens

    def run(self, harness: Harness, candidates: Sequence[CandidateItem]) -> LiveBriefing:
        prompt_text = harness.prompt.render()
        user = json.dumps(
            [self._candidate_dict(c) for c in candidates], ensure_ascii=False
        )
        by_link = {c.link.strip(): c for c in candidates}
        by_model: dict[str, tuple[SelectedEntry, ...]] = {}
        records: list[ModelRunRecord] = []

        for alias, model in self._models.executor_models():
            system = "\n\n".join(
                [prompt_text, f"【运行时侧重】{FOCUS_NOTES.get(alias, '')}", OUTPUT_SPEC]
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            start = self._clock()
            try:
                text = self._client.chat(model, messages, max_tokens=self._max_tokens)
            except OpenRouterError as e:
                records.append(
                    ModelRunRecord(alias, model, self._clock() - start, 0, "error", str(e))
                )
                by_model[alias] = ()
                continue
            entries, status, error = self._parse_entries(text, alias, by_link)
            records.append(
                ModelRunRecord(alias, model, self._clock() - start, len(text), status, error)
            )
            by_model[alias] = tuple(entries)

        merged: list[SelectedEntry] = []
        seen_links: set[str] = set()
        for alias, _model in self._models.executor_models():
            for entry in by_model[alias]:
                key = entry.link.strip()
                if key in seen_links:
                    continue
                seen_links.add(key)
                merged.append(entry)

        return LiveBriefing(
            by_model=by_model,
            merged=tuple(merged),
            records=tuple(records),
            prompt_version=harness.prompt.version,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _candidate_dict(c: CandidateItem) -> dict:
        return {
            "title": c.title,
            "summary": c.summary,
            "link": c.link,
            "published": c.published.isoformat() if c.published else "",
            "source": c.source_name,
        }

    @staticmethod
    def _parse_entries(
        text: str, alias: str, by_link: dict[str, CandidateItem]
    ) -> tuple[list[SelectedEntry], str, str]:
        data = extract_json(text)
        if not isinstance(data, list):
            return [], "parse_failed", "返回中提取不到 JSON 数组"
        entries: list[SelectedEntry] = []
        for obj in data:
            if not isinstance(obj, dict):
                continue
            link = str(obj.get("link") or "").strip()
            entries.append(
                SelectedEntry(
                    title=str(obj.get("title") or ""),
                    topic=str(obj.get("topic") or ""),
                    one_liner=str(obj.get("one_liner") or ""),
                    detail=str(obj.get("detail") or ""),
                    link=link,
                    date=str(obj.get("date") or ""),
                    model_alias=alias,
                    candidate=by_link.get(link),
                )
            )
        return entries, "ok", ""
