"""live 全链路确定性单测：假 client 脚本化响应，不联网、不需要 key。

覆盖：执行器 JSON 提取（含代码块包裹）与单模型失败不崩、评估的
link-in-set/重复/judge 计数、编辑器修订解析、LiveRunner 在脚本化
judge 下的采纳（任务一）与拒绝（任务二，合规降幅 >20%）两条路径、
任务二提示词带经验附则、--no-probe 语义、CLI 无 key 明确报错。
"""

from __future__ import annotations

import json

import pytest

from harness2_demo.cli.main import main
from harness2_demo.contrast.live_evaluator import (
    JudgeEvaluator,
    Judgement,
    compute_metrics,
)
from harness2_demo.domain import CandidateItem
from harness2_demo.editors.llm_editor import LlmEditor
from harness2_demo.executor.llm_executor import LlmExecutor, SelectedEntry
from harness2_demo.harness import Guardrails, Harness, PromptComponent
from harness2_demo.library import JsonLessonStore
from harness2_demo.llm import ModelSet, OpenRouterError
from harness2_demo.runner_live import LiveRunner


class FakeClient:
    """记录全部调用，按 handler(model, messages) 返回脚本化文本。"""

    def __init__(self, handler):
        self._handler = handler
        self.calls: list[tuple[str, list]] = []

    def chat(self, model, messages, *, max_tokens=None, temperature=0.0):
        self.calls.append((model, messages))
        return self._handler(model, messages)


def cand(i: int, title: str) -> CandidateItem:
    return CandidateItem(
        title=title,
        summary=f"摘要{i}",
        link=f"https://ex.com/{i}",
        published=None,
        source_name="测试源",
    )


CANDIDATES = [
    cand(1, "协议 X 发布 v2 版本"),
    cand(2, "DeFi 市场数据盘点：TVL 周报"),
    cand(3, "Agent 框架 Y 开源新版本"),
    cand(4, "治理提案 Z 通过执行"),
]
BY_LINK = {c.link: c for c in CANDIDATES}


def sel(*idxs: int) -> str:
    return json.dumps(
        [
            {
                "title": CANDIDATES[i - 1].title,
                "topic": "defi",
                "one_liner": "一句话",
                "detail": "细节",
                "link": CANDIDATES[i - 1].link,
                "date": "",
            }
            for i in idxs
        ],
        ensure_ascii=False,
    )


def harness(text: str = "提示词全文") -> Harness:
    return Harness(prompt=PromptComponent(version=5, full_text=text), guardrails=Guardrails())


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------


def test_executor_parses_fenced_json_and_isolates_failures():
    def handler(model, messages):
        if model == ModelSet().grok:
            # 代码块包裹 + 一条编造链接（幻觉抓手）
            body = sel(1)[:-1] + ', {"title": "编造条目", "topic": "defi", "one_liner": "", "detail": "", "link": "https://fake.example/x", "date": ""}]'
            return f"好的，结果如下：\n```json\n{body}\n```"
        if model == ModelSet().gemini:
            raise OpenRouterError("HTTP 503：上游不可用")
        return "这不是 JSON"

    executor = LlmExecutor(FakeClient(handler), ModelSet(), clock=lambda: 0.0)
    briefing = executor.run(harness(), CANDIDATES)
    statuses = {r.alias: r.status for r in briefing.records}
    assert statuses == {"grok": "ok", "gemini": "error", "chatgpt": "parse_failed"}
    grok_entries = briefing.entries_of("grok")
    assert len(grok_entries) == 2
    assert grok_entries[0].candidate is CANDIDATES[0]
    assert grok_entries[1].candidate is None  # 编造链接匹配不回候选
    assert len(briefing.merged) == 2


# ---------------------------------------------------------------------------
# 评估
# ---------------------------------------------------------------------------


def _entry(link: str, title: str, candidate=None) -> SelectedEntry:
    return SelectedEntry(
        title=title, topic="defi", one_liner="", detail="",
        link=link, date="", model_alias="grok", candidate=candidate,
    )


