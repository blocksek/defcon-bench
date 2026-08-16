"""Command-line interface: ``ctfbench list|show|build|run|report``."""

from __future__ import annotations

import argparse
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

    results = []
    for c in challenges:
        print(f"==> {c.id} [{label}]")
        res = runner.run(c, provider, model_label=label, config=config)
        status = "SOLVED" if res.solved else "failed"
        extra = f" ({res.error})" if res.error else ""
        print(f"    {status} in {res.steps} steps, {res.duration_s:.1f}s{extra}")
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
    rp.set_defaults(func=cmd_run)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
