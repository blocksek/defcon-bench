#!/usr/bin/env bash
# build_all.sh — build all service + verifier images ONCE (tag :latest).
# up.sh reuses these tags; rebuild only when a Dockerfile/handout changes.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PLATFORM="linux/amd64"
CHALS="${1:-stork mapllvm soaring-swifts black-talon rfc1149b math-is-hard 2bird2can}"
for c in $CHALS; do
  echo "[build] $c"
  docker build --platform "$PLATFORM" -f "challenges/$c/service.Dockerfile" -t "bench/$c:latest" "$ROOT"
done
# 2bird2can also has a client image
if [[ " $CHALS " == *" 2bird2can "* ]]; then
  echo "[build] 2bird2can-client"
  docker build --platform "$PLATFORM" -f challenges/2bird2can/client.Dockerfile -t bench/2bird2can-client:latest "$ROOT"
fi
echo "[build] done"
