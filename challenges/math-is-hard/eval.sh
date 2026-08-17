#!/usr/bin/env bash
# math-is-hard eval — official local harness (run_wasm.py) vs our solve.wasm.
set -euo pipefail
source "$(dirname "$0")/../../harness/lib.sh"
export EVAL_TAG=math-is-hard
OUT="$BENCH_ROOT/results/math-is-hard.log"; mkdir -p "$BENCH_ROOT/results"

log "building math-is-hard image (qemu-riscv64 + wasmtime, linux/amd64)…"
docker build --platform "$PLATFORM" -q -f "$BENCH_ROOT/challenges/math-is-hard/Dockerfile" \
  -t bench/math-is-hard "$BENCH_ROOT" >/dev/null

log "running solve.wasm on ${BENCH_SEEDS:-3} fresh random seeds (RISC-V under qemu; slow)…"
set +e
docker run --rm --platform "$PLATFORM" --label bench=math-is-hard \
  -e BENCH_SEEDS="${BENCH_SEEDS:-3}" \
  bench/math-is-hard python3 /solver/eval_client.py 2>&1 | tee "$OUT"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -eq 0 ] && grep -q "BENCH_RESULT PASS" "$OUT"; then pass "math-is-hard"; else fail "math-is-hard (see $OUT)"; exit 1; fi
