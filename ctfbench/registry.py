"""Discover and load challenges from the ``challenges/`` tree."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import yaml

from .models import Challenge, ChallengeError

CHALLENGE_FILE = "challenge.yaml"


def _repo_root() -> Path:
    # ctfbench/registry.py -> repo root is one level up from the package dir.
    return Path(__file__).resolve().parent.parent


def default_challenges_dir() -> Path:
    return _repo_root() / "challenges"


def load_challenge(path: Path) -> Challenge:
    """Load a single challenge from a directory or its ``challenge.yaml``."""
    path = Path(path)
    yaml_path = path / CHALLENGE_FILE if path.is_dir() else path
    if not yaml_path.exists():
        raise ChallengeError(f"no {CHALLENGE_FILE} at {yaml_path}")
    with yaml_path.open() as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ChallengeError(f"{yaml_path} does not contain a mapping")
    return Challenge.from_dict(data, path=yaml_path.parent)


def discover(root: Optional[Path] = None) -> list[Challenge]:
    """Load every challenge under ``root`` (default: ``challenges/``).

    Directories containing a ``challenge.yaml`` are treated as challenges.
    Results are sorted by id for stable ordering.
    """
    root = Path(root) if root else default_challenges_dir()
    challenges: list[Challenge] = []
    if not root.exists():
        return challenges
    for yaml_path in sorted(root.rglob(CHALLENGE_FILE)):
        challenges.append(load_challenge(yaml_path.parent))
    challenges.sort(key=lambda c: c.id)
    return challenges


def select(
    ids: Optional[Iterable[str]] = None,
    *,
    root: Optional[Path] = None,
    category: Optional[str] = None,
    year: Optional[int] = None,
) -> list[Challenge]:
    """Return challenges filtered by id / category / year."""
    all_ch = discover(root)
    id_set = set(ids) if ids else None
    out = []
    for c in all_ch:
        if id_set is not None and c.id not in id_set:
            continue
        if category is not None and c.category != category:
            continue
        if year is not None and c.year != year:
            continue
        out.append(c)
    if id_set is not None:
        found = {c.id for c in out}
        missing = id_set - found
        if missing:
            raise ChallengeError(f"unknown challenge id(s): {sorted(missing)}")
    return out
