#!/usr/bin/env bash
# up.sh — bring up a full bench run: fresh flags, isolated network, CTFd,
# challenge services, and (optionally) the agent container.
#
#   ./up.sh [--run-id ID] [--mode reference|agent|infra] [--challenges "a b c"]
#
# modes:  infra     = CTFd + services only (default)
#         reference = additionally run solvers/<chal> and assert flag capture
#         agent     = additionally start the agent container (no solvers anywhere)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
MODE="infra"
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run-id) RUN_ID=$2; shift 2;;
    --mode) MODE=$2; shift 2;;
    --challenges) ONLY=$2; shift 2;;
    *) echo "unknown arg $1"; exit 1;;
  esac
done

RUN_DIR="$ROOT/results/$RUN_ID"
mkdir -p "$RUN_DIR/flags"; chmod 700 "$RUN_DIR"
NET="benchnet-$RUN_ID"
PLATFORM="linux/amd64"
export RUN_ID NET PLATFORM RUN_DIR ROOT

echo "[up] run=$RUN_ID mode=$MODE net=$NET"

# ---- 1. flags (orchestrator-only) ----
python3 - "$RUN_DIR" <<'PY'
import json, os, secrets, sys
run_dir = sys.argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(run_dir), "..", "orchestrator"))
from catalog import CATALOG
flags = {c["name"]: f"bbb{{{c['name']}_{secrets.token_hex(16)}}}" for c in CATALOG}
with open(os.path.join(run_dir, "flags.json"), "w") as f:
    json.dump(flags, f, indent=1)
os.chmod(os.path.join(run_dir, "flags.json"), 0o600)
for name, flag in flags.items():
    p = os.path.join(run_dir, "flags", name)
    with open(p, "w") as f: f.write(flag)
    os.chmod(p, 0o600)
print("[up] generated", len(flags), "flags")
PY

# ---- 2. network (internal = no internet for anything attached) ----
docker network rm -f "$NET" >/dev/null 2>&1 || true
docker network create --internal "$NET" >/dev/null

# ---- 3. CTFd ----
# CTFd hangs indefinitely when booted on an --internal network (empirically
# confirmed, CTFd 3.8.6). Topology: ctfd boots dual-homed on a normal bridge
# (bootnet, reused across runs) for boot + orchestrator host access, and is
# additionally attached to the internal bench net (agent access). Nothing the
# agent controls is on bootnet; the agent container itself is benchnet-only.
CTFD_PORT=$(( 18000 + RANDOM % 500 ))
docker network create bootnet >/dev/null 2>&1 || true
docker run -d --name "ctfd-$RUN_ID" --network bootnet \
  -p 127.0.0.1:$CTFD_PORT:8000 -e SECRET_KEY="$(openssl rand -hex 32)" \
  --label bench="$RUN_ID" ctfd/ctfd:latest >/dev/null
echo "$CTFD_PORT" > "$RUN_DIR/ctfd_port"
echo "[up] ctfd on 127.0.0.1:$CTFD_PORT (waiting)"
for i in $(seq 1 240); do curl -sk -m 2 "http://127.0.0.1:$CTFD_PORT/" >/dev/null 2>&1 && break; sleep 1; done
docker network connect "$NET" "ctfd-$RUN_ID" --alias ctfd

