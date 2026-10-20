"""命令行入口与组合根（composition root）。

全项目只有这一处同时认识所有具体实现类：它负责把 RuleExecutor、
BehaviorEvaluator、规则编辑器组、JsonLessonStore 装配进 DemoRunner。
其余模块只依赖抽象接口——这就是依赖倒置在工程上的落点：
装配发生在一个点，替换实现也只动这一个点。
"""

from __future__ import annotations

import argparse

from ..contrast import BehaviorEvaluator, ProbeRunner
from ..editors import default_editors
from ..executor import RuleExecutor
from ..library import JsonLessonStore, LessonApplier
from ..runner import DemoRunner


def build_runner(library_path: str, emit=print) -> DemoRunner:
    """组装一个可直接运行的 DemoRunner（测试也复用这个组装函数）。"""
    executor = RuleExecutor()
    evaluator = BehaviorEvaluator()
    probe = ProbeRunner(executor, evaluator)
    store = JsonLessonStore(library_path)
    return DemoRunner(
        executor=executor,
        editors=default_editors(),
        probe=probe,
        store=store,
        applier=LessonApplier(),
        emit=emit,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="harness2-demo",
        description="Harness² 双层递归自我改进演示：新闻收集提示词场景（全离线、确定性）",
    )
    parser.add_argument(
        "--library",
        default="improvement_library.json",
        help="改进库 JSON 文件路径（默认：当前目录 improvement_library.json；每次演示从空库开始并重写该文件）",
    )
    args = parser.parse_args(argv)

    runner = build_runner(args.library)
    runner.run()
    print(f"\n改进库已写入：{args.library}（可直接打开检视每条教训的证据与 effect）")


if __name__ == "__main__":
    main()
