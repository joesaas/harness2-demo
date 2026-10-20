"""教训应用器：把改进库里的教训变成新任务的初始驾驭层。

这是驾驭级递归「经验迁移」的落点：新任务不是从最终版驾驭层
的二进制副本起步，而是从出厂默认起步、逐条应用教训的 effect
重建配置——教训是可移植的，这正是它与「存一份配置文件」的区别。
应用过的教训会以条款形式写进提示词并占用一个版本号，
让「自带教训起步」在产出里看得见。
"""

from __future__ import annotations

from ..harness import Harness
from .lessons import Lesson


class LessonApplier:
    def apply(self, harness: Harness, lessons: list[Lesson]) -> Harness:
        result = harness
        applied_clauses: list[str] = []
        for lesson in lessons:
            if not lesson.effect:
                continue  # 负教训只记录、不应用
            result = result.apply_changes(lesson.effect)
            applied_clauses.append(f"（改进库 {lesson.id}）{lesson.text}")
        if applied_clauses:
            result = result.with_prompt(result.prompt.extended(applied_clauses))
            result = result.with_lessons(tuple(lessons))
        return result