def test_compute_metrics_link_in_set_duplicates_and_judge():
    entries = [
        _entry("https://ex.com/1", "标题一", CANDIDATES[0]),
        _entry("https://ex.com/1", "标题一", CANDIDATES[0]),  # 同 link 重复
        _entry("https://fake.example/x", "编造", None),  # 幻觉
        _entry("https://ex.com/2", "数据盘点", CANDIDATES[1]),
    ]
    judgements = [
        Judgement("event", "event", ""),
        Judgement("event", "event", ""),
        None,  # judge 没判成
        Judgement("non-event", "data", "数据盘点"),
    ]
    m = compute_metrics(entries, judgements, set(BY_LINK))
    assert m.selected == 4
    assert m.hallucinated == 1
    assert m.duplicates == 1
    assert m.violations == 1
    assert m.compliant == 2
    assert m.judge_failed == 1
    assert m.total_violations == 3


def test_judge_evaluator_scripted_and_failure_modes():
    from harness2_demo.executor.llm_executor import LiveBriefing

    entries = (
        _entry("https://ex.com/1", "事件条目", CANDIDATES[0]),
        _entry("https://ex.com/2", "数据盘点", CANDIDATES[1]),
        _entry("https://fake.example/x", "编造条目", None),
    )
    briefing = LiveBriefing(
        by_model={"grok": entries}, merged=entries, records=(), prompt_version=5
    )

    def judge_handler(model, messages):
        # 只回前两条：第三条 judge 漏判 -> judge_failed
        return json.dumps(
            [
                {"index": 0, "verdict": "event", "kind": "event", "reason": "版本发布"},
                {"index": 1, "verdict": "non-event", "kind": "data", "reason": "数据盘点"},
            ]
        )

    ev = JudgeEvaluator(FakeClient(judge_handler), "judge-x").evaluate(
        CANDIDATES, briefing, "提示词"
    )
    agg = ev.aggregate
    assert (agg.hallucinated, agg.violations, agg.compliant, agg.judge_failed) == (1, 1, 1, 1)
    examples = ev.violation_examples()
    assert len(examples) == 1 and examples[0].kind == "data"

    def boom(model, messages):
        raise OpenRouterError("HTTP 500")

    ev2 = JudgeEvaluator(FakeClient(boom), "judge-x").evaluate(CANDIDATES, briefing, "提示词")
    assert ev2.aggregate.judge_failed == 3 and ev2.aggregate.violations == 0


# ---------------------------------------------------------------------------
# 编辑器
# ---------------------------------------------------------------------------


def test_editor_revise_parses_and_degrades():
    from harness2_demo.contrast.live_evaluator import LiveMetrics

    metrics = LiveMetrics(selected=6, violations=3, compliant=3)

    def handler(model, messages):
        return (
            '```json\n{"prompt": "修订后的提示词全文", "changes": '
            '[{"section": "明确不收", "why": "数据类违规集中", "metric": "违规收录"}]}\n```'
        )

    editor = LlmEditor(FakeClient(handler), "editor-x")
    revision = editor.revise("原文", metrics, [])
    assert revision is not None
    assert revision.new_prompt == "修订后的提示词全文"
    assert revision.changes[0].section == "明确不收"

    garbage = LlmEditor(FakeClient(lambda m, msgs: "没有 JSON"), "editor-x")
    assert garbage.revise("原文", metrics, []) is None
    assert LlmEditor().revise("原文", metrics, []) is None  # 无 client 不崩


# ---------------------------------------------------------------------------
# LiveRunner 端到端：任务一采纳、任务二拒绝（合规降幅 >20%）
# ---------------------------------------------------------------------------

REVISION_JSON = json.dumps(
    {
        "prompt": "修订版提示词：只收具体事件，数据盘点一律不收。",
        "changes": [
            {"section": "明确不收", "why": "数据盘点类违规集中", "metric": "违规收录"}
        ],
    },
    ensure_ascii=False,
)


