"""OpenRouter 客户端与 JSON 提取的确定性单测（假 transport，不联网）。"""

from __future__ import annotations

import json
import urllib.error

import pytest

from harness2_demo.llm import (
    ModelSet,
    OpenRouterClient,
    OpenRouterError,
    extract_json,
    parse_dotenv,
    resolve_api_key,
)


def _ok_payload(text: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode("utf-8")


class FakeTransport:
    """按脚本逐个返回 (status, body) 或抛异常；记录每次请求。

    transport 约定：(url, headers, body_bytes, timeout) -> (status, body_bytes)。
    """

    def __init__(self, script: list):
        self._script = list(script)
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        self.requests.append((url, headers, body, timeout))
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_chat_assembles_request_and_returns_text():
    transport = FakeTransport([(200, _ok_payload("你好"))])
    client = OpenRouterClient("sk-test", transport=transport)
    out = client.chat("m/1", [{"role": "user", "content": "hi"}], max_tokens=10)
    assert out == "你好"
    url, headers, raw_body, timeout = transport.requests[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    assert timeout == 120.0
    body = json.loads(raw_body.decode("utf-8"))
    assert body["model"] == "m/1"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["max_tokens"] == 10
    assert body["temperature"] == 0


def test_http_4xx_raises_with_status_and_body_no_retry():
    transport = FakeTransport([(401, b'{"error": "bad key"}')])
    client = OpenRouterClient("sk-bad", transport=transport)
    with pytest.raises(OpenRouterError) as exc:
        client.chat("m/1", [{"role": "user", "content": "hi"}])
    assert "401" in str(exc.value) and "bad key" in str(exc.value)
    assert len(transport.requests) == 1  # 4xx 不重试


def test_http_500_retries_once_then_succeeds():
    transport = FakeTransport([(500, b"oops"), (200, _ok_payload("恢复"))])
    client = OpenRouterClient("sk-test", transport=transport)
    assert client.chat("m/1", [{"role": "user", "content": "hi"}]) == "恢复"
    assert len(transport.requests) == 2


def test_network_error_retries_once_then_raises():
    transport = FakeTransport(
        [urllib.error.URLError("down"), urllib.error.URLError("down")]
    )
    client = OpenRouterClient("sk-test", transport=transport)
    with pytest.raises(OpenRouterError):
        client.chat("m/1", [{"role": "user", "content": "hi"}])
    assert len(transport.requests) == 2


def test_malformed_success_body_raises():
    transport = FakeTransport([(200, b"not json")])
    client = OpenRouterClient("sk-test", transport=transport)
    with pytest.raises(OpenRouterError):
        client.chat("m/1", [{"role": "user", "content": "hi"}])


def test_modelset_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL_GROK", raising=False)
    models = ModelSet.from_env()
    assert models.grok == "x-ai/grok-4.7"
    assert models.gemini == "google/gemini-3.8-flash"
    assert models.chatgpt == "openai/gpt-5.6-luna"
    assert models.editor == models.chatgpt and models.judge == models.chatgpt
    monkeypatch.setenv("OPENROUTER_MODEL_GROK", "x-ai/grok-env")
    assert ModelSet.from_env().grok == "x-ai/grok-env"
    # 显式覆盖（CLI）优先于环境变量
    assert ModelSet.from_env(overrides={"grok": "x-ai/grok-cli"}).grok == "x-ai/grok-cli"


def test_parse_dotenv_and_key_resolution(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# 注释\nOPENROUTER_API_KEY='sk-from-file'\nOTHER=1\n\nBADLINE\n",
        encoding="utf-8",
    )
    assert parse_dotenv(env_file.read_text(encoding="utf-8"))["OPENROUTER_API_KEY"] == "sk-from-file"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert resolve_api_key(dotenv_paths=[env_file]) == "sk-from-file"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")
    assert resolve_api_key(dotenv_paths=[env_file]) == "sk-from-env"  # 环境变量优先
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert resolve_api_key(dotenv_paths=[tmp_path / "missing.env"]) is None


def test_extract_json_variants():
    assert extract_json('[{"a": 1}]') == [{"a": 1}]
    assert extract_json('说明文字\n```json\n{"a": 1}\n```\n完') == {"a": 1}
    assert extract_json('前缀 {"a": [1, {"b": "}]"}]} 后缀') == {"a": [1, {"b": "}]"}]}
    assert extract_json("完全没有 JSON") is None
    assert extract_json("") is None
