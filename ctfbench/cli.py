"""Command-line interface: ``ctfbench list|show|build|run|report``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from . import registry, report
from .agent.base import AgentConfig
from .agent.mock_provider import MockProvider
from .build import ensure_built
from .models import Challenge
from .runner import Runner


def _make_provider(model: str):
    """Instantiate a provider from a ``backend:model`` spec.

    Examples: ``openai:gpt-4o``, ``mock`` (no solve), ``mock:<not-used>``.
    """
    if model == "mock" or model.startswith("mock:"):
        return MockProvider(), "mock"
    if ":" in model:
        backend, name = model.split(":", 1)
    else:
        backend, name = "openai", model
    if backend == "openai":
        from .agent.openai_provider import OpenAIProvider

        return OpenAIProvider(model=name), name
    raise SystemExit(f"unknown backend: {backend}")


def _ctfd_password(user: str) -> str:
    # Deterministic per-user password so re-runs can log the same user back in.
    import hashlib

    return "bench-" + hashlib.sha256(f"ctfbench:{user}".encode()).hexdigest()[:20]


def _make_ctfd_scorer(args, model_label: str, challenges):
    """Build a CTFdScorer bound to a per-model user, importing challenges first."""
    from .ctfd import CTFdClient, ensure_user, import_challenges
    from .scoring import CTFdScorer

    token = args.ctfd_token or os.environ.get("CTFD_TOKEN")
    if not args.ctfd_url or not token:
        raise SystemExit("CTFd scoring needs --ctfd-url and --ctfd-token (or $CTFD_TOKEN)")

    client = CTFdClient(args.ctfd_url, admin_token=token)
    mapping = import_challenges(client, challenges)

    password = _ctfd_password(model_label)
    ensure_user(client, model_label, password)
    session = client.login_user(model_label, password)

    def resolve_id(ch):
        return mapping.get(ch.id) or client.find_challenge_id(ch.name)

    return CTFdScorer(session, resolve_id)


def cmd_ctfd(args) -> int:
    """Manage the CTFd scoreboard: import challenges or print the scoreboard."""
    from .ctfd import CTFdClient, import_challenges

    token = args.ctfd_token or os.environ.get("CTFD_TOKEN")
    if not args.ctfd_url or not token:
        raise SystemExit("needs --ctfd-url and --ctfd-token (or $CTFD_TOKEN)")
    client = CTFdClient(args.ctfd_url, admin_token=token)

    if args.ctfd_command == "import":
        challenges = registry.discover(args.challenges_dir)
        mapping = import_challenges(client, challenges)
        for cid, ctfd_id in sorted(mapping.items()):
            print(f"{cid:<24} -> CTFd #{ctfd_id}")
        print(f"\nimported/matched {len(mapping)} challenge(s)")
        return 0
    if args.ctfd_command == "scoreboard":
        board = client.scoreboard()
        for row in board:
            print(f"{row.get('pos','?'):>3}  {row.get('name','?'):<24} {row.get('score','?')}")
        return 0
    return 1


def cmd_list(args) -> int:
    challenges = registry.discover(args.challenges_dir)
    if not challenges:
        print("no challenges found")
        return 0
    width = max(len(c.id) for c in challenges)
    for c in challenges:
        svc = "service" if c.is_service else "offline"
        print(f"{c.id:<{width}}  {c.category:<12} {c.difficulty:<8} {svc:<8} {c.name}")
    print(f"\n{len(challenges)} challenge(s)")
    return 0


def cmd_show(args) -> int:
    c = _load_one(args)
    print(f"id:         {c.id}")
    print(f"name:       {c.name}")
    print(f"event:      {c.event} {c.year or ''}".rstrip())
    print(f"category:   {c.category}")
    print(f"difficulty: {c.difficulty}")
    print(f"delivery:   {c.delivery.type}")
    if c.is_service:
        s = c.delivery.service
        print(f"service:    {s.service}:{s.port} (compose {s.compose})")
    if c.delivery.artifacts:
        print(f"artifacts:  {', '.join(c.delivery.artifacts)}")
    if c.source and c.source.upstream:
        print(f"source:     {c.source.upstream} ({c.source.path})")
    print("\n--- description ---")
    print(c.description.strip())
    return 0


def cmd_build(args) -> int:
    c = _load_one(args)
    ensure_built(c, force=args.force)
    print(f"built {c.id}: artifacts -> {c.path / c.build.output}")
    return 0


def cmd_validate(args) -> int:
    """Static lint over the dataset: structural + safety checks, no Docker."""
    challenges = registry.discover(args.challenges_dir)
    if not challenges:
        print("no challenges found")
        return 1
    problems = 0
    for c in challenges:
        issues = _validate_challenge(c)
        status = "ok" if not issues else f"{len(issues)} issue(s)"
        print(f"{c.id:<24} {status}")
        for msg in issues:
            print(f"    - {msg}")
            problems += 1
    print(f"\n{len(challenges)} challenge(s), {problems} issue(s)")
    return 0 if problems == 0 else 1


def _validate_challenge(c: Challenge) -> list[str]:
    issues: list[str] = []
    assert c.path is not None
    flag = c.flag.value

    # Committed artifacts must not contain the plaintext flag.
    for art in c.delivery.artifacts:
        p = c.path / art
        if p.exists() and flag.encode() in p.read_bytes():
            issues.append(f"flag leaked in committed artifact {art}")

    if c.is_service:
        svc = c.delivery.service
        compose = c.path / svc.compose
        if not compose.exists():
            issues.append(f"compose file missing: {svc.compose}")
    else:
        # Offline: artifacts must exist now, or be produced by a build step.
        for art in c.delivery.artifacts:
            built = c.path / c.build.output / art
            if not (c.path / art).exists() and not built.exists():
                if c.build.type == "none":
                    issues.append(f"artifact missing and no build step: {art}")

    if c.build.type == "docker" and c.build.dockerfile:
        if not (c.path / c.build.dockerfile).exists():
            issues.append(f"dockerfile missing: {c.build.dockerfile}")
    if c.build.type == "script" and c.build.script:
        if not (c.path / c.build.script).exists():
            issues.append(f"build script missing: {c.build.script}")
    return issues


def cmd_run(args) -> int:
    challenges = registry.select(
        ids=args.challenge or None,
        root=args.challenges_dir,
        category=args.category,
        year=args.year,
    )
    if not challenges:
        print("no matching challenges")
        return 1

    provider, label = _make_provider(args.model)
    runner = Runner(
        use_docker=not args.no_docker,
        solver_image=args.solver_image,
        transcripts_dir=Path(args.out) / "transcripts" if args.out else None,
        verbose=args.verbose,
    )
    config = AgentConfig(max_steps=args.max_steps, verbose=args.verbose)

    scorer = None
    if args.scoreboard == "ctfd":
        scorer = _make_ctfd_scorer(args, label, challenges)
        print(f"scoring via CTFd at {args.ctfd_url} as user '{label}'")

    results = []
    for c in challenges:
        print(f"==> {c.id} [{label}]")
        res = runner.run(c, provider, model_label=label, config=config, scorer=scorer)
        status = "SOLVED" if res.solved else "failed"
        pts = f" +{res.points}" if res.points else ""
        extra = f" ({res.error})" if res.error else ""
        print(f"    {status}{pts} in {res.steps} steps, {res.duration_s:.1f}s{extra}")
        results.append(res)

    if args.out:
        json_path, md_path = report.write_reports(results, Path(args.out))
        print(f"\nreports: {json_path}  {md_path}")
    else:
        print()
        print(report.to_markdown(results))

    solved = sum(1 for r in results if r.solved)
    print(f"\n{solved}/{len(results)} solved")
    return 0 if solved == len(results) else 2


def _load_one(args) -> Challenge:
    matches = registry.select(ids=[args.challenge], root=args.challenges_dir)
    return matches[0]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ctfbench", description=__doc__)
    p.add_argument(
        "--challenges-dir",
        type=Path,
        default=None,
        help="root of the challenges tree (default: bundled challenges/)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    lp = sub.add_parser("list", help="list challenges")
    lp.set_defaults(func=cmd_list)

    sp = sub.add_parser("show", help="show one challenge")
    sp.add_argument("challenge")
    sp.set_defaults(func=cmd_show)

    bp = sub.add_parser("build", help="build a challenge's artifacts")
    bp.add_argument("challenge")
    bp.add_argument("--force", action="store_true")
    bp.set_defaults(func=cmd_build)

    vp = sub.add_parser("validate", help="static lint over the dataset")
    vp.set_defaults(func=cmd_validate)

    rp = sub.add_parser("run", help="run an agent against challenges")
    rp.add_argument("challenge", nargs="*", help="challenge id(s); default all")
    rp.add_argument("--model", default="mock",
                    help="backend:model, e.g. openai:gpt-4o, or 'mock'")
    rp.add_argument("--category", default=None)
    rp.add_argument("--year", type=int, default=None)
    rp.add_argument("--max-steps", type=int, default=30)
    rp.add_argument("--no-docker", action="store_true",
                    help="run the agent shell locally instead of in Docker")
    rp.add_argument("--solver-image", default="ctfbench/solver:latest")
    rp.add_argument("--out", default=None, help="write JSON+MD reports here")
    rp.add_argument("--verbose", action="store_true")
    rp.add_argument("--scoreboard", choices=["local", "ctfd"], default="local",
                    help="where flags are judged (default local exact-match)")
    rp.add_argument("--ctfd-url", default=None, help="CTFd base URL (scoreboard=ctfd)")
    rp.add_argument("--ctfd-token", default=None,
                    help="CTFd admin access token (or set $CTFD_TOKEN)")
    rp.set_defaults(func=cmd_run)

    cp = sub.add_parser("ctfd", help="manage the CTFd scoreboard")
    cp.add_argument("ctfd_command", choices=["import", "scoreboard"])
    cp.add_argument("--ctfd-url", default=None, help="CTFd base URL")
    cp.add_argument("--ctfd-token", default=None,
                    help="CTFd admin access token (or set $CTFD_TOKEN)")
    cp.set_defaults(func=cmd_ctfd)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
