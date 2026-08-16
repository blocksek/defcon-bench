"""Agent-loop tests using the scripted/mock providers and a fake sandbox."""

from ctfbench.agent.base import Agent, AgentConfig, Completion, ToolCall
from ctfbench.agent.mock_provider import MockProvider, ScriptedProvider
from ctfbench.sandbox import ExecResult


class FakeSandbox:
    """Records commands and returns canned outputs keyed by substring."""

    def __init__(self, responses):
        self.responses = responses
        self.commands = []

    def run(self, command, timeout=120):
        self.commands.append(command)
        for needle, out in self.responses.items():
            if needle in command:
                return ExecResult(0, out)
        return ExecResult(0, "")


def _agent(provider, sandbox, max_steps=10):
    return Agent(
        provider,
        run_bash=lambda cmd, to: sandbox.run(cmd, to),
        config=AgentConfig(max_steps=max_steps),
    )


def test_scripted_bash_then_submit():
    sandbox = FakeSandbox({"cat flag": "flag{scripted}"})
    provider = ScriptedProvider(
        [
            Completion("", [ToolCall("c1", "run_bash", {"command": "cat flag"})]),
            Completion("", [ToolCall("c2", "submit_flag", {"flag": "flag{scripted}"})]),
        ]
    )
    outcome = _agent(provider, sandbox).solve("task")
    assert outcome.submitted_flag == "flag{scripted}"
    assert "cat flag" in sandbox.commands
    assert "flag{scripted}" in outcome.accumulated_output


def test_mock_provider_reacts_to_flag_in_output():
    sandbox = FakeSandbox({"solve": "recovered flag{mocked}"})
    provider = MockProvider(solver_commands=["ls", "python3 solve.py"])
    outcome = _agent(provider, sandbox).solve("task")
    assert outcome.submitted_flag == "flag{mocked}"


def test_agent_stops_when_script_exhausted():
    sandbox = FakeSandbox({})
    provider = MockProvider(solver_commands=["ls"])  # no flag ever appears
    outcome = _agent(provider, sandbox, max_steps=5).solve("task")
    assert outcome.submitted_flag is None
    assert outcome.steps <= 5


def test_provider_error_is_captured():
    class Boom:
        name = "boom"

        def complete(self, messages, tools):
            raise RuntimeError("kaboom")

    outcome = _agent(Boom(), FakeSandbox({})).solve("task")
    assert outcome.error and "kaboom" in outcome.error
