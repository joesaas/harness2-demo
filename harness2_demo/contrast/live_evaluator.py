"""live 行为评估：不用真值，只看可观察属性 + 一名 judge 模型的判定。

指标口径（与离线 BehaviorEvaluator 的分工）：
- 幻觉条目数、重复数：纯程序检查（link 是否在候选集、link/标题是否
  重复），确定性，不经模型；
- 违规收录数、合规收录数：由 judge 模型逐条判定 event / non-event。
  **这是模型评的估计值，不是真值**——judge 本身会看走眼，报告与
  README 都按估计口径标注；judge 调用失败或解析不出的条目记入
  judge_failed，两边都不算，绝不假装判过。

judge 每模型简报最多调用一次（<=3 次/期），把被选条目（标题+摘要）
连同收集提示词全文（含【明确不收】规则）一起发过去。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Sequence

from ..domain import CandidateItem, ViolationExample
from ..executor.llm_executor import LiveBriefing, SelectedEntry
from ..llm import OpenRouterClient, OpenRouterError, extract_json

JUDGE_SYSTEM = (
    "你是一名新闻简报质检员。给你一份新闻收集提示词（内含收录范围与【明确不收】规则）"
    "和一批已被选中的条目，请逐条判定：event = 符合收录范围的技术/产品事件；"
    "non-event = 属于明确不收的类型（数据盘点与趋势综述、融资八卦、代币行情、"
    "市场预测、营销软文、纯观点文章、旧闻重发）。"
    "只返回一个 JSON 数组，不要输出其它文字。每项字段："
    "index（条目序号）、verdict（\"event\" 或 \"non-event\"）、"
    "kind（event / data / trend / funding / price / marketing / opinion / old / other）、"
    "reason（一句话理由）。"
)


@dataclass(frozen=True)
class Judgement:
    verdict: str  # "event" | "non-event"
    kind: str
    reason: str


@dataclass(frozen=True)
class JudgedEntry:
    entry: SelectedEntry
    judgement: Judgement | None  # None = judge 没判成（失败/漏项），不算违规也不算合规


@dataclass(frozen=True)
class LiveMetrics:
    """一期（或一个模型）live 简报的行为指标。全部是行为事实或 judge 估计。"""

    selected: int = 0  # 被选条数
    hallucinated: int = 0  # 违规：link 不在候选集里（模型编造/改写了出处）
    duplicates: int = 0  # 违规：同 link 或近似标题重复出现
    violations: int = 0  # 违规：judge 判 non-event 的条数（估计）
    compliant: int = 0  # 合规：judge 判 event 的条数（估计）
    judge_failed: int = 0  # judge 未能判定的条数（两边都不计）

    @property
    def total_violations(self) -> int:
        return self.hallucinated + self.duplicates + self.violations


@dataclass(frozen=True)
class LiveEvaluation:
    per_model: dict[str, LiveMetrics]
    aggregate: LiveMetrics
    judged: tuple[JudgedEntry, ...]  # 全部条目的逐条判定（按执行器模型顺序拼接）

    def violation_examples(self, per_kind: int = 3) -> list[ViolationExample]:
        """给编辑器的违规样例：按 judge 的 kind 分组，每类最多 per_kind 条。"""
        counts: dict[str, int] = {}
        out: list[ViolationExample] = []
        for je in self.judged:
            j = je.judgement
            if j is None or j.verdict != "non-event":
                continue
            if counts.get(j.kind, 0) >= per_kind:
                continue
            counts[j.kind] = counts.get(j.kind, 0) + 1
            out.append(ViolationExample(title=je.entry.title, kind=j.kind, reason=j.reason))
        return out


# ---------------------------------------------------------------------------
# 纯函数部分：程序可判的指标（确定性，单测直接钉）
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    return re.sub(r"\W+", "", title.lower())


def compute_metrics(
    entries: Sequence[SelectedEntry],
    judgements: Sequence[Judgement | None],
    candidate_links: set[str],
) -> LiveMetrics:
    hallucinated = sum(1 for e in entries if e.link.strip() not in candidate_links)
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    duplicates = 0
    for e in entries:
        link_key = e.link.strip()
        title_key = _normalize_title(e.title)
        if link_key in seen_links or (title_key and title_key in seen_titles):
            duplicates += 1
        seen_links.add(link_key)
        if title_key:
            seen_titles.add(title_key)
    return LiveMetrics(
        selected=len(entries),
        hallucinated=hallucinated,
        duplicates=duplicates,
        violations=sum(1 for j in judgements if j is not None and j.verdict == "non-event"),
        compliant=sum(1 for j in judgements if j is not None and j.verdict == "event"),
        judge_failed=sum(1 for j in judgements if j is None),
    )


# ---------------------------------------------------------------------------
# judge 调用
# ---------------------------------------------------------------------------


class JudgeEvaluator:
    """Evaluator 角色的 live 实现：程序检查 + judge 模型判定。"""

    def __init__(self, client: OpenRouterClient, judge_model: str, *, max_tokens: int | None = 4096):
        self._client = client
        self._judge_model = judge_model
        self._max_tokens = max_tokens

    def evaluate(
        self,
        candidates: Sequence[CandidateItem],
        briefing: LiveBriefing,
        prompt_text: str,
    ) -> LiveEvaluation:
        candidate_links = {c.link.strip() for c in candidates}
        per_model: dict[str, LiveMetrics] = {}
        judged_all: list[JudgedEntry] = []
        for alias, entries in briefing.by_model.items():
            judgements = self._judge(prompt_text, entries) if entries else []
            per_model[alias] = compute_metrics(entries, judgements, candidate_links)
            judged_all.extend(
                JudgedEntry(e, j) for e, j in zip(entries, judgements)
            )
        # 汇总 = 各模型指标之和（不是把三份简报拼起来重算：跨模型选中
        # 同一条是共识、不是重复，重复只在单个模型的简报内部计）。
        ms = list(per_model.values())
        aggregate = LiveMetrics(
            selected=sum(m.selected for m in ms),
            hallucinated=sum(m.hallucinated for m in ms),
            duplicates=sum(m.duplicates for m in ms),
            violations=sum(m.violations for m in ms),
            compliant=sum(m.compliant for m in ms),
            judge_failed=sum(m.judge_failed for m in ms),
        )
        return LiveEvaluation(
            per_model=per_model, aggregate=aggregate, judged=tuple(judged_all)
        )

    def _judge(
        self, prompt_text: str, entries: Sequence[SelectedEntry]
    ) -> list[Judgement | None]:
        payload = [
            {
                "index": i,
                "title": e.title,
                "summary": (e.candidate.summary if e.candidate else e.detail)[:600],
            }
            for i, e in enumerate(entries)
        ]
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"【收集提示词全文】\n{prompt_text}\n\n【被选条目】\n"
                    + json.dumps(payload, ensure_ascii=False)
                ),
            },
        ]
        try:
            text = self._client.chat(self._judge_model, messages, max_tokens=self._max_tokens)
        except OpenRouterError:
            return [None] * len(entries)
        data = extract_json(text)
        if not isinstance(data, list):
            return [None] * len(entries)
        by_index: dict[int, Judgement] = {}
        for obj in data:
            if not isinstance(obj, dict) or not isinstance(obj.get("index"), int):
                continue
            verdict = str(obj.get("verdict") or "")
            if verdict not in ("event", "non-event"):
                continue
            by_index[obj["index"]] = Judgement(
                verdict=verdict,
                kind=str(obj.get("kind") or "other"),
                reason=str(obj.get("reason") or ""),
            )
        return [by_index.get(i) for i in range(len(entries))]
