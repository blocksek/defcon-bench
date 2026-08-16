"""OpenAI-backed provider using the Chat Completions API with tool calling.

Kept intentionally thin: it translates our normalized ``Message``/``ToolCall``
types to and from the OpenAI wire format. The ``openai`` package is imported
lazily so the rest of the harness (and its tests) work without it installed.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .base import Completion, Message, Provider, ToolCall


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_retries: int = 4,
        request_timeout: float = 120.0,
    ):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "the 'openai' package is required for OpenAIProvider "
                "(pip install 'ctfbench[openai]')"
            ) from exc

        self.model = model
        self.temperature = temperature
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
            max_retries=max_retries,
            timeout=request_timeout,
        )

    def complete(self, messages: list[Message], tools: list[dict]) -> Completion:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[_to_openai(m) for m in messages],
            tools=tools,
            tool_choice="auto",
            temperature=self.temperature,
        )
        choice = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return Completion(text=choice.content or "", tool_calls=tool_calls)


def _to_openai(msg: Message) -> dict[str, Any]:
    if msg.role == "tool":
        return {"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content}
    out: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
            }
            for c in msg.tool_calls
        ]
        # OpenAI expects content to be present (may be empty) alongside tool_calls.
        out["content"] = msg.content or ""
    return out
