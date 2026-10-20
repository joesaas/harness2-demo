"""端到端冒烟：完整演示的关键数字与改进库落盘结果。"""

from harness2_demo.cli.main import build_runner
from harness2_demo.library import JsonLessonStore


def test_full_demo(tmp_path):
    lines: list[str] = []
    lib = tmp_path / "improvement_library.json"
    runner = build_runner(str(lib), emit=lines.append)
    report = runner.run()

    # 两期任务的指标轨迹（演示的骨架数字）
    assert report.task1_base.total_violations == 13
    assert report.task1_final.total_violations == 0
    assert report.task2_initial.total_violations == 1
    assert report.task2_initial.total_violations < report.task1_base.total_violations
    assert report.task2_final.total_violations == 0

    # 提示词版本轨迹：v1 ->（任务一拼装）v2 ->（任务二带库重建）v2 ->（任务二拼装）v3
    assert report.task1_prompt_versions == (1, 2)
    assert report.task2_prompt_versions == (2, 3)

    # 改进库：任务一沉淀 5 条（4 采纳 + 1 负教训），任务二再 +1
    assert report.lessons_after_task1 == 5
    assert report.lessons_total == 6
    saved = JsonLessonStore(lib).load()
    assert len(saved) == 6
    negative = [ls for ls in saved if not ls.effect]
    assert len(negative) == 1 and "只认官方" in negative[0].text
    assert all(ls.evidence for ls in saved)  # 每条教训都带证据

    # 输出里有总结段
    assert any("总结对照" in line for line in lines)
