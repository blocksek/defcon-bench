# DEF CON CTF Qualifier 2026 — held-out set (pending release)

This directory is reserved for the **2026** quals. The point of a recent year is
**contamination control**: write-ups for 2022–2024 (and increasingly 2025) are
almost certainly in the training data of current models, so those years measure
recall as much as capability. The most recent quals are the cleanest held-out
test set.

## Status

As of the last update, **Nautilus Institute has not published the 2026 quals
source** (`https://github.com/Nautilus-Institute/quals-2026` is not yet public —
it is typically open-sourced after that summer's DEF CON finals). There are no
2026 challenges to vendor yet, so this directory is intentionally empty of
`challenge.yaml` files (the registry skips it).

## When 2026 is released

Package it exactly like the other years — nothing about the harness changes:

1. Clone the upstream release:
   `git clone https://github.com/Nautilus-Institute/quals-2026`
2. For each challenge you want, create `challenges/2026/<year>-<slug>/` with a
   `challenge.yaml`, vendor the minimal build/infra, and bake **our** controlled
   flag where the intended solution reads it. Follow
   [`../../docs/AUTHORING.md`](../../docs/AUTHORING.md) and the packaging notes
   in the repo's reference challenges.
3. `python3 -m ctfbench.cli validate` should report 0 issues for the new
   challenges.

Prefer challenges whose flag we control (a file the deployed service reads, or a
build that embeds our flag) so the ground truth is well-defined — the same rule
that governs the existing dataset. Record each challenge's write-up reference in
its `references:` block for solve verification.

Until then, **2025** is the newest packaged year and the closest available
held-out set.
