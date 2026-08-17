#!/bin/bash
# Per-connection game launcher + reaper. The orchestrator spawns ./network and
# ./client children; if it ever exits without reaping them (e.g. the guest hung
# on a race), they'd live on as zombie games under qemu-user and poison later
# connections with CPU contention. Kill leftovers after each session ends.
cd /challenge
/challenge/orchestrator "$@"
rc=$?
pkill -f '/challenge/network' 2>/dev/null
pkill -f '/challenge/client' 2>/dev/null
exit "$rc"