def _scenario_clients():
    """按调用顺序脚本化：执行 1-3 任务一初始、4-6 任务一探测、
    7-9 任务二初始、10-12 任务二探测（探测选空 -> 合规清零 -> 拒绝）。"""
    state = {"n": 0}

    def exec_handler(model, messages):
        state["n"] += 1
        n = state["n"]
        if n <= 3:
            return sel(1, 2)
        if n <= 6:
            return sel(1, 3)
        if n <= 9:
            return sel(1, 2)
        return "[]"

    def judge_handler(model, messages):
        payload = json.loads(messages[1]["content"].split("【被选条目】\n", 1)[1])
        return json.dumps(
            [
                {
                    "index": item["index"],
                    "verdict": "non-event" if "数据" in item["title"] else "event",
                    "kind": "data" if "数据" in item["title"] else "event",
                    "reason": "脚本化判定",
                }
                for item in payload
            ]
        )

    return (
        FakeClient(exec_handler),
        FakeClient(judge_handler),
        FakeClient(lambda m, msgs: REVISION_JSON),
    )


def _make_runner(tmp_path, exec_client, judge_client, editor_client, lines, **kw):
    return LiveRunner(
        executor=LlmExecutor(exec_client, ModelSet(), clock=lambda: 0.0),
        evaluator=JudgeEvaluator(judge_client, "judge-x"),
        editor=LlmEditor(editor_client, "editor-x"),
        store=JsonLessonStore(str(tmp_path / "lib.json")),
        emit=lines.append,
        clock=lambda: "2026-10-20T00:00:00+00:00",
        candidate_loader=lambda bundle, limit, errors: list(CANDIDATES),
        **kw,
    )


def test_live_runner_end_to_end_adopt_then_reject(tmp_path):
    exec_client, judge_client, editor_client = _scenario_clients()
    lines: list[str] = []
    runner = _make_runner(tmp_path, exec_client, judge_client, editor_client, lines)
    report = runner.run("出厂提示词全文", 5)

    # 任务一：违规 3 -> 0、合规 3 -> 6，采纳，版本 5 -> 6
    assert report.task1.base.total_violations == 3
    assert report.task1.final.total_violations == 0
    assert report.task1.adopted is True and report.task1.final_version == 6
    # 任务二：探测把合规清零（降幅 >20%），拒绝并写负教训
    assert report.task2.adopted is False
    assert "20%" in report.task2.note
    assert report.lessons_total == 2

    # 经验附则：含任务一的正教训，且任务二执行时真的进了 system
    assert "经验附则" in report.appendix and "提示词修订已采纳" in report.appendix
    task2_systems = [msgs[0]["content"] for _m, msgs in exec_client.calls[6:9]]
    assert all("经验附则" in s and "L1" in s for s in task2_systems)

    out = "\n".join(lines)
    assert "至多 13 次" in out  # 成本计划先行打印
    assert "经验附则" in out
    lessons = JsonLessonStore(str(tmp_path / "lib.json")).load()
    assert len(lessons) == 2 and "被拒绝" in lessons[1].text
    assert all(lesson.effect == {} for lesson in lessons)  # live 教训靠文本迁移


def test_live_runner_no_probe_adopts_unverified(tmp_path):
    exec_client, judge_client, editor_client = _scenario_clients()
    lines: list[str] = []
    runner = _make_runner(
        tmp_path, exec_client, judge_client, editor_client, lines, probe_enabled=False
    )
    report = runner.run("出厂提示词全文", 5)
    assert len(exec_client.calls) == 6  # 两期各跑一轮，没有探测轮
    assert report.task1.adopted is True
    assert report.task1.final.total_violations == report.task1.base.total_violations
    assert "未复测" in report.task1.note


# ---------------------------------------------------------------------------
# CLI：无 key 明确报错
# ---------------------------------------------------------------------------


def test_cli_live_without_key_exits_nonzero(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # 当前目录无 .env；项目根 .env 也不存在（仓库不含真 key）
    with pytest.raises(SystemExit) as exc:
        main(["--live", "--library", str(tmp_path / "lib.json")])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "OPENROUTER_API_KEY" in err and ".env" in err
