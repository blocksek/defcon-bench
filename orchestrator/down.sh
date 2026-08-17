#!/usr/bin/env bash
# down.sh RUN_ID — tear down a bench run (containers + network). Run dir kept.
set -uo pipefail
RUN_ID=${1:?usage: down.sh RUN_ID}
docker ps -aq --filter "label=bench=$RUN_ID" | xargs -r docker rm -f >/dev/null 2>&1
docker network rm -f "benchnet-$RUN_ID" >/dev/null 2>&1 || true
echo "[down] run $RUN_ID torn down"
