import re

import pytest

from ctfbench.models import (
    Challenge,
    ChallengeError,
    Delivery,
    Flag,
    ServiceSpec,
)


def test_flag_exact_match_not_format_match():
    flag = Flag(value="flag{real}", format=r"flag\{[^}]*\}")
    assert flag.matches("flag{real}")
    assert flag.matches("  flag{real}\n")
    # format-shaped but wrong contents must not score
    assert not flag.matches("flag{guess}")


def test_flag_find_candidates_and_scan():
    flag = Flag(value="flag{abc}")
    text = "noise flag{abc} more flag{xyz}"
    assert flag.find_candidates(text) == ["flag{abc}", "flag{xyz}"]
    assert flag.scan(text)
    assert not flag.scan("nothing here")


def test_flag_rejects_empty():
    with pytest.raises(ChallengeError):
        Flag(value="   ")


def test_service_port_validation():
    with pytest.raises(ChallengeError):
        ServiceSpec(port=0)
    with pytest.raises(ChallengeError):
        ServiceSpec(port=99999)
    ServiceSpec(port=31337)  # ok


def test_delivery_service_requires_block():
    with pytest.raises(ChallengeError):
        Delivery(type="service", service=None)
    with pytest.raises(ChallengeError):
        Delivery(type="bogus")


def test_challenge_from_dict_minimal():
    c = Challenge.from_dict(
        {
            "id": "x",
            "name": "X",
            "category": "misc",
            "description": "do it",
            "flag": {"value": "flag{y}"},
        }
    )
    assert c.id == "x"
    assert not c.is_service
    assert c.flag.matches("flag{y}")


def test_challenge_rejects_unknown_fields():
    with pytest.raises(ChallengeError):
        Challenge.from_dict(
            {
                "id": "x",
                "name": "X",
                "category": "misc",
                "description": "d",
                "flag": {"value": "flag{y}"},
                "bogus": 1,
            }
        )


def test_challenge_service_roundtrip():
    c = Challenge.from_dict(
        {
            "id": "svc",
            "name": "Svc",
            "category": "pwn",
            "description": "d",
            "flag": {"value": "flag{y}"},
            "delivery": {
                "type": "service",
                "service": {"service": "challenge", "port": 1337},
            },
            "build": {"type": "docker", "dockerfile": "d/Dockerfile"},
        }
    )
    assert c.is_service
    assert c.delivery.service.port == 1337
