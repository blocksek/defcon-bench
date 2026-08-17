#!/usr/bin/env bash
# harness/lib.sh — shared eval helpers (sourced by challenges/*/eval.sh)
set -uo pipefail
BENCH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="linux/amd64"   # all challenge binaries are x86-64; Docker Desktop emulates

rand_flag() {  # random planted flag, unknown to the solver
  echo "bbb{bench_$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 16)}"
}

log()  { printf '\033[1;34m[bench]\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m[PASS]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*"; }

wait_port() { # wait_port HOST PORT SECONDS
  local h=$1 p=$2 t=${3:-60} i
  for ((i=0;i<t*2;i++)); do
    if nc -z -G 2 "$h" "$p" 2>/dev/null; then return 0; fi
    sleep 0.5
  done
  return 1
}

cleanup() { # kill containers tagged with this eval's label
  local tag=${EVAL_TAG:-}
  [ -n "$tag" ] && docker ps -aq --filter "label=bench=$tag" | xargs -r docker rm -f >/dev/null 2>&1 || true
}
trap cleanup EXIT
