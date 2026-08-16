"""Core data model for a benchmark challenge and a run result.

A challenge on disk is a directory containing a ``challenge.yaml`` plus the
files needed to build and serve it. The YAML deserializes into the
dataclasses below. Nothing here touches Docker, the network, or an LLM --
this module is pure data so it can be imported and unit-tested cheaply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class ChallengeError(Exception):
    """Raised when a challenge definition is malformed."""


# --------------------------------------------------------------------------
# Flag / grading
# --------------------------------------------------------------------------


@dataclass
class Flag:
    """Ground truth for grading plus the format shown to the agent.

    ``value`` is the exact flag the agent must recover. It is loaded from the
    challenge directory (inline or from a file) and is *never* included in the
    material handed to the agent. ``format`` is a regex describing what a valid
    flag looks like (e.g. ``flag\\{.*\\}``); it is shown to the agent so it
    knows what it is hunting for, and is also used to extract flag candidates
    from tool output.
    """

    value: str
    format: str = r"flag\{[^}]*\}"

    def __post_init__(self) -> None:
        self.value = self.value.strip()
        if not self.value:
            raise ChallengeError("flag value is empty")
        try:
            self._format_re = re.compile(self.format)
        except re.error as exc:  # pragma: no cover - defensive
            raise ChallengeError(f"invalid flag format regex: {exc}") from exc

    def matches(self, candidate: str) -> bool:
        """True if ``candidate`` is exactly the ground-truth flag.

        Comparison is exact after stripping surrounding whitespace. The
        ``format`` regex is deliberately *not* used here -- format only gates
        what counts as a candidate; correctness is exact-match so a
        format-shaped guess never scores.
        """
        return candidate.strip() == self.value

    def find_candidates(self, text: str) -> list[str]:
        """Return every substring of ``text`` matching the flag format."""
        return self._format_re.findall(text)

    def scan(self, text: str) -> bool:
        """True if the ground-truth flag appears verbatim in ``text``."""
        return self.value in text


# --------------------------------------------------------------------------
# Delivery: how the challenge reaches the agent
# --------------------------------------------------------------------------


@dataclass
class ServiceSpec:
    """A networked service the agent connects to.

    The service is brought up from a docker-compose file. ``service`` names the
    compose service that exposes the challenge; ``port`` is the container port
    the agent should target. ``ready_log`` / ``ready_timeout`` control how the
    harness waits for the service to become reachable.
    """

    compose: str = "docker-compose.yml"
    service: str = "challenge"
    port: int = 0
    ready_log: Optional[str] = None
    ready_timeout: int = 60

    def __post_init__(self) -> None:
        if not (0 < self.port <= 65535):
            raise ChallengeError(f"service.port out of range: {self.port}")


@dataclass
class Delivery:
    """How the challenge is presented to the agent.

    - ``offline``: the agent is given ``artifacts`` (files) and must recover
      the flag locally. No network service.
    - ``service``: a networked service is deployed and the agent is told its
      host/port. ``artifacts`` may still be provided (e.g. a binary to reverse
      that also runs remotely).
    """

    type: str = "offline"  # "offline" | "service"
    artifacts: list[str] = field(default_factory=list)
    service: Optional[ServiceSpec] = None

    def __post_init__(self) -> None:
        if self.type not in ("offline", "service"):
            raise ChallengeError(f"unknown delivery.type: {self.type}")
        if self.type == "service" and self.service is None:
            raise ChallengeError("delivery.type=service requires a service block")


# --------------------------------------------------------------------------
# Build: how to produce artifacts / images
# --------------------------------------------------------------------------


@dataclass
class BuildSpec:
    """How to materialize the challenge before a run.

    - ``none``: artifacts are already committed in the challenge dir.
    - ``script``: run ``script`` (relative to the challenge dir) to produce
      artifacts into ``output`` (default ``dist``).
    - ``docker``: build ``dockerfile`` and copy ``artifacts`` out (handled by
      the service/deployment layer for service challenges).
    """

    type: str = "none"  # "none" | "script" | "docker"
    script: Optional[str] = None
    output: str = "dist"
    dockerfile: Optional[str] = None
    context: str = "."

    def __post_init__(self) -> None:
        if self.type not in ("none", "script", "docker"):
            raise ChallengeError(f"unknown build.type: {self.type}")
        if self.type == "script" and not self.script:
            raise ChallengeError("build.type=script requires a script")


# --------------------------------------------------------------------------
# Challenge
# --------------------------------------------------------------------------


@dataclass
class SourceInfo:
    upstream: Optional[str] = None
    path: Optional[str] = None
    license: Optional[str] = None
    commit: Optional[str] = None


@dataclass
class Challenge:
    """A single benchmark task, loaded from ``<dir>/challenge.yaml``."""

    id: str
    name: str
    category: str
    description: str
    flag: Flag
    year: Optional[int] = None
    event: str = "DEF CON CTF Qualifier"
    difficulty: str = "unknown"
    points: int = 0
    tags: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    delivery: Delivery = field(default_factory=Delivery)
    build: BuildSpec = field(default_factory=BuildSpec)
    source: Optional[SourceInfo] = None
    # Write-up URLs / notes describing the intended solution. Used to confirm a
    # solve is genuine (does the agent's path match a known-good one?) and to
    # document how the packaged instance is meant to be broken.
    references: list[str] = field(default_factory=list)
    # Populated by the registry loader; the directory the YAML lives in.
    path: Optional[Path] = None

    # -- construction -------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, path: Optional[Path] = None) -> "Challenge":
        data = dict(data)
        flag = _build_flag(data.pop("flag", None), path)
        delivery = _build_delivery(data.pop("delivery", None))
        build = _build_build(data.pop("build", None))
        source = _build_source(data.pop("source", None))

        required = ("id", "name", "category", "description")
        for key in required:
            if not data.get(key):
                raise ChallengeError(f"challenge is missing required field: {key}")

        known = {
            "id", "name", "category", "description", "year", "event",
            "difficulty", "points", "tags", "authors", "references",
        }
        kwargs = {k: v for k, v in data.items() if k in known}
        unknown = set(data) - known - {"solver"}  # 'solver' is metadata-only
        if unknown:
            raise ChallengeError(f"unknown challenge fields: {sorted(unknown)}")

        return cls(
            flag=flag,
            delivery=delivery,
            build=build,
            source=source,
            path=path,
            **kwargs,
        )

    # -- helpers ------------------------------------------------------------

    @property
    def is_service(self) -> bool:
        return self.delivery.type == "service"

    def artifact_paths(self) -> list[Path]:
        """Absolute paths of the files handed to the agent.

        Artifacts are resolved relative to the build output dir if it exists
        (so freshly built files win), otherwise relative to the challenge dir.
        """
        if self.path is None:
            raise ChallengeError("challenge.path is not set; load via the registry")
        out = self.path / self.build.output
        resolved: list[Path] = []
        for name in self.delivery.artifacts:
            built = out / name
            resolved.append(built if built.exists() else self.path / name)
        return resolved


def _build_flag(raw: Any, path: Optional[Path]) -> Flag:
    if raw is None:
        raise ChallengeError("challenge is missing a flag block")
    fmt = raw.get("format", r"flag\{[^}]*\}")
    if "value" in raw and raw["value"] is not None:
        return Flag(value=str(raw["value"]), format=fmt)
    vf = raw.get("value_file")
    if vf:
        if path is None:
            raise ChallengeError("flag.value_file requires a challenge path")
        fp = path / vf
        if not fp.exists():
            raise ChallengeError(f"flag.value_file not found: {fp}")
        return Flag(value=fp.read_text().strip(), format=fmt)
    raise ChallengeError("flag block needs 'value' or 'value_file'")


def _build_delivery(raw: Any) -> Delivery:
    if raw is None:
        return Delivery()
    raw = dict(raw)
    svc_raw = raw.pop("service", None)
    service = ServiceSpec(**svc_raw) if svc_raw else None
    return Delivery(
        type=raw.get("type", "offline"),
        artifacts=list(raw.get("artifacts", [])),
        service=service,
    )


def _build_build(raw: Any) -> BuildSpec:
    if raw is None:
        return BuildSpec()
    return BuildSpec(**raw)


def _build_source(raw: Any) -> Optional[SourceInfo]:
    if raw is None:
        return None
    return SourceInfo(**raw)


# --------------------------------------------------------------------------
# Run result
# --------------------------------------------------------------------------


@dataclass
class RunResult:
    """Outcome of running one agent against one challenge."""

    challenge_id: str
    model: str
    solved: bool
    submitted_flag: Optional[str] = None
    steps: int = 0
    duration_s: float = 0.0
    error: Optional[str] = None
    transcript_path: Optional[str] = None
    points: int = 0
    score_backend: str = "local"
    score_status: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "model": self.model,
            "solved": self.solved,
            "submitted_flag": self.submitted_flag,
            "steps": self.steps,
            "duration_s": round(self.duration_s, 2),
            "error": self.error,
            "transcript_path": self.transcript_path,
            "points": self.points,
            "score_backend": self.score_backend,
            "score_status": self.score_status,
        }
