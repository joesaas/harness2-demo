"""从 LLM 返回文本里提取 JSON：容错工具。

模型被要求「只返回 JSON」，但真实返回常带代码块包裹、前后杂字、
解释性文字。本模块按宽容顺序尝试：整段直解 -> 代码块内容 ->
从第一个 [ 或 { 起做括号配平扫描。全部失败返回 None，调用方
按「解析失败事件」处理，绝不抛异常打断主流程。
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str):
    """提取第一个可解析的 JSON 值（list / dict / 标量），失败返回 None。"""
    if not text:
        return None
    candidates: list[str] = [text.strip()]
    m = _FENCE_RE.search(text)
    if m:
        candidates.append(m.group(1).strip())
    for cand in candidates:
        try:
            return json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            pass
    # 括号配平扫描：从每个 [ / { 位置起尝试截取平衡片段
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        frag = _balanced_slice(text, i)
        if frag is None:
            continue
        try:
            return json.loads(frag)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _balanced_slice(text: str, start: int) -> str | None:
    """从 start 处的开括号起，扫描到与之配平的闭括号（跳过字符串内部）。"""
    opener = text[start]
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
