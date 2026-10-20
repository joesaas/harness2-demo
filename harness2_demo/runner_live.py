"""live 编排（LiveRunner）：Harness² 双层递归换上真实零件后的同一条演示线。

与离线 DemoRunner 的对应关系（结构不变、实现替换）：
- 语料：构造 fixture -> RSS 实时抓取（tasks/feeds，两组 bundle 不重叠）
- 执行器：RuleExecutor -> LlmExecutor（三模型各跑一份提示词）
- 评估：BehaviorEvaluator（纯属性）-> JudgeEvaluator（程序检查 + judge 判定）
- 编辑器：规则编辑器组 -> LlmEditor（全文修订提议）
- Compose：离线是「违规降且合规不降」；live 的合规数是 judge 估计、
  噪声更大，护栏放宽为「合规下降不超过 20%」——口径差异写在这里，
  也是全文唯一出处。
- 改进库：同一 LessonStore；live 教训的 effect 为空（live 驾驭层是
  提示词全文，没有 Guardrails 字段可映射），迁移方式改为把教训文本
  以「经验附则」附在下一期提示词末尾。

成本护栏：每期开跑前先打印调用计划。单期调用量 = 执行 3 +
judge 至多 3 + 编辑 1 = 至多 7 次；开探测再 +6（执行 3 + judge
至多 3），至多 13 次。--no-probe 可关掉探测轮（修订未经对照
直接采纳，输出与教训证据都会如实标注）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence

from .contrast.live_evaluator import JudgeEvaluator, LiveMetrics
from .domain import CandidateItem
from .editors.llm_editor import LlmEditor, PromptRevision
from .executor.llm_executor import LlmExecutor
from .harness import Guardrails, Harness, PromptComponent
from .library import Lesson, LessonStore
from .tasks import FEED_BUNDLE_A, FEED_BUNDLE_B, FeedSource, fetch_candidates

Loader = Callable[[Sequence[FeedSource], int, list], list[CandidateItem]]


def _default_loader(bundle: Sequence[FeedSource], limit: int, errors: list) -> list[CandidateItem]:
    return fetch_candidates(bundle, limit=limit, errors=errors)


def _fmt_live(m: LiveMetrics) -> str:
    return (
        f"被选 {m.selected} 条｜违规总计 {m.total_violations}"
        f"（幻觉 {m.hallucinated}、重复 {m.duplicates}、judge 判违规 {m.violations}）"
        f"｜合规（judge 判 event）{m.compliant}"
        + (f"｜judge 未判定 {m.judge_failed}" if m.judge_failed else "")
    )


@dataclass
class LiveTaskResult:
    name: str
    candidates: int
    feed_errors: tuple[str, ...]
    base: LiveMetrics
    final: LiveMetrics
    adopted: bool
    start_version: int
    final_version: int
    note: str  # 本轮编辑结局的人类可读说明（无修订 / 采纳 / 拒绝 / 未经探测采纳）


@dataclass
class LiveReport:
    task1: LiveTaskResult
    task2: LiveTaskResult
    appendix: str  # 附在任务二提示词末尾的经验附则全文
    lessons_total: int


class LiveRunner:
    def __init__(
        self,
        executor: LlmExecutor,
        evaluator: JudgeEvaluator,
        editor: LlmEditor,
        store: LessonStore,
        *,
        emit: Callable[[str], None] = print,
        clock: Callable[[], str] | None = None,
        probe_enabled: bool = True,
        limit: int = 30,
        candidate_loader: Loader | None = None,
    ):
        self._executor = executor
        self._evaluator = evaluator
        self._editor = editor
        self._store = store
        self._emit = emit
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
        self._probe_enabled = probe_enabled
        self._limit = limit
        self._loader = candidate_loader or _default_loader
        self._lessons_buffer: list[Lesson] = []
        self._lesson_seq = 0

    # ------------------------------------------------------------------
    def run(self, prompt_text: str, start_version: int) -> LiveReport:
        e = self._emit
        e("=" * 68)
        e("Harness² live 演示：真实 LLM 场景——一套提示词 × 三个模型整理实时新闻")
        e("执行模型：Grok / Gemini / ChatGPT（经 OpenRouter）；违规判定含 judge 模型估计")
        e("=" * 68)
        self._lessons_buffer = list(self._store.load())
        self._lesson_seq = len(self._lessons_buffer)

        text1, version1, result1 = self._run_task(
            "任务一", FEED_BUNDLE_A, prompt_text, start_version
        )
        self._store.save(list(self._lessons_buffer))

        appendix = self._build_appendix()
        e("\n【经验附则】以下教训将附在任务二提示词末尾（改进库迁移方式）：")
        e(appendix)

        text2 = text1 + appendix
        _text2, _version2, result2 = self._run_task(
            "任务二", FEED_BUNDLE_B, text2, version1
        )
        self._store.save(list(self._lessons_buffer))

        e("\n【live 总结对照】")
        e(
            f"  任务一：违规总计 {result1.base.total_violations} → {result1.final.total_violations}，"
            f"合规 {result1.base.compliant} → {result1.final.compliant}（{result1.note}）"
        )
        e(
            f"  任务二（提示词 = 任务一最终版 + 经验附则）：违规总计 {result2.base.total_violations} → "
            f"{result2.final.total_violations}，合规 {result2.base.compliant} → {result2.final.compliant}"
            f"（{result2.note}）"
        )
        e("  注：合规/违规中的 judge 部分为模型判定，属估计口径，不是真值。")
        return LiveReport(
            task1=result1,
            task2=result2,
            appendix=appendix,
            lessons_total=len(self._lessons_buffer),
        )

    # ------------------------------------------------------------------
    def _run_task(
        self,
        name: str,
        bundle: Sequence[FeedSource],
        prompt_text: str,
        version: int,
    ) -> tuple[str, int, LiveTaskResult]:
        e = self._emit
        errors: list[str] = []
        candidates = self._loader(bundle, self._limit, errors)
        planned = 7 + (6 if self._probe_enabled else 0)
        e(f"\n【{name}】feed {len(bundle)} 个，候选 {len(candidates)} 条（上限 {self._limit}）")
        for err in errors:
            e(f"        feed 抓取失败：{err}")
        e(
            "        调用计划：执行 3 + judge 至多 3 + 编辑 1"
            + (" + 探测轮（执行 3 + judge 至多 3）" if self._probe_enabled else "（已关探测）")
            + f" = 至多 {planned} 次"
        )
        e(f"        起步提示词：v{version}")

        harness = Harness(
            prompt=PromptComponent(version=version, full_text=prompt_text),
            guardrails=Guardrails(),
        )
        briefing = self._executor.run(harness, candidates)
        self._print_briefing(briefing)
        evaluation = self._evaluator.evaluate(candidates, briefing, prompt_text)
        base = evaluation.aggregate
        e(f"        初始指标（汇总）：{_fmt_live(base)}")

        revision = self._editor.revise(prompt_text, base, evaluation.violation_examples())
        if revision is None:
            e("        编辑器本轮未产出可用修订（调用失败或 JSON 解析失败），保持原提示词")
            return prompt_text, version, LiveTaskResult(
                name, len(candidates), tuple(errors), base, base,
                False, version, version, "编辑器无修订",
            )
        e(f"        编辑器提议全文修订（{len(revision.changes)} 条改动）：")
        for change in revision.changes:
            e(f"          - [{change.section}] {change.why}（对应指标：{change.metric}）")

        if not self._probe_enabled:
            new_version = version + 1
            self._record_lesson(
                name,
                text=f"提示词修订（未经探测采纳）：{self._changes_summary(revision)}",
                evidence=(
                    f"{name} --no-probe 模式：修订未在同语料上重跑对照，"
                    f"采纳前指标为违规 {base.total_violations}、合规 {base.compliant}"
                ),
            )
            e(f"        --no-probe：修订未经对照直接采纳，提示词 v{version} → v{new_version}（最终指标未复测）")
            return revision.new_prompt, new_version, LiveTaskResult(
                name, len(candidates), tuple(errors), base, base,
                True, version, new_version, "修订未经探测直接采纳，最终指标未复测",
            )

        candidate_harness = harness.with_prompt(
            harness.prompt.replaced_full_text(revision.new_prompt)
        )
        briefing2 = self._executor.run(candidate_harness, candidates)
        evaluation2 = self._evaluator.evaluate(candidates, briefing2, revision.new_prompt)
        after = evaluation2.aggregate
        e(
            f"        探测对照：违规 {base.total_violations} → {after.total_violations}，"
            f"合规 {base.compliant} → {after.compliant}"
        )

        adopted, reason = self._decide(base, after)
        if adopted:
            new_version = version + 1
            self._record_lesson(
                name,
                text=f"提示词修订已采纳：{self._changes_summary(revision)}",
                evidence=(
                    f"{name} 探测对照：违规总计 {base.total_violations} → {after.total_violations}，"
                    f"合规 {base.compliant} → {after.compliant}"
                ),
            )
            e(f"        拼装：采纳（{reason}），提示词 v{version} → v{new_version}")
            return revision.new_prompt, new_version, LiveTaskResult(
                name, len(candidates), tuple(errors), base, after,
                True, version, new_version, f"修订经探测采纳：{reason}",
            )
        self._record_lesson(
            name,
            text=f"提示词修订被拒绝：{reason}。修订内容摘要：{self._changes_summary(revision)}",
            evidence=(
                f"{name} 探测对照：违规总计 {base.total_violations} → {after.total_violations}，"
                f"合规 {base.compliant} → {after.compliant}"
            ),
        )
        e(f"        拼装：拒绝（{reason}），保持提示词 v{version}，负教训已写入改进库")
        return prompt_text, version, LiveTaskResult(
            name, len(candidates), tuple(errors), base, base,
            False, version, version, f"修订被拒绝：{reason}",
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _decide(before: LiveMetrics, after: LiveMetrics) -> tuple[bool, str]:
        """live 版 Compose 规则：违规严格下降，且合规下降不超过 20%。"""
        if after.total_violations >= before.total_violations:
            return (
                False,
                f"违规总数未下降（{before.total_violations} → {after.total_violations}）",
            )
        if before.compliant > 0 and after.compliant * 5 < before.compliant * 4:
            return (
                False,
                f"合规收录下降超过 20%（{before.compliant} → {after.compliant}），"
                "靠少收换来的违规下降不算改进",
            )
        return (
            True,
            f"违规总数 {before.total_violations} → {after.total_violations}，"
            f"合规 {before.compliant} → {after.compliant}（下降在 20% 容忍带内）",
        )

    def _print_briefing(self, briefing) -> None:
        e = self._emit
        for record in briefing.records:
            count = len(briefing.entries_of(record.alias))
            if record.status == "ok":
                e(
                    f"        模型 {record.alias}（{record.model}）：ok，"
                    f"{record.elapsed_s:.1f}s，返回 {record.raw_chars} 字符，选 {count} 条"
                )
            else:
                e(
                    f"        模型 {record.alias}（{record.model}）：{record.status}"
                    f"——{record.error}，选 0 条"
                )
        titles = [entry.title for entry in briefing.merged[:5]]
        e(f"        合并视图 {len(briefing.merged)} 条，前 5 条：")
        for title in titles:
            e(f"          · {title}")

    def _build_appendix(self) -> str:
        lines = ["", "【经验附则（来自改进库的历史教训，执行本提示词时一并遵守）】"]
        for lesson in self._lessons_buffer:
            lines.append(f"- （{lesson.id}，{lesson.source_task}）{lesson.text}")
        return "\n".join(lines)

    @staticmethod
    def _changes_summary(revision: PromptRevision) -> str:
        if not revision.changes:
            return "编辑器未逐条说明改动"
        return "；".join(
            f"{c.section}：{c.why}" if c.why else c.section for c in revision.changes
        )

    def _record_lesson(self, task_name: str, *, text: str, evidence: str) -> None:
        self._lesson_seq += 1
        self._lessons_buffer.append(
            Lesson(
                id=f"L{self._lesson_seq}",
                text=text,
                evidence=evidence,
                source_task=task_name,
                created_at=self._clock(),
                effect={},  # live 教训靠文本附则迁移，没有 Guardrails effect 可映射
            )
        )
