"""Materialize a challenge's artifacts before a run.

For ``build.type == "script"`` the script is executed in the challenge dir and
is expected to drop the agent-facing artifacts into ``build.output`` (default
``dist/``). For ``docker`` / ``none`` this is a no-op here -- docker service
builds happen in the deployment layer, and ``none`` means artifacts are already
committed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .models import Challenge


class BuildError(Exception):
    pass


def ensure_built(challenge: Challenge, *, force: bool = False) -> None:
    """Ensure the challenge's artifacts exist, running the build if needed."""
    spec = challenge.build
    if spec.type != "script":
        return

    assert challenge.path is not None
    out = challenge.path / spec.output
    artifacts_present = out.exists() and all(
        (out / a).exists() for a in challenge.delivery.artifacts
    )
    if artifacts_present and not force:
        return

    out.mkdir(parents=True, exist_ok=True)
    script = challenge.path / spec.script
    if not script.exists():
        raise BuildError(f"build script not found: {script}")

    proc = subprocess.run(
        ["bash", str(script)],
        cwd=str(challenge.path),
        capture_output=True,
        text=True,
        env={"OUTPUT_DIR": str(out), "PATH": _path_env()},
    )
    if proc.returncode != 0:
        raise BuildError(
            f"build script failed for {challenge.id} (exit {proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    missing = [a for a in challenge.delivery.artifacts if not (out / a).exists()]
    if missing:
        raise BuildError(
            f"build for {challenge.id} did not produce artifacts: {missing}"
        )


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
