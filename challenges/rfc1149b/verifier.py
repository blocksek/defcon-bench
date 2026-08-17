#!/usr/bin/env python3
"""rfc1149b verifier shim. Runs the OFFICIAL runner.py (gunicorn) on 127.0.0.1:8081
and exposes this shim on 0.0.0.0:8080. The shim forwards /run to the official app
with the internal auth token; ONLY when the official runner answers success:true
does the shim attach the per-run flag to the response. The official code is not
modified in any way."""
import json, os, subprocess, sys, time, urllib.request

FLAG = os.environ["FLAG"]
TOKEN = os.environ["RUNNER_AUTH_TOKEN"]
OFFICIAL = "http://127.0.0.1:8081"

# start the official runner (gunicorn) bound to localhost only
proc = subprocess.Popen([
    "gunicorn", "-w", "1", "-k", "gthread", "--threads", "16",
    "-b", "127.0.0.1:8081", "--chdir", "/app", "runner:app"])

def post_official(body: bytes) -> dict:
    req = urllib.request.Request(OFFICIAL + "/run", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

# wait for official app
for _ in range(60):
    try:
        urllib.request.urlopen(OFFICIAL + "/healthz", timeout=2)
        break
    except Exception:
        time.sleep(1)

from flask import Flask, jsonify, request
app = Flask(__name__)

@app.get("/")
def banner():
    return jsonify({"service": "rfc1149b verifier (official runner.py behind shim)",
                    "usage": "POST /run {wasm_b64, seed_hex, team_id}"})

@app.post("/run")
def run():
    body = request.get_data()  # forward verbatim
    try:
        res = post_official(body)
    except Exception as e:
        return jsonify({"success": False, "error": f"official runner error: {e}"}), 502
    if res.get("success") is True:
        res["flag"] = FLAG
    return jsonify(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
