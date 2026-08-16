"""ctfbench: an eval harness for LLM agents solving CTF challenges.

The benchmark is seeded with challenges from the DEF CON CTF Qualifiers
(open-source releases by the Nautilus Institute). Each challenge is
described declaratively (``challenge.yaml``); the harness builds its
infrastructure with Docker, hands the player-facing artifacts to a
tool-calling agent, lets the agent work end-to-end, and grades the flag it
recovers against a ground truth the agent never sees.
"""

from .models import Challenge, Delivery, Flag, RunResult, ChallengeError

__all__ = [
    "Challenge",
    "Delivery",
    "Flag",
    "RunResult",
    "ChallengeError",
    "__version__",
]

__version__ = "0.1.0"
