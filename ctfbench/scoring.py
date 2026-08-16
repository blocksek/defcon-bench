"""Pluggable scoring: where a submitted flag is judged and recorded.

The agent's submission contract never changes -- it calls the ``submit_flag``
tool. What happens behind that call is a ``Scorer``:

  * ``LocalScorer`` -- exact-match against the challenge's ground truth, in
    process. Zero dependencies; the default and the CI/offline path.
  * ``CTFdScorer`` -- forwards the flag to a live CTFd scoreboard as the model's
    user (``POST /api/v1/challenges/attempt``) and takes CTFd's verdict as
    authoritative. This makes the score visible on a real scoreboard and lets
    models be compared as competitors.

The harness (not the agent) performs the POST: the agent submits a string, the
runner routes it to the active scorer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Challenge


@dataclass
class ScoreResult:
    """Verdict for one submitted flag."""

    correct: bool
    status: str  # correct | incorrect | already_solved | no_submission | error | ...
    points: int = 0
    message: str = ""
    backend: str = "local"

    @property
    def solved(self) -> bool:
        return self.correct or self.status == "already_solved"


class Scorer:
    backend = "base"

    def submit(self, challenge: Challenge, flag: Optional[str]) -> ScoreResult:
        raise NotImplementedError


class LocalScorer(Scorer):
    """Exact-match against ground truth, in process."""

    backend = "local"

    def submit(self, challenge: Challenge, flag: Optional[str]) -> ScoreResult:
        if not flag:
            return ScoreResult(False, "no_submission", backend=self.backend)
        if challenge.flag.matches(flag):
            return ScoreResult(True, "correct", challenge.points, "correct", self.backend)
        return ScoreResult(False, "incorrect", 0, "incorrect flag", self.backend)


class CTFdScorer(Scorer):
    """Submit to a live CTFd instance as a specific competitor.

    ``session`` is a logged-in :class:`ctfbench.ctfd.CTFdUserSession`.
    ``resolve_id`` maps a benchmark :class:`Challenge` to its CTFd challenge id
    (by an explicit map, or by looking the name up on the server).
    """

    backend = "ctfd"

    def __init__(self, session, resolve_id):
        self._session = session
        self._resolve_id = resolve_id

    def submit(self, challenge: Challenge, flag: Optional[str]) -> ScoreResult:
        if not flag:
            return ScoreResult(False, "no_submission", backend=self.backend)
        cid = self._resolve_id(challenge)
        if cid is None:
            return ScoreResult(
                False, "error", 0,
                f"challenge {challenge.id} not found on CTFd", self.backend,
            )
        status, message = self._session.attempt(cid, flag)
        correct = status in ("correct", "already_solved")
        points = challenge.points if correct else 0
        return ScoreResult(correct, status, points, message, self.backend)
