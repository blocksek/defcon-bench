#!/usr/bin/env python3
"""scoreboard.py RUN_DIR — pull the CTFd scoreboard + per-challenge solve status
for the run's agent, using the orchestrator's admin token. Ground truth for evals."""
import json, sys, urllib.request

run_dir = sys.argv[1]
ctfd = json.load(open(f"{run_dir}/ctfd.json"))
port = open(f"{run_dir}/ctfd_port").read().strip()
BASE = f"http://127.0.0.1:{port}"
ADMIN = ctfd["admin_token"]

def api(path):
    r = urllib.request.Request(BASE + path, headers={
        "Authorization": "Token " + ADMIN, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read())

sb = api("/api/v1/scoreboard")["data"]
agent_id = ctfd["agent_id"]
solves = api(f"/api/v1/users/{agent_id}/solves")["data"]
solved = {s["challenge_id"] for s in solves}
ids = ctfd["challenge_ids"]
print("scoreboard:", json.dumps(sb))
print(f"agent (id={agent_id}) solved {len(solved)}/{len(ids)}:")
for name, cid in ids.items():
    print(f"  {'✓' if cid in solved else '✗'} {name}")
