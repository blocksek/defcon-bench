"""End-to-end: build omgzip, run the mock agent locally, expect a solve.

This exercises the whole pipeline without Docker or an API key: build script ->
LocalSandbox -> agent loop (run_bash + submit_flag) -> grading. The mock agent
runs the vendored reference solver, reads the flag from output, and submits it.
"""

import pytest

from ctfbench import registry
from ctfbench.agent.base import AgentConfig
from ctfbench.agent.mock_provider import MockProvider
from ctfbench.runner import Runner


def test_omgzip_offline_solve(tmp_path):
    ch = registry.select(ids=["2023-omgzip"])[0]
    solver_src = (ch.path / "solver" / "solve.py").read_text()
    commands = [
        "ls -la",
        "unzip -o omg.zip >/dev/null && ls -la",
        "cat > solve.py <<'EOF'\n" + solver_src + "\nEOF",
        "python3 solve.py omg.zip",
    ]
    provider = MockProvider(solver_commands=commands, flag_regex=ch.flag.format)
    runner = Runner(use_docker=False, transcripts_dir=tmp_path)
    res = runner.run(ch, provider, model_label="mock",
                     config=AgentConfig(max_steps=12))

    assert res.error is None, res.error
    assert res.solved, res.to_dict()
    assert res.submitted_flag == ch.flag.value
