"""命令行入口与组合根（composition root）。

全项目只有这一处同时认识所有具体实现类：离线模式把 RuleExecutor、
BehaviorEvaluator、规则编辑器组、JsonLessonStore 装配进 DemoRunner；
live 模式把 LlmExecutor、JudgeEvaluator、LlmEditor 装配进 LiveRunner。
其余模块只依赖抽象接口——这就是依赖倒置在工程上的落点：
装配发生在一个点，替换实现也只动这一个点。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..contrast import BehaviorEvaluator, JudgeEvaluator, ProbeRunner
from ..editors import LlmEditor, default_editors
from ..executor import LlmExecutor, RuleExecutor
from ..library import JsonLessonStore, LessonApplier
from ..llm import ModelSet, OpenRouterClient, resolve_api_key
from ..runner import DemoRunner
from ..runner_live import LiveRunner
from ..tasks import FACTORY_PROMPT_TEXT, FACTORY_PROMPT_VERSION, FeedFetchError


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


def build_live_runner(
    library_path: str,
    client: OpenRouterClient,
    models: ModelSet,
    emit=print,
    probe_enabled: bool = True,
    limit: int = 30,
) -> LiveRunner:
    """组装 live 模式的 LiveRunner（真实零件，测试以假 client 复用）。"""
    return LiveRunner(
        executor=LlmExecutor(client, models),
        evaluator=JudgeEvaluator(client, models.judge),
        editor=LlmEditor(client, models.editor),
        store=JsonLessonStore(library_path),
        emit=emit,
        probe_enabled=probe_enabled,
        limit=limit,
    )


def _run_live(args: argparse.Namespace) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    key = resolve_api_key(dotenv_paths=[Path.cwd() / ".env", repo_root / ".env"])
    if not key:
        print(
            "错误：未找到 OpenRouter API key，live 模式无法启动（不会假装跑通）。\n"
            "配置方式二选一：\n"
            "  1) 环境变量：export OPENROUTER_API_KEY=<你的 key>\n"
            "  2) .env 文件：在当前目录或项目根目录放 .env，一行 "
            "OPENROUTER_API_KEY=<你的 key>（模板见项目根 .env.example）\n"
            "离线演示不受影响：不带 --live 直接运行即可。",
            file=sys.stderr,
        )
        raise SystemExit(2)
    models = ModelSet.from_env(
        overrides={
            "grok": args.model_grok,
            "gemini": args.model_gemini,
            "chatgpt": args.model_chatgpt,
            "editor": args.model_editor,
            "judge": args.model_judge,
        }
    )
    runner = build_live_runner(
        args.library,
        OpenRouterClient(key),
        models,
        probe_enabled=not args.no_probe,
        limit=args.limit,
    )
    try:
        runner.run(FACTORY_PROMPT_TEXT, FACTORY_PROMPT_VERSION)
    except FeedFetchError as e:
        print(f"错误：实时语料抓取失败——{e}", file=sys.stderr)
        raise SystemExit(2)
    print(f"\n改进库已写入：{args.library}（live 教训以文本保存，下一期以经验附则迁移）")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="harness2-demo",
        description="Harness² 双层递归自我改进演示：新闻收集提示词场景（默认全离线；--live 为真实 LLM 模式）",
    )
    parser.add_argument(
        "--library",
        default="improvement_library.json",
        help="改进库 JSON 文件路径（默认：当前目录 improvement_library.json）",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="真实 LLM 模式：经 OpenRouter 调 Grok/Gemini/ChatGPT 整理 RSS 实时新闻（需要 OPENROUTER_API_KEY）",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="live 模式关掉探测轮：编辑器修订未经行为对照直接采纳（省一半调用，最终指标不复测）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="live 模式每期候选条数上限（默认 30）",
    )
    parser.add_argument("--model-grok", default=None, help="覆盖 Grok 的 OpenRouter 模型 ID")
    parser.add_argument("--model-gemini", default=None, help="覆盖 Gemini 的 OpenRouter 模型 ID")
    parser.add_argument("--model-chatgpt", default=None, help="覆盖 ChatGPT 的 OpenRouter 模型 ID")
    parser.add_argument("--model-editor", default=None, help="覆盖编辑模型的 OpenRouter 模型 ID")
    parser.add_argument("--model-judge", default=None, help="覆盖 judge 模型的 OpenRouter 模型 ID")
    args = parser.parse_args(argv)

    if args.live:
        _run_live(args)
        return

    runner = build_runner(args.library)
    runner.run()
    print(f"\n改进库已写入：{args.library}（可直接打开检视每条教训的证据与 effect）")


if __name__ == "__main__":
    main()
