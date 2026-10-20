"""LLM 接入包：OpenRouter 客户端（标准库 urllib）与 JSON 容错提取。

live 模式的全部模型调用都走这里；client 的 transport 可注入，
使整条 live 链路能在无 key、无网络时用假响应确定性测试。
"""

from .client import (
    ModelSet,
    OpenRouterClient,
    OpenRouterError,
    parse_dotenv,
    resolve_api_key,
)
from .jsonutil import extract_json

__all__ = [
    "ModelSet",
    "OpenRouterClient",
    "OpenRouterError",
    "extract_json",
    "parse_dotenv",
    "resolve_api_key",
]