# ---- 4. challenge services ----
CHALS=$(python3 -c "import sys; sys.path.insert(0,'orchestrator'); from catalog import CATALOG; print(' '.join(c['name'] for c in CATALOG))")
[ -n "$ONLY" ] && CHALS="$ONLY"
for c in $CHALS; do
  if ! docker image inspect "bench/$c:latest" >/dev/null 2>&1; then
    echo "[up] building $c (first time)"
    docker build --platform "$PLATFORM" -q -f "challenges/$c/service.Dockerfile" -t "bench/$c:latest" "$ROOT" >/dev/null
  fi
  echo "[up] starting $c"
  case "$c" in
    stork|mapllvm)
      # kctf jail template ships the image; services launch via chroot+socat
      # (nsjail unsupported under qemu-user — see service.Dockerfile comments).
      # Flag bind-mounted into the chroot at /flag.
      # mapllvm gets MAPLLVM_RUN_TIMEOUT (disclosed timed-emulation accommodation).
      EXTRA_ENV=(); [ "$c" = "mapllvm" ] && EXTRA_ENV=(-e MAPLLVM_RUN_TIMEOUT="${MAPLLVM_RUN_TIMEOUT:-120}")
      docker run -d --name "$c-$RUN_ID" --network "$NET" --network-alias "$c" \
        --platform "$PLATFORM" \
        ${EXTRA_ENV[@]+"${EXTRA_ENV[@]}"} -v "$RUN_DIR/flags/$c:/chroot/flag:ro" --label bench="$RUN_ID" "bench/$c:latest" >/dev/null;;
    soaring-swifts)
      docker run -d --name "$c-$RUN_ID" --network "$NET" --network-alias "$c" \
        --platform "$PLATFORM" \
        -e FLAG="$(cat "$RUN_DIR/flags/$c")" --label bench="$RUN_ID" "bench/$c:latest" >/dev/null;;
    2bird2can)
      # Publish game+map on 127.0.0.1 loopback for the orchestrator-side host
      # browser reference solver (agents still reach it only via the bench net).
      B2C_SRV=$((17500 + RANDOM % 400)); B2C_MAP=$((17900 + RANDOM % 90))
      echo "$B2C_SRV $B2C_MAP" > "$RUN_DIR/2bird2can_ports"
      docker run -d --name "$c-$RUN_ID" --network "$NET" --network-alias "$c" \
        --platform "$PLATFORM" \
        -p 127.0.0.1:$B2C_SRV:7777 -p 127.0.0.1:$B2C_MAP:7778 \
        -e FLAG="$(cat "$RUN_DIR/flags/$c")" --label bench="$RUN_ID" "bench/$c:latest" >/dev/null
      docker run -d --name "$c-client-$RUN_ID" --network "$NET" --network-alias "$c-client" \
        -e MAP_HOST="http://$c:7778" -e DEFAULT_SERVER_URL="ws://$c:7777/" \
        --label bench="$RUN_ID" bench/2bird2can-client:latest >/dev/null;;
    black-talon)
      docker run -d --name "$c-$RUN_ID" --network "$NET" --network-alias "$c" \
        --platform "$PLATFORM" \
        --platform "$PLATFORM" -v "$RUN_DIR/flags/$c:/chroot/challenge/flag:ro" --label bench="$RUN_ID" "bench/$c:latest" >/dev/null;;
    rfc1149b|math-is-hard)
      TOKEN=$(openssl rand -hex 16)
      echo "$TOKEN" > "$RUN_DIR/verifier_token_$c"; chmod 600 "$RUN_DIR/verifier_token_$c"
      docker run -d --name "$c-$RUN_ID" --network "$NET" --network-alias "$c" \
        --platform "$PLATFORM" \
        -e FLAG="$(cat "$RUN_DIR/flags/$c")" -e RUNNER_AUTH_TOKEN="$TOKEN" \
        --label bench="$RUN_ID" "bench/$c:latest" >/dev/null;;
  esac
done

# ---- 5. register in CTFd ----
python3 - "$RUN_DIR" "$CTFD_PORT" "$CHALS" <<'PY'
import json, subprocess, sys, secrets
run_dir, port, chals = sys.argv[1], sys.argv[2], sys.argv[3].split()
sys.path.insert(0, "orchestrator")
from catalog import CATALOG
flags = json.load(open(f"{run_dir}/flags.json"))
cfg = {"ctfd_url": f"http://127.0.0.1:{port}",
       "admin_name": "benchadmin", "admin_password": secrets.token_hex(16),
       "agent_name": "agent1", "agent_password": secrets.token_hex(16),
       "challenges": []}
for c in CATALOG:
    if c["name"] not in chals: continue
    cfg["challenges"].append({
        "name": c["name"], "category": c["category"], "value": c["value"],
        "description": c["description"].format(host=c["name"], port=c["port"]),
        "flag": flags[c["name"]]})
p = subprocess.run(["python3", "orchestrator/ctfd_setup.py"], input=json.dumps(cfg).encode(),
                   capture_output=True)
if p.returncode != 0:
    print(p.stderr.decode()); sys.exit(1)
out = json.loads(p.stdout)
out["admin_password"] = cfg["admin_password"]; out["agent_password"] = cfg["agent_password"]
with open(f"{run_dir}/ctfd.json", "w") as f: json.dump(out, f, indent=1)
import os; os.chmod(f"{run_dir}/ctfd.json", 0o600)
print("[up] ctfd registered:", list(out["challenge_ids"].keys()))
PY

# ---- 6. agent manifest (the ONLY thing the agent is given) ----
python3 - "$RUN_DIR" "$CHALS" <<'PY'
import json, sys
run_dir, chals = sys.argv[1], sys.argv[2].split()
sys.path.insert(0, "orchestrator")
from catalog import CATALOG
ctfd = json.load(open(f"{run_dir}/ctfd.json"))
manifest = {"ctfd_url": "http://ctfd:8000", "agent_token": ctfd["agent_token"],
            "challenges": []}
for c in CATALOG:
    if c["name"] not in chals: continue
    manifest["challenges"].append({"name": c["name"], "host": c["name"], "port": c["port"],
        "category": c["category"], "value": c["value"],
        "description": c["description"].format(host=c["name"], port=c["port"])})
with open(f"{run_dir}/agent_manifest.json", "w") as f: json.dump(manifest, f, indent=1)
print("[up] agent manifest written")
PY

echo "[up] DONE. run dir: $RUN_DIR"
echo "[up]   CTFd (orchestrator view): http://127.0.0.1:$CTFD_PORT"
echo "[up]   next: MODE=$MODE -> ./orchestrator/reference.sh $RUN_ID  OR  ./orchestrator/agent.sh $RUN_ID"
