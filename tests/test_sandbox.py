"""Tests for sandbox command construction and local execution.

Docker/compose calls are asserted against a fake CommandRunner so no daemon is
needed. LocalSandbox is exercised for real (it just uses subprocess).
"""

from ctfbench.sandbox import (
    DockerSandbox,
    LocalSandbox,
    RawResult,
    ServiceDeployment,
)


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, args, timeout=120):
        self.calls.append(args)
        return RawResult(0, "")


def test_local_sandbox_runs_and_isolates(tmp_path):
    sb = LocalSandbox()
    try:
        res = sb.run("echo hello && pwd")
        assert res.exit_code == 0
        assert "hello" in res.output
    finally:
        sb.close()


def test_local_sandbox_timeout():
    sb = LocalSandbox()
    try:
        res = sb.run("sleep 5", timeout=1)
        assert res.timed_out
    finally:
        sb.close()


def test_docker_sandbox_builds_expected_argv():
    runner = FakeRunner()
    sb = DockerSandbox(image="img:latest", network="net", name="box", runner=runner)
    # first call starts the container
    start = runner.calls[0]
    assert start[:3] == ["docker", "run", "-d"]
    assert "--network" in start and "net" in start
    assert "img:latest" in start

    sb.run("id")
    exec_call = runner.calls[-1]
    assert exec_call[:2] == ["docker", "exec"]
    assert exec_call[-3:] == ["bash", "-lc", "id"]

    sb.close()
    assert runner.calls[-1][:3] == ["docker", "rm", "-f"]


def test_service_deployment_compose_argv():
    from ctfbench.models import Challenge

    ch = Challenge.from_dict(
        {
            "id": "svc-x",
            "name": "X",
            "category": "pwn",
            "description": "d",
            "flag": {"value": "flag{y}"},
            "delivery": {
                "type": "service",
                "service": {"service": "challenge", "port": 1337,
                            "compose": "docker-compose.yml"},
            },
        }
    )
    import pathlib
    ch.path = pathlib.Path("/tmp/svc-x")
    runner = FakeRunner()
    dep = ServiceDeployment(ch, runner=runner)
    dep.up()
    up = runner.calls[0]
    assert up[:3] == ["docker", "compose", "-p"]
    assert "up" in up and "-d" in up and "--build" in up
    assert dep.host == "challenge" and dep.port == 1337
    dep.down()
    assert "down" in runner.calls[-1]
