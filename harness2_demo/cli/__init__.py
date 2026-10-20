"""CLI 包：组合根（把具体实现装配给只依赖抽象的 runner）。"""

from .main import build_runner, main

__all__ = ["build_runner", "main"]
