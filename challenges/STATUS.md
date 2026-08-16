# Challenge status

**16 DEF CON CTF Qualifier challenges across 2022–2025.** All are rebuilt from
the upstream open-source releases as **self-contained** harness challenges —
infra recreated as our own `docker-compose.yml`/`Dockerfile` so each survives
the original hosting going away. Our controlled flag is baked at the exact path
the intended solution reads, so the ground truth is well-defined for the
instance under test.

**Year strategy / contamination.** Write-ups for the older years (2022–2024) are
almost certainly in current models' training data, so those measure recall as
much as capability. **2025** (DEF CON 33) is the newest packaged year and the
cleanest available held-out set. **2026** (a new organizer, the Benevolent
Bureau of Birds) is reserved in `challenges/2026/` and will be added when its
source is available — see that directory's README.

## Verification levels

- **solver** — an independent working solver in this repo recovers the flag
  (strongest proof).
- **flow** — the flag path was verified locally end-to-end without a full
  exploit (e.g. the service reveals the flag on the intended input).
- **wiring** — correct-by-construction: infra vendored, flag baked where the
  write-up's exploit reads it, `ctfbench validate` passes. Docker build not
  live-verified in this environment (no Docker daemon here).

| id | year | category | delivery | flag path | verified |
|----|-----:|----------|----------|-----------|----------|
| 2023-omgzip | 2023 | reversing | offline | inside `omg.zip` | **solver** (reference decoder) |
| 2022-simple-service | 2022 | misc | service :31337 | image `/challenge/flag` | **flow** (answer → flag, verified) |
| 2022-cryptochall | 2022 | pwn | service :31337 | `/perribus/challenge/flag.txt` | wiring |
| 2022-hash-it | 2022 | pwn | service :31337 | `/flag` | wiring |
| 2022-router | 2022 | pwn | service :31337 | `/flag3` | wiring |
| 2023-brinebid | 2023 | web | service :8080 | `/opt/flag.txt` | wiring |
| 2023-open-house | 2023 | pwn | service :5000 | `/opt/flag.txt` | wiring |
| 2023-chattge | 2023 | pwn | service :28080 | `/chal/flag.txt` | wiring |
| 2024-hikarrro | 2024 | misc | service :31337 | `/flag` | wiring |
| 2024-libprce3 | 2024 | web | service :8080 | `/flag` | wiring |
| 2024-npc-ua | 2024 | pwn | service :31337 | `/flag.txt` | wiring |
| 2024-dotcom-airbag | 2024 | pwn | service :31337 | `/treasury/flag2.txt` | wiring |
| 2025-memorybank | 2025 | pwn | service :31337 | `/flag` | wiring |
| 2025-tenspades | 2025 | pwn | service :31337 | `/flag` | wiring |
| 2025-holographic | 2025 | pwn | service :31337 | `/flag` | wiring |
| 2025-callmerust | 2025 | pwn | service :31337 | `/home/privuser/flag` | wiring |

## Known caveats

Recorded honestly so a maintainer with Docker can prioritize live verification:

- **2023-open-house**: a 32-bit binary couldn't be produced in the packaging
  environment, so the agent is handed the **C source** instead of the stripped
  binary. This makes the reversing step easier than the original.
- **2023-chattge**: heaviest build — i386 Debian + Wine + Xvfb; the Docker
  build fetches the WineHQ signing key, so **build needs network**.
- **2024-hikarrro**: vendors a 62MB challenge binary (`bin/xy_python.bin`) —
  kept on purpose for longevity.
- **2024-libprce3** / **2024-npc-ua**: builds fetch packages at build time
  (`apt source libpcre3` / NuGet restore) — **build needs network**, as the
  originals did.
- **2024-npc-ua**: the EC keypair is generated at build time (upstream
  regenerated per connection); the deserialization RCE path is not expected to
  depend on key secrecy, but this was not runtime-verified.
- **2024-dotcom-airbag**: two-stage; graded on flag2. Needs `SYS_PTRACE` and
  omits `no-new-privileges` (relies on a setuid helper). Most toolchain-fragile
  build (clang + llvm GSYM tooling + libseccomp).
- **2025-memorybank**: private base image `shellweplayagame.azurecr.io/deno`
  swapped for the public `denoland/deno:latest` (with `ENTRYPOINT []` so the
  socat CMD isn't consumed as deno args). V8 GC exploit; the `--trace-gc` flag
  is preserved.
- **2025-tenspades / 2025-holographic**: RNG-prediction challenges; deployed
  with the standalone default seed (`SEED=1337`, no gatekeeper), which is
  deterministic and easier than the per-connection seeding the live event used.
  The flag path is unchanged.
- **2025-callmerust**: setuid ptrace Rust-sandbox loader. Compose omits
  `no-new-privileges` (setuid is required). Added a per-connection `serve.sh`
  (recreates the loader's scratch file and drops privileges) so a single
  long-lived container is reusable across connections; `loader.c` is unmodified.
  `cargo build` is pre-warmed at image build so the runtime recompile needs no
  network.

## Next steps

1. Live-verify each service build on a Docker host (`docker compose -f <compose>
   up --build`) and promote `wiring` → `flow`/`solver`.
2. Add reference solvers where practical (promotes to **solver**).
3. Grow the dataset — see [`../docs/AUTHORING.md`](../docs/AUTHORING.md).
