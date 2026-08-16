# Scoring

The agent's submission contract never changes: it calls the `submit_flag` tool
with a string. What judges that string is a pluggable **`Scorer`**. The agent
does *not* talk to the scoreboard directly — the **harness forwards** the
submitted flag to the active scorer. This keeps the agent provider-agnostic and
keeps flag-handling in one place.

```
agent.submit_flag("flag{…}")  ─▶  harness  ─▶  Scorer.submit(challenge, flag)  ─▶  verdict + points
```

If the agent never calls `submit_flag` but a format-matching flag is visible in
its tool output, the harness submits that candidate too, so a genuine find still
scores.

## Backends

### `local` (default)

Exact-match against the challenge's ground truth, in process. Zero
dependencies. Used for CI, offline challenges, and quick iteration. A
format-shaped guess with the wrong contents never scores.

```bash
ctfbench run 2023-omgzip --model openai:gpt-4o          # scoreboard=local
```

### `ctfd`

Submissions go to a live [CTFd](https://ctfd.io/) instance as the model's user
(`POST /api/v1/challenges/attempt`); **CTFd's verdict is authoritative** and its
scoreboard shows the score, with each model appearing as a competitor.

Bring up CTFd and import the dataset:

```bash
docker compose -f deploy/ctfd/docker-compose.yml up -d
# open http://localhost:8000, do the one-time admin setup,
# then Settings -> Access Tokens -> generate an admin token
export CTFD_URL=http://localhost:8000
export CTFD_TOKEN=ctfd_xxxxxxxx

pip install -e '.[ctfd,openai]'
ctfbench ctfd import --ctfd-url "$CTFD_URL"     # push challenges + flags into CTFd
```

Run against the scoreboard (installs a per-model CTFd user automatically):

```bash
ctfbench run --scoreboard ctfd --ctfd-url "$CTFD_URL" --model openai:gpt-4o --out runs/
ctfbench ctfd scoreboard --ctfd-url "$CTFD_URL"
```

Each `--model` is registered as a CTFd user, so running several models fills the
CTFd scoreboard with a head-to-head ranking. `points` in `ctfbench`'s own JSON/MD
report mirror the CTFd challenge values.

## How it maps

| ctfbench | CTFd |
|----------|------|
| challenge (`challenge.yaml`) | a challenge (name, category, `points` → value) |
| ground-truth flag | a static flag on that challenge |
| a `--model` run | a user/competitor |
| `submit_flag` | `POST /api/v1/challenges/attempt` as that user |

## Notes

- Importing registers the ground-truth flag in CTFd (CTFd needs it to grade).
  Keep your CTFd instance private to the eval.
- `import` is idempotent (challenges are matched by name).
- Admin operations use a CTFd **access token** (CSRF-exempt); competitor
  submissions use a normal login session with CTFd's `CSRF-Token` header — both
  handled by `ctfbench/ctfd.py`.
