"""演示编排（DemoRunner）：把两个递归层串成一条完整演示线。

编排只依赖抽象接口（Executor / Editor / Evaluator / LessonStore），
不依赖任何具体实现（依赖倒置）；也不伸手进 Harness 内部字段，
一律走它对外的方法（迪米特法则）。换执行器、加编辑器、换存储，
这一层都不用改。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence

from .contrast import Composer, ProbeRunner
from .domain import Metrics, NewsItem
from .editors.base import Editor
from .executor.base import Executor
from .harness import Harness
from .library import Lesson, LessonApplier, LessonStore
from .tasks import build_corpus_1, build_corpus_2, build_factory_harness


@dataclass
class DemoReport:
    """一次完整演示的结构化结果（CLI 打印用它，测试断言也用它）。"""

    task1_base: Metrics
    task1_final: Metrics
    task2_initial: Metrics
    task2_final: Metrics
    lessons_after_task1: int
    lessons_total: int
    task1_prompt_versions: tuple[int, int]  # (起始, 最终)
    task2_prompt_versions: tuple[int, int]  # (带库起步, 最终)


def _fmt_metrics(m: Metrics) -> str:
    return (
        f"收录 {m.included} 条｜违规总计 {m.total_violations}"
        f"（非事件 {m.non_event}、窗口外 {m.out_of_window}、重复 {m.duplicates}、"
        f"来源问题 {m.source_problem}）｜合规事件 {m.compliant_groups}/{m.corpus_compliant_groups}"
        + (f"，漏收 {m.missed_compliant}" if m.missed_compliant else "")
    )


class DemoRunner:
    def __init__(
        self,
        executor: Executor,
        editors: Sequence[Editor],
        probe: ProbeRunner,
        store: LessonStore,
        applier: LessonApplier,
        emit: Callable[[str], None] = print,
        clock: Callable[[], str] | None = None,
    ):
        self._executor = executor
        self._editors = list(editors)
        self._composer = Composer(probe)
        self._probe = probe
        self._store = store
        self._applier = applier
        self._emit = emit
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
        self._lesson_seq = 0
        self._lessons_buffer: list[Lesson] = []

    # ------------------------------------------------------------------
    def run(self) -> DemoReport:
        e = self._emit
        e("=" * 68)
        e("Harness² 演示：新闻收集提示词的双层递归自我改进")
        e("场景：AI Agent & Web3 DeFi 协议新闻收集提示词（语料为构造 fixture，非真实新闻）")
        e("=" * 68)

        # ---------------- 任务一：任务级递归 ----------------
        corpus1 = build_corpus_1()
        harness = build_factory_harness()
        e(f"\n【第一部分 · 任务一】候选语料 {len(corpus1)} 条，出厂驾驭层起步")
        e(f"步骤 1  初始运行：{harness.describe()}")
        base_metrics = self._probe.evaluate(harness, corpus1)
        e(f"        {_fmt_metrics(base_metrics)}")

        result1, harness = self._improve_round("任务一", harness, corpus1, step_from=2)
        self._store.save(list(self._lessons_buffer))
        e(f"步骤 5  改进库写入：{len(self._lessons_buffer)} 条教训已落盘")
        for lesson in self._lessons_buffer:
            e(f"        {lesson.id} {lesson.text}")
        lessons_after_task1 = len(self._lessons_buffer)

        # ---------------- 任务二：驾驭级递归（经验迁移） ----------------
        corpus2 = build_corpus_2()
        e(f"\n【第二部分 · 任务二】候选语料 {len(corpus2)} 条，全是新面孔")
        fresh = build_factory_harness()
        loaded = self._store.load()
        harness2 = self._applier.apply(fresh, loaded)
        e(f"步骤 6  自带教训起步：出厂 v1 + 改进库 {len(loaded)} 条教训 → {harness2.describe()}")
        e(f"        （对照：任务一从零起步时违规总计 {base_metrics.total_violations}）")
        initial2 = self._probe.evaluate(harness2, corpus2)
        e(f"        任务二初始运行：{_fmt_metrics(initial2)}")
        task2_start_version = harness2.prompt.version

        result2, harness2 = self._improve_round("任务二", harness2, corpus2, step_from=7)
        self._store.save(list(self._lessons_buffer))
        e(
            f"步骤 10 改进库更新：共 {len(self._lessons_buffer)} 条教训"
            f"（本期新增 {len(self._lessons_buffer) - lessons_after_task1} 条）"
        )

        # ---------------- 总结 ----------------
        e("\n【总结对照】")
        e(
            f"  任务一：违规总计 {result1.base_metrics.total_violations} → {result1.final_metrics.total_violations}，"
            f"合规事件 {result1.base_metrics.compliant_groups} → {result1.final_metrics.compliant_groups}"
            "（全程不靠真值打分，只看行为对照）"
        )
        e(
            f"  任务二：自带教训起步违规总计 {initial2.total_violations}"
            f"（任务一从零起步是 {base_metrics.total_violations}），一轮改进后 → {result2.final_metrics.total_violations}"
        )
        e("  结论：任务级递归让单期产出变干净；驾驭级递归让下一期不必从零再错一遍。")

        return DemoReport(
            task1_base=result1.base_metrics,
            task1_final=result1.final_metrics,
            task2_initial=initial2,
            task2_final=result2.final_metrics,
            lessons_after_task1=lessons_after_task1,
            lessons_total=len(self._lessons_buffer),
            task1_prompt_versions=(1, result1.harness.prompt.version),
            task2_prompt_versions=(task2_start_version, harness2.prompt.version),
        )

    # ------------------------------------------------------------------
    def _improve_round(
        self, task_name: str, harness: Harness, corpus: list[NewsItem], step_from: int
    ):
        """一轮任务级递归：提议 -> 逐条探测对照 -> 拼装 -> 记录教训。"""
        e = self._emit
        base_metrics = self._probe.evaluate(harness, corpus)
        edits = [
            edit for ed in self._editors for edit in ed.propose(base_metrics, harness)
        ]
        e(f"步骤 {step_from}  编辑器提议 {len(edits)} 条：")
        for edit in edits:
            e(f"        - [{edit.name}] {edit.title}")
        if not edits:
            e("        （没有编辑器被触发，本轮无提议）")

        result = self._composer.compose(harness, edits, corpus)
        e(f"步骤 {step_from + 1}  逐条探测对照（同一任务上跑候选版，只看行为指标）：")
        for row in result.rows:
            e(
                f"        [{row.edit.name}] 违规 {row.before.total_violations} → {row.after.total_violations}，"
                f"合规 {row.before.compliant_groups} → {row.after.compliant_groups}｜{row.reason}"
            )
        e(
            f"步骤 {step_from + 2}  拼装完成：采纳 {len(result.adopted)} 条、拒绝 {len(result.rejected)} 条，"
            f"新版驾驭层：{result.harness.describe()}"
        )
        e(f"        最终运行：{_fmt_metrics(result.final_metrics)}")

        self._record_lessons(task_name, result)
        return result, result.harness

    def _record_lessons(self, task_name: str, result) -> None:
        """把本轮有证据的结论沉淀为教训：被采纳的编辑各一条，
        被拒且留了「拒绝教训」的编辑也一条（负教训，effect 为空）。"""
        for row in result.rows:
            if row.adopted:
                text, effect = row.edit.lesson_text, dict(row.edit.changes)
            elif row.edit.lesson_text_on_reject:
                text, effect = row.edit.lesson_text_on_reject, {}
            else:
                continue
            self._lesson_seq += 1
            self._lessons_buffer.append(
                Lesson(
                    id=f"L{self._lesson_seq}",
                    text=text,
                    evidence=(
                        f"{task_name} 探测对照「{row.edit.title}」："
                        f"违规总计 {row.before.total_violations} → {row.after.total_violations}，"
                        f"合规事件 {row.before.compliant_groups} → {row.after.compliant_groups}"
                    ),
                    source_task=task_name,
                    created_at=self._clock(),
                    effect=effect,
                )
            )
