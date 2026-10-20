"""OpenRouter 客户端：只用标准库 urllib，保持项目零第三方依赖。

设计要点：
- transport 可注入（默认 urllib 实现）：测试用假 transport 即可
  确定性覆盖请求组装、错误透传与重试，不需要真 key、不发真请求
  ——这是依赖倒置在 live 链路上的落点，与离线部分一脉相承。
- 凭证只从环境变量 OPENROUTER_API_KEY 或 .env 文件读，绝不写进代码。
- chat 是读取型调用：网络错误 / 429 / 5xx 最多重试 1 次；
  其余 HTTP 错误立即以 OpenRouterError 透传（状态码 + 响应体摘要）。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# transport 签名：(url, headers, body_bytes, timeout_seconds) -> (status, body_bytes)
Transport = Callable[[str, dict, bytes, float], tuple[int, bytes]]


class OpenRouterError(RuntimeError):
    """OpenRouter 调用失败：带 HTTP 状态与响应体摘要，便于定位。"""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport | None = None,
        timeout: float = 120.0,
        url: str = API_URL,
    ):
        if not api_key:
            raise OpenRouterError("缺少 API key：请设置环境变量 OPENROUTER_API_KEY 或在 .env 中配置")
        self._api_key = api_key
        self._transport = transport or _urllib_transport
        self._timeout = timeout
        self._url = url

    def chat(
        self,
        model: str,
        messages: Sequence[dict],
        max_tokens: int | None = None,
        temperature: float = 0,
    ) -> str:
        """发一次 chat completion，返回 assistant 的文本内容。"""
        payload: dict = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        last_error: OpenRouterError | None = None
        for _attempt in range(2):  # 首次 + 最多重试 1 次
            try:
                status, raw = self._transport(self._url, headers, body, self._timeout)
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_error = OpenRouterError(f"网络错误：{e}")
                continue
            if status == 200:
                return self._extract_text(raw)
            excerpt = raw.decode("utf-8", errors="replace")[:300].strip()
            last_error = OpenRouterError(
                f"OpenRouter 返回 HTTP {status}：{excerpt}", status=status, body=excerpt
            )
            if status != 429 and status < 500:
                raise last_error  # 4xx（除 429）是请求本身的问题，重试无意义
        assert last_error is not None
        raise last_error

    @staticmethod
    def _extract_text(raw: bytes) -> str:
        try:
            data = json.loads(raw.decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise OpenRouterError(f"响应结构无法解析：{e}") from e
        if content is None:
            raise OpenRouterError("响应 content 为空")
        return content if isinstance(content, str) else str(content)


# ---------------------------------------------------------------------------
# 模型配置与凭证解析
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelSet:
    """live 模式的模型组：三个执行模型 + 编辑模型 + judge 模型。

    默认 ID 是本项目约定的 OpenRouter 模型标识，可用环境变量覆盖：
    OPENROUTER_MODEL_GROK / _GEMINI / _CHATGPT / _EDITOR / _JUDGE，
    CLI 参数覆盖优先级最高。
    """

    grok: str = "x-ai/grok-4.7"
    gemini: str = "google/gemini-3.8-flash"
    chatgpt: str = "openai/gpt-5.6-luna"
    editor: str = "openai/gpt-5.6-luna"
    judge: str = "openai/gpt-5.6-luna"

    def executor_models(self) -> tuple[tuple[str, str], ...]:
        """执行器要跑的 (运行时别名, 模型 ID) 列表，顺序固定。"""
        return (("grok", self.grok), ("gemini", self.gemini), ("chatgpt", self.chatgpt))

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, overrides: dict | None = None
    ) -> "ModelSet":
        env = os.environ if env is None else env
        overrides = overrides or {}
        base = cls()
        values = {
            "grok": env.get("OPENROUTER_MODEL_GROK") or base.grok,
            "gemini": env.get("OPENROUTER_MODEL_GEMINI") or base.gemini,
            "chatgpt": env.get("OPENROUTER_MODEL_CHATGPT") or base.chatgpt,
            "editor": env.get("OPENROUTER_MODEL_EDITOR") or base.editor,
            "judge": env.get("OPENROUTER_MODEL_JUDGE") or base.judge,
        }
        for key, val in overrides.items():
            if val:
                values[key] = val
        return cls(**values)


def parse_dotenv(text: str) -> dict[str, str]:
    """极简 .env 解析：KEY=VALUE 行，# 注释，值可带引号。不求全功能。"""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def resolve_api_key(
    env: Mapping[str, str] | None = None, dotenv_paths: Sequence[Path] = ()
) -> str | None:
    """找 OpenRouter key：环境变量优先，其次逐个 .env 文件。找不到返回 None。"""
    env = os.environ if env is None else env
    if env.get("OPENROUTER_API_KEY"):
        return env["OPENROUTER_API_KEY"]
    for path in dotenv_paths:
        try:
            if Path(path).exists():
                values = parse_dotenv(Path(path).read_text(encoding="utf-8"))
                if values.get("OPENROUTER_API_KEY"):
                    return values["OPENROUTER_API_KEY"]
        except OSError:
            continue
    return None
