"""执行器筛选规则：每条 Guardrails 规则都有独立考题（fixture 就是为此构造的）。"""

from dataclasses import replace

from harness2_demo.harness import Guardrails


def _ids(briefing):
    return {it.id for it in briefing.items}


def test_factory_harness_includes_everything(executor, corpus1, factory):
    briefing = executor.run(factory, corpus1)
    assert len(briefing.items) == 19  # 出厂规则宽松到全收——这是 v1 的问题所在


def test_event_only_blocks_non_events_but_keeps_old_event(executor, corpus1, factory):
    h = factory.apply_changes({"event_only": True})
    ids = _ids(executor.run(h, corpus1))
    assert not ({"t1", "t2", "t3", "t4", "t5"} & ids)  # 数据/趋势/融资/行情/旧闻类型全拦
    assert "t6" in ids  # 窗口外的技术事件不在本规则管辖内（归窗口规则管）


def test_window_rule_blocks_out_of_window(executor, corpus1, factory):
    h = factory.apply_changes({"window_hours": 48})
    ids = _ids(executor.run(h, corpus1))
    assert "t5" not in ids and "t6" not in ids  # 150h 与 80h
    assert "t1" in ids  # 窗口内的非事件仍在（归事件规则管）


def test_dedup_keeps_official_copy(executor, corpus1, factory):
    h = factory.apply_changes({"dedup": True})
    briefing = executor.run(h, corpus1)
    uni = [it for it in briefing.items if it.event_group == "g-uni"]
    fw = [it for it in briefing.items if it.event_group == "g-framework"]
    assert [it.id for it in uni] == ["d2"]  # 三个来源只留官方
    assert [it.id for it in fw] == ["a2"]


def test_tiered_source_policy(executor, corpus1, factory):
    h = factory.apply_changes({"source_policy": "tiered"})
    ids = _ids(executor.run(h, corpus1))
    assert not ({"t2", "t7", "t8"} & ids)  # 盘点站 x2 + 未知来源
    assert "d4" in ids and "a4" in ids  # 只有社交来源的合规事件不误伤


def test_official_only_policy_cost(executor, corpus1, factory):
    h = factory.apply_changes({"source_policy": "official_only"})
    ids = _ids(executor.run(h, corpus1))
    assert "d3" not in ids and "d4" not in ids  # 资讯 / 社交来源的合规事件被误伤


def test_require_named_source_blocks_anonymous(executor, corpus2, factory):
    h = factory.apply_changes({"require_named_source": True})
    ids = _ids(executor.run(h, corpus2))
    assert "t12" not in ids  # 类别是社交、但发布者匿名
    assert "a6" in ids  # 具名社交来源不受影响


def test_max_per_topic_cap(executor, corpus1):
    from harness2_demo.tasks import build_factory_harness

    h = build_factory_harness().apply_changes({"max_per_topic": 1})
    briefing = executor.run(h, corpus1)
    counts = briefing.count_by_topic()
    assert all(v <= 1 for v in counts.values())


def test_guardrails_are_immutable(factory):
    g2 = replace(factory.guardrails, event_only=True)
    assert factory.guardrails.event_only is False and g2.event_only is True
    assert isinstance(factory.guardrails, Guardrails)
