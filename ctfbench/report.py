"""Aggregate run results into JSON and a Markdown scoreboard."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .models import RunResult


def to_json(results: Iterable[RunResult]) -> str:
    return json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False)


def summarize(results: list[RunResult]) -> dict:
    by_model: dict[str, list[RunResult]] = defaultdict(list)
    for r in results:
        by_model[r.model].append(r)
    summary = {}
    for model, rs in by_model.items():
        solved = sum(1 for r in rs if r.solved)
        summary[model] = {
            "solved": solved,
            "total": len(rs),
            "solve_rate": round(solved / len(rs), 3) if rs else 0.0,
            "points": sum(r.points for r in rs),
        }
    return summary


def to_markdown(results: list[RunResult]) -> str:
    summary = summarize(results)
    lines = ["# ctfbench results", ""]

    lines.append("## Scoreboard")
    lines.append("")
    lines.append("| Model | Solved | Total | Solve rate | Points |")
    lines.append("|-------|-------:|------:|-----------:|-------:|")
    for model, s in sorted(summary.items(), key=lambda kv: (-kv[1]["points"], kv[0])):
        lines.append(
            f"| {model} | {s['solved']} | {s['total']} | {s['solve_rate']:.1%} "
            f"| {s['points']} |"
        )
    lines.append("")

    lines.append("## Per-challenge")
    lines.append("")
    lines.append("| Challenge | Model | Result | Steps | Time (s) | Notes |")
    lines.append("|-----------|-------|--------|------:|---------:|-------|")
    for r in sorted(results, key=lambda r: (r.challenge_id, r.model)):
        mark = "✅ solved" if r.solved else "❌ failed"
        note = r.error or (r.submitted_flag or "")
        note = note.replace("|", "\\|")[:60]
        lines.append(
            f"| {r.challenge_id} | {r.model} | {mark} | {r.steps} | "
            f"{r.duration_s:.1f} | {note} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_reports(results: list[RunResult], out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "results.json"
    md_path = out_dir / "results.md"
    json_path.write_text(to_json(results))
    md_path.write_text(to_markdown(results))
    return json_path, md_path
