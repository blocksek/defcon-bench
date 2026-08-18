#!/usr/bin/env bash
# run_eval.sh — launch an opencode agent against the bench eval (default: math-is-hard).
#
#   ./run_eval.sh [RUN_ID] [CHALLENGE]
#
# Mounts $WINNER_DIR (default /Users/fork/winner) at /winner — ALL opencode traces,
# sessions, and logs land there (XDG_* redirected). Dual-homes the container:
# bootnet (internet for the LLM API) + the bench net (service/CTFd access).
# The challenge handout is mounted read-only at /handouts/<name>.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
RUN_ID=${1:-full1}
CHAL=${2:-math-is-hard}
NET="benchnet-$RUN_ID"
HOST_DIR=${WINNER_DIR:-/Users/fork/winner}
MODEL=${MODEL:-openrouter/anthropic/claude-sonnet-4.5}
NAME="eval-$RUN_ID-$CHAL"
IMAGE="bench/eval-agent:latest"

# ---- preflight ----
PROMPT_FILE="$ROOT/agent/eval/prompts/$CHAL.md"
[ -f "$PROMPT_FILE" ] || { echo "no prompt for challenge '$CHAL' (expected $PROMPT_FILE)"; exit 1; }
[ -f "$ROOT/results/$RUN_ID/agent_manifest.json" ] || { echo "no manifest for run '$RUN_ID'"; exit 1; }
[ -n "${OPENROUTER_API_KEY:-}${ANTHROPIC_API_KEY:-}" ] || {
  echo "set OPENROUTER_API_KEY (for openrouter/...) or ANTHROPIC_API_KEY (for anthropic/...)"; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
  echo "building eval agent image"; docker build --platform linux/arm64 -q -f agent/eval/Dockerfile.eval -t "$IMAGE" "$ROOT" >/dev/null; }
mkdir -p "$HOST_DIR" "$ROOT/agent/eval/workspace"

# ---- opencode config (inline; model + provider picked up from env keys) ----
read -r -d '' CFG <<JSON || true
{"\$schema":"https://opencode.ai/config.json","model":"$MODEL","share":"disabled","logLevel":"INFO"}
JSON

# ---- start eval container (bootnet = internet for LLM API) ----
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --network bootnet \
  -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  -e OPENCODE_CONFIG_CONTENT="$CFG" \
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

echo "[eval] run=$RUN_ID chal=$CHAL model=$MODEL traces->$HOST_DIR"
# ---- run the agent ----
docker exec -it "$NAME" opencode run "$(cat "$PROMPT_FILE")"
