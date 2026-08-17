#!/usr/bin/env bash
# rfc1149b eval — official KoTH harness (runner.py) vs our black-box solver.
set -euo pipefail
source "$(dirname "$0")/../../harness/lib.sh"
export EVAL_TAG=rfc1149b
C="$BENCH_ROOT/challenges/rfc1149b"
OUT="$BENCH_ROOT/results/rfc1149b.log"; mkdir -p "$BENCH_ROOT/results"

log "building OFFICIAL handout harness (linux/amd64)…"
docker build --platform "$PLATFORM" -q -t bench/rfc1149b-harness "$C/handout/rfc1149b" >/dev/null
log "building solver image…"
docker build --platform "$PLATFORM" -q -f "$C/solver.Dockerfile" -t bench/rfc1149b-solver "$BENCH_ROOT" >/dev/null

docker network rm -f bench-rfc1149b >/dev/null 2>&1 || true
docker network create bench-rfc1149b >/dev/null
log "starting official runner.py service…"
docker run -d --platform "$PLATFORM" --label bench=rfc1149b --network bench-rfc1149b \
  --network-alias rfc1149b -e RUNNER_AUTH_TOKEN=s3cret bench/rfc1149b-harness >/dev/null
sleep 3
docker run --rm --platform "$PLATFORM" --network bench-rfc1149b bench/rfc1149b-harness \
  python3 -c "import urllib.request,os,time
for i in range(60):
    try: print(urllib.request.urlopen('http://rfc1149b:8080/healthz',timeout=2).read()); break
    except Exception: time.sleep(1)
else: raise SystemExit('service never came up')"

log "running solver against service (this does 20 sim runs per seed; a few minutes under emulation)…"
set +e
docker run --rm --platform "$PLATFORM" --network bench-rfc1149b --label bench=rfc1149b \
  -e RUNNER_AUTH_TOKEN=s3cret -e BENCH_SEEDS="${BENCH_SEEDS:-2}" \
  bench/rfc1149b-solver python3 /solver/eval_client.py 2>&1 | tee "$OUT"
rc=${PIPESTATUS[0]}
set -e
docker network rm -f bench-rfc1149b >/dev/null 2>&1 || true

if [ "$rc" -eq 0 ] && grep -q "BENCH_RESULT PASS" "$OUT"; then pass "rfc1149b"; else fail "rfc1149b (see $OUT)"; exit 1; fi
