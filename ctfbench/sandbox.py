"""Execution sandboxes for the agent's shell, and service deployment.

The agent is given a ``run_bash`` tool. Where that shell executes is
pluggable:

  * ``DockerSandbox`` -- commands run inside a throwaway container that shares
    a Docker network with the challenge service (the realistic mode).
  * ``LocalSandbox`` -- commands run in a subprocess in a temp workspace on the
    host (no isolation; handy for offline challenges and for CI without a
    Docker daemon).

``ServiceDeployment`` brings a challenge's networked service up and down with
docker compose and reports the host/port the agent should target.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExecResult:
    exit_code: int
    output: str  # combined stdout+stderr, truncated
    timed_out: bool = False


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit - 200]
    return head + f"\n...[truncated {len(text) - limit + 200} bytes]..."


class Sandbox:
    """Base class: a place the agent can run shell commands and read files."""

    workdir: Path

    def run(self, command: str, timeout: int = 120) -> ExecResult:
        raise NotImplementedError

    def put_files(self, files: list[Path], dest: str = ".") -> None:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - trivial
        pass

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class LocalSandbox(Sandbox):
    """Run commands in a subprocess inside a temp workspace on the host."""

    def __init__(self, output_limit: int = 20000, workdir: Optional[Path] = None):
        self._tmp = None
        if workdir is None:
            self._tmp = tempfile.mkdtemp(prefix="ctfbench-ws-")
            self.workdir = Path(self._tmp)
        else:
            self.workdir = Path(workdir)
            self.workdir.mkdir(parents=True, exist_ok=True)
        self.output_limit = output_limit

    def run(self, command: str, timeout: int = 120) -> ExecResult:
        try:
            proc = subprocess.run(
                ["bash", "-lc", command],
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            return ExecResult(124, _truncate(out, self.output_limit), timed_out=True)
        combined = (proc.stdout or "") + (proc.stderr or "")
        return ExecResult(proc.returncode, _truncate(combined, self.output_limit))

    def put_files(self, files: list[Path], dest: str = ".") -> None:
        target = self.workdir / dest
        target.mkdir(parents=True, exist_ok=True)
        for f in files:
            f = Path(f)
            if f.is_dir():
                shutil.copytree(f, target / f.name, dirs_exist_ok=True)
            else:
                shutil.copy2(f, target / f.name)

    def close(self) -> None:
        if self._tmp and os.path.isdir(self._tmp):
            shutil.rmtree(self._tmp, ignore_errors=True)


class DockerSandbox(Sandbox):
    """Run commands inside a long-lived solver container.

    The container is started detached with ``sleep infinity`` and commands are
    executed with ``docker exec``. If ``network`` is given, the container joins
    that Docker network so it can reach the challenge service by name.
    """

    def __init__(
        self,
        image: str = "ctfbench/solver:latest",
        network: Optional[str] = None,
        output_limit: int = 20000,
        name: Optional[str] = None,
        runner: "CommandRunner | None" = None,
    ):
        self.image = image
        self.network = network
        self.output_limit = output_limit
        self.workdir = Path("/workspace")
        self._runner = runner or CommandRunner()
        self._name = name or f"ctfbench-solver-{os.getpid()}-{int(time.time())}"
        self._started = False
        self._start()

    def _start(self) -> None:
        args = ["docker", "run", "-d", "--rm", "--name", self._name, "-w", "/workspace"]
        if self.network:
            args += ["--network", self.network]
        args += [self.image, "sleep", "infinity"]
        res = self._runner.run(args, timeout=120)
        if res.exit_code != 0:
            raise RuntimeError(f"failed to start solver container: {res.output}")
        self._runner.run(["docker", "exec", self._name, "mkdir", "-p", "/workspace"])
        self._started = True

    def run(self, command: str, timeout: int = 120) -> ExecResult:
        args = ["docker", "exec", "-w", "/workspace", self._name, "bash", "-lc", command]
        res = self._runner.run(args, timeout=timeout)
        return ExecResult(res.exit_code, _truncate(res.output, self.output_limit), res.timed_out)

    def put_files(self, files: list[Path], dest: str = ".") -> None:
        for f in files:
            self._runner.run(["docker", "cp", str(f), f"{self._name}:/workspace/{dest}"])

    def close(self) -> None:
        if self._started:
            self._runner.run(["docker", "rm", "-f", self._name], timeout=60)
            self._started = False


@dataclass
class RawResult:
    exit_code: int
    output: str
    timed_out: bool = False


class CommandRunner:
    """Thin wrapper over subprocess for host commands (docker, compose).

    Isolated behind a class so tests can inject a fake and assert on the exact
    argv without a Docker daemon.
    """

    def run(self, args: list[str], timeout: int = 120) -> RawResult:
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout, errors="replace"
            )
        except FileNotFoundError as exc:
            return RawResult(127, f"command not found: {exc}")
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            return RawResult(124, out, timed_out=True)
        return RawResult(proc.returncode, (proc.stdout or "") + (proc.stderr or ""))


class ServiceDeployment:
    """Bring a challenge's networked service up/down via docker compose."""

    def __init__(self, challenge, runner: Optional[CommandRunner] = None):
        if not challenge.is_service:
            raise ValueError("ServiceDeployment requires a service challenge")
        self.challenge = challenge
        self.spec = challenge.delivery.service
        self._runner = runner or CommandRunner()
        self._project = f"ctfbench-{challenge.id}".replace("_", "-").lower()
        self._up = False

    @property
    def compose_file(self) -> Path:
        return self.challenge.path / self.spec.compose

    @property
    def network(self) -> str:
        # docker compose default network name.
        return f"{self._project}_default"

    @property
    def host(self) -> str:
        # Agents on the same compose network reach the service by name.
        return self.spec.service

    @property
    def port(self) -> int:
        return self.spec.port

    def up(self) -> None:
        args = [
            "docker", "compose", "-p", self._project,
            "-f", str(self.compose_file), "up", "-d", "--build",
        ]
        res = self._runner.run(args, timeout=self.spec.ready_timeout + 600)
        if res.exit_code != 0:
            raise RuntimeError(f"compose up failed: {res.output}")
        self._up = True
        self._wait_ready()

    def _wait_ready(self) -> None:
        deadline = time.time() + self.spec.ready_timeout
        while time.time() < deadline:
            logs = self._runner.run(
                ["docker", "compose", "-p", self._project, "-f",
                 str(self.compose_file), "logs", "--no-color"],
                timeout=30,
            )
            if self.spec.ready_log is None or self.spec.ready_log in logs.output:
                return
            time.sleep(1)
        # Not fatal: some services log nothing. Proceed and let the agent try.

    def down(self) -> None:
        if not self._up:
            return
        self._runner.run(
            ["docker", "compose", "-p", self._project, "-f",
             str(self.compose_file), "down", "-v", "--remove-orphans"],
            timeout=120,
        )
        self._up = False

    def __enter__(self) -> "ServiceDeployment":
        self.up()
        return self

    def __exit__(self, *exc) -> None:
        self.down()
