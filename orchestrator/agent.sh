#!/usr/bin/env bash
# agent.sh RUN_ID — start the agent container for a run (see agent/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
RUN_ID=${1:?usage: agent.sh RUN_ID}
NET="benchnet-$RUN_ID"
RUN_DIR="$ROOT/results/$RUN_ID"
# arm64-native agent with qemu-user + gdb-multiarch (see agent/Dockerfile.arm64): the
# agent can then debug the amd64 (qemu-emulated) pwn services via the qemu gdbstub
# pattern, which is impossible from an amd64-emulated agent (nested emulation breaks
# gdb). See agent/README.md.
PLATFORM="linux/arm64"
IMAGE="bench/agent:arm64"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[agent] building agent image (arm64)"
  docker build --platform "$PLATFORM" -q -f agent/Dockerfile.arm64 -t "$IMAGE" "$ROOT" >/dev/null
fi
mkdir -p "$ROOT/agent/workspace"
# Handout access (as-per-the-CTF: players had the handout files). Mount each
# challenge's handout read-only at /handouts/<name>. Handouts contain the
# challenge source/binaries only — never flags (flags live in results/, which is
# never mounted). This is NOT an anti-cheat leak: anti-cheat guards flags.
MOUNTS=()
for c in $(python3 -c "import json;print(' '.join(x['name'] for x in json.load(open('$RUN_DIR/agent_manifest.json'))['challenges']))"); do
  if [ -d "$ROOT/challenges/$c/handout" ]; then
    MOUNTS+=(-v "$ROOT/challenges/$c/handout:/handouts/$c:ro")
  fi
done
docker run -d --name "agent-$RUN_ID" --network "$NET" --platform "$PLATFORM" \
  -v "$RUN_DIR/agent_manifest.json:/etc/bench/manifest.json:ro" \
  -v "$ROOT/agent/workspace:/workspace" \
  "${MOUNTS[@]+"${MOUNTS[@]}"}" \
  --cap-drop ALL --security-opt no-new-privileges \
  --label bench="$RUN_ID" "$IMAGE" >/dev/null
echo "[agent] agent-$RUN_ID up. Exec in with:  docker exec -it agent-$RUN_ID bash"
echo "[agent] manifest:"; cat "$RUN_DIR/agent_manifest.json"
