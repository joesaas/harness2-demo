"""改进库：落盘往返、教训应用（effect 生效、负教训跳过）、经验迁移效果。"""

from harness2_demo.library import JsonLessonStore, Lesson, LessonApplier


def _lesson(id, text, effect):
    return Lesson(
        id=id,
        text=text,
        evidence="测试证据",
        source_task="任务一",
        created_at="2026-10-20T00:00:00+00:00",
        effect=effect,
    )


def test_json_store_round_trip(tmp_path):
    path = tmp_path / "lib.json"
    store = JsonLessonStore(path)
    assert store.load() == []  # 文件不存在时为空库
    lessons = [_lesson("L1", "教训一", {"event_only": True}), _lesson("L2", "负教训", {})]
    store.save(lessons)
    assert store.load() == lessons  # 落盘再读回，逐字段相等


def test_applier_applies_effects_and_skips_negative(factory):
    lessons = [
        _lesson("L1", "只收事件", {"event_only": True}),
        _lesson("L2", "窗口 48", {"window_hours": 48}),
        _lesson("L3", "不要只认官方（负教训）", {}),
        _lesson("L4", "来源分级", {"source_policy": "tiered"}),
    ]
    h = LessonApplier().apply(factory, lessons)
    g = h.guardrails
    assert g.event_only is True and g.window_hours == 48 and g.source_policy == "tiered"
    assert h.prompt.version == 2  # 应用教训占用一个版本号
    assert len(h.lessons) == 4  # 教训快照随驾驭层携带（含负教训，供检视）


def test_migration_effect_task2_starts_cleaner(probe, corpus1, corpus2, factory):
    """核心性质：带教训起步的任务二初始违规，远低于任务一从零起步。"""
    lessons = [
        _lesson("L1", "", {"event_only": True}),
        _lesson("L2", "", {"window_hours": 48}),
        _lesson("L3", "", {"dedup": True}),
        _lesson("L4", "", {"source_policy": "tiered"}),
    ]
    task1_initial = probe.evaluate(factory, corpus1)
    task2_initial = probe.evaluate(LessonApplier().apply(factory, lessons), corpus2)
    assert task1_initial.total_violations == 13
    assert task2_initial.total_violations == 1  # 只剩匿名社交来源这一个新失败
    assert task2_initial.total_violations < task1_initial.total_violations
    assert task2_initial.compliant_groups == 7  # 合规事件一个没漏
