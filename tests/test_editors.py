"""编辑器映射：哪类失败触发哪条提议；已生效的规则不再重复提议。"""

from harness2_demo.contrast import BehaviorEvaluator
from harness2_demo.editors import LlmEditor, default_editors
from harness2_demo.executor import RuleExecutor
from harness2_demo.library import Lesson, LessonApplier
from harness2_demo.tasks import build_corpus_1


def _propose_all(metrics, harness):
    return [e for ed in default_editors() for e in ed.propose(metrics, harness)]


def test_task1_base_metrics_trigger_five_edits(probe, corpus1, factory):
    metrics = probe.evaluate(factory, corpus1)
    names = [e.name for e in _propose_all(metrics, factory)]
    assert names == ["event_only", "window_48", "dedup", "source_official_only", "source_tiered"]


def test_task2_state_triggers_only_named_source(probe, corpus1, corpus2, factory):
    # 模拟任务二初始状态：出厂规则 + 任务一教训的 effect 已全部生效
    lessons = [
        Lesson("L1", "", "", "任务一", "t", {"event_only": True}),
        Lesson("L2", "", "", "任务一", "t", {"window_hours": 48}),
        Lesson("L3", "", "", "任务一", "t", {"dedup": True}),
        Lesson("L4", "", "", "任务一", "t", {"source_policy": "tiered"}),
    ]
    harness = LessonApplier().apply(factory, lessons)
    metrics = probe.evaluate(harness, corpus2)
    names = [e.name for e in _propose_all(metrics, harness)]
    assert names == ["require_named_source"]


def test_no_failures_no_proposals(probe, corpus2, factory):
    clean = factory.apply_changes(
        {
            "event_only": True,
            "window_hours": 48,
            "dedup": True,
            "source_policy": "tiered",
            "require_named_source": True,
        }
    )
    metrics = probe.evaluate(clean, corpus2)
    assert metrics.total_violations == 0
    assert _propose_all(metrics, clean) == []


def test_llm_editor_placeholder_is_substitutable(factory):
    metrics = BehaviorEvaluator().evaluate(
        build_corpus_1(), RuleExecutor().run(factory, build_corpus_1())
    )
    assert LlmEditor().propose(metrics, factory) == []  # 占位实现：恒不提议，不改变行为
