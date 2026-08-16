"""Validate every bundled challenge loads and never leaks its flag."""

import zipfile

import pytest

from ctfbench import registry


def test_discover_finds_challenges():
    challenges = registry.discover()
    ids = {c.id for c in challenges}
    assert "2023-omgzip" in ids
    assert "2022-simple-service" in ids
    assert len(challenges) >= 2


@pytest.mark.parametrize("challenge", registry.discover(), ids=lambda c: c.id)
def test_challenge_wellformed(challenge):
    # required fields present, delivery/build validated by dataclasses on load
    assert challenge.id and challenge.name and challenge.category
    assert challenge.description.strip()
    assert challenge.flag.value
    if challenge.is_service:
        assert challenge.delivery.service is not None
        assert 0 < challenge.delivery.service.port <= 65535


@pytest.mark.parametrize("challenge", registry.discover(), ids=lambda c: c.id)
def test_flag_not_committed_in_artifacts(challenge):
    """The ground-truth flag must not sit verbatim in any committed artifact.

    (Built artifacts live in gitignored dist/; committed source must not
    contain the plaintext flag.)
    """
    flag = challenge.flag.value
    for art in challenge.delivery.artifacts:
        p = challenge.path / art
        if not p.exists():
            continue  # produced at build time into dist/
        data = p.read_bytes()
        assert flag.encode() not in data, f"flag leaked in committed artifact {p}"
