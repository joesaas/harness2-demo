"""拼装决策：违规下降且合规不降才采纳；「只认官方」必须被合规护栏挡下。"""

from harness2_demo.contrast import Composer
from harness2_demo.editors import default_editors


def _compose_task1(probe, corpus1, factory):
    base = probe.evaluate(factory, corpus1)
    edits = [e for ed in default_editors() for e in ed.propose(base, factory)]
    return Composer(probe).compose(factory, edits, corpus1)


def test_task1_base_metrics_anchor(probe, corpus1, factory):
    m = probe.evaluate(factory, corpus1)
    assert (m.non_event, m.out_of_window, m.duplicates, m.source_problem) == (5, 2, 3, 3)
    assert m.total_violations == 13
    assert m.compliant_groups == 8 and m.corpus_compliant_groups == 8


def test_adopted_and_rejected_sets(probe, corpus1, factory):
    result = _compose_task1(probe, corpus1, factory)
    assert {e.name for e in result.adopted} == {
        "event_only",
        "window_48",
        "dedup",
        "source_tiered",
    }
    assert [r.edit.name for r in result.rejected] == ["source_official_only"]


def test_official_only_rejected_by_compliance_guard(probe, corpus1, factory):
    result = _compose_task1(probe, corpus1, factory)
    row = result.rejected[0]
    # 它的违规确实降到了 0，但合规事件 8 -> 4，靠少收刷出来的「改进」不算数
    assert row.after.total_violations == 0
    assert row.after.compliant_groups == 4
    assert "合规事件收录下降" in row.reason


def test_final_state_clean_and_version_bumped(probe, corpus1, factory):
    result = _compose_task1(probe, corpus1, factory)
    assert result.final_metrics.total_violations == 0
    assert result.final_metrics.compliant_groups == 8
    g = result.harness.guardrails
    assert (g.event_only, g.window_hours, g.dedup, g.source_policy) == (
        True,
        48,
        True,
        "tiered",
    )
    assert result.harness.prompt.version == 2
    assert any("分级" in c for c in result.harness.prompt.clauses)
