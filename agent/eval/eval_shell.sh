#!/usr/bin/env bash
# eval_shell.sh — per-challenge INTERACTIVE opencode TUI launcher.
#
#   ./eval_shell.sh [RUN_ID] [CHALLENGE]
#
# Same wiring as run_eval.sh (dual-home bench-net + bootnet internet, handout +
# manifest + prompt mounted read-only, XDG traces to $WINNER_DIR), but instead of a
# headless `opencode run`, it drops you into a bash shell in the container so you can
# configure the provider key yourself and drive the interactive TUI (`opencode`).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
RUN_ID=${1:-full1}
CHAL=${2:-math-is-hard}
NET="benchnet-$RUN_ID"
HOST_DIR=${WINNER_DIR:-/Users/fork/winner}
NAME="eval-shell-$RUN_ID-$CHAL"
IMAGE="bench/eval-agent:latest"
PROMPT_FILE="$ROOT/agent/eval/prompts/$CHAL.md"

# ---- preflight ----
[ -f "$PROMPT_FILE" ] || { echo "no prompt for challenge '$CHAL' (expected $PROMPT_FILE)"; exit 1; }
[ -f "$ROOT/results/$RUN_ID/agent_manifest.json" ] || { echo "no manifest for run '$RUN_ID'"; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
  echo "building eval agent image"; docker build --platform linux/arm64 -q -f agent/eval/Dockerfile.eval -t "$IMAGE" "$ROOT" >/dev/null; }
mkdir -p "$HOST_DIR" "$ROOT/agent/eval/workspace"

# ---- start container (bootnet = internet for LLM API) ----
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --network bootnet \
  -e TERM=xterm-256color -e COLORTERM=truecolor \
  -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  -e XDG_DATA_HOME=/winner/data -e XDG_CONFIG_HOME=/winner/config -e XDG_CACHE_HOME=/winner/cache \
  -v "$HOST_DIR:/winner" \
  -v "$ROOT/challenges/$CHAL/handout:/handouts/$CHAL:ro" \
  -v "$ROOT/results/$RUN_ID/agent_manifest.json:/etc/bench/manifest.json:ro" \
  -v "$PROMPT_FILE:/eval/PROMPT.md:ro" \
  -v "$ROOT/agent/eval/workspace:/workspace" \
  "$IMAGE" sleep infinity >/dev/null
# ---- attach to the bench net (service + CTFd access) ----
docker network connect "$NET" "$NAME"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

cat <<EOF
[eval-shell] run=$RUN_ID chal=$CHAL traces->$HOST_DIR
  handout:  /handouts/$CHAL/
  manifest: /etc/bench/manifest.json   (CTFd URL + your agent_token)
  prompt:   /eval/PROMPT.md
Inside:
  export OPENROUTER_API_KEY=...        # or ANTHROPIC_API_KEY
  opencode                             # interactive TUI — paste the prompt there
EOF

docker exec -it "$NAME" bash
