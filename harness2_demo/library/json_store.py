"""改进库的 JSON 文件实现：整库读写，落盘即持久化。

演示选择 JSON 而非数据库，是为了让「教训跨任务保留」这件事
可以直接打开文件检视——文件本身就是演示证据。
"""

from __future__ import annotations

import json
from pathlib import Path

from .lessons import Lesson


class JsonLessonStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[Lesson]:
        if not self._path.exists():
            return []
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return [Lesson.from_dict(d) for d in data]

    def save(self, lessons: list[Lesson]) -> None:
        payload = [lesson.to_dict() for lesson in lessons]
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
