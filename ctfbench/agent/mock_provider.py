"""Mock providers for tests and offline demos (no network, no API key).

``ScriptedProvider`` replays a fixed list of completions -- ideal for unit
tests of the agent loop.

``MockProvider`` is a tiny reactive "agent": it runs a supplied list of shell
commands in order, watches the tool output stream for anything matching the
flag format, and submits the first match. Given a correct solve script it
drives a *real* end-to-end solve (sandbox exec + flag extraction + grading)
without any LLM -- useful as a smoke test and a reference for what a solving
transcript looks like.
"""

from __future__ import annotations

import re
from typing import Optional

from .base import Completion, Message, Provider, ToolCall


class ScriptedProvider(Provider):
    name = "scripted"

    def __init__(self, completions: list[Completion]):
        self._completions = list(completions)
        self._i = 0

    def complete(self, messages: list[Message], tools: list[dict]) -> Completion:
        if self._i >= len(self._completions):
            return Completion(text="(script exhausted)", tool_calls=[])
        c = self._completions[self._i]
        self._i += 1
        return c


class MockProvider(Provider):
    name = "mock"

    def __init__(
        self,
        solver_commands: Optional[list[str]] = None,
        flag_regex: str = r"flag\{[^}]*\}",
    ):
        self._commands = list(solver_commands or [])
        self._flag_re = re.compile(flag_regex)
        self._i = 0
        self._submitted = False

    def complete(self, messages: list[Message], tools: list[dict]) -> Completion:
        # Look for a flag in any tool output we've already collected.
        for m in reversed(messages):
            if m.role == "tool" and m.content:
                found = self._flag_re.search(m.content)
                if found and not self._submitted:
                    self._submitted = True
                    return Completion(
                        text="I found the flag.",
                        tool_calls=[
                            ToolCall(
                                id=f"call_submit",
                                name="submit_flag",
                                arguments={"flag": found.group(0)},
                            )
                        ],
                    )

        if self._i < len(self._commands):
            cmd = self._commands[self._i]
            call_id = f"call_{self._i}"
            self._i += 1
            return Completion(
                text=f"Running step {self._i}.",
                tool_calls=[ToolCall(id=call_id, name="run_bash", arguments={"command": cmd})],
            )

        return Completion(text="I could not recover the flag.", tool_calls=[])
