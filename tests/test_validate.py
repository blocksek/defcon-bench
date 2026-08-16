from ctfbench.cli import _validate_challenge
from ctfbench.models import Challenge


def _mk(tmp_path, **over):
    data = {
        "id": "t",
        "name": "T",
        "category": "misc",
        "description": "d",
        "flag": {"value": "flag{secret}"},
    }
    data.update(over)
    c = Challenge.from_dict(data)
    c.path = tmp_path
    return c


def test_validate_clean_offline_with_build(tmp_path):
    c = _mk(
        tmp_path,
        delivery={"type": "offline", "artifacts": ["a.bin"]},
        build={"type": "script", "script": "build.sh", "output": "dist"},
    )
    (tmp_path / "build.sh").write_text("#")
    # artifact will be produced by the build -> not flagged as missing
    assert _validate_challenge(c) == []


def test_validate_flags_leaked_artifact(tmp_path):
    c = _mk(tmp_path, delivery={"type": "offline", "artifacts": ["leak.txt"]})
    (tmp_path / "leak.txt").write_bytes(b"here is flag{secret} oops")
    issues = _validate_challenge(c)
    assert any("leaked" in i for i in issues)


def test_validate_flags_missing_compose(tmp_path):
    c = _mk(
        tmp_path,
        delivery={"type": "service", "service": {"service": "challenge", "port": 1337}},
        build={"type": "docker", "dockerfile": "d/Dockerfile"},
    )
    issues = _validate_challenge(c)
    assert any("compose file missing" in i for i in issues)
    assert any("dockerfile missing" in i for i in issues)
