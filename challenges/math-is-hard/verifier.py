#!/usr/bin/env python3
"""math-is-hard verifier shim. Exposes POST /run {wasm_b64}; runs the OFFICIAL local
harness (run_wasm.py / math_host.py) on a fresh random master seed (the harness itself
generates a fresh random flag per run). Only on Success:True does the shim return the
per-run bench flag. CHALL_TIMEOUT=900 is set in the image (double-emulation
accommodation, disclosed in README); every other official limit is untouched."""
import json, os, secrets, subprocess
from flask import Flask, jsonify

FLAG = os.environ["FLAG"]
app = Flask(__name__)

@app.get("/")
def banner():
    return jsonify({"service": "math-is-hard verifier (official run_wasm.py harness)",
                    "usage": "POST /run {wasm_b64}"})

@app.post("/run")
def run():
    from flask import request
    body = request.get_json(silent=True) or {}
    wasm_b64 = body.get("wasm_b64", "")
    import base64
    try:
        wasm = base64.b64decode(wasm_b64, validate=True)
        assert wasm.startswith(b"\x00asm")
    except Exception:
        return jsonify({"success": False, "error": "invalid wasm_b64"}), 400
    with open("/tmp/sub.wasm", "wb") as f:
        f.write(wasm)
    seed = secrets.token_hex(32)
    try:
        p = subprocess.run(["python3", "/app/run_wasm.py", "/tmp/sub.wasm", "--seed-hex", seed],
                           capture_output=True, text=True, timeout=4200)
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "harness timeout"})
    out = p.stdout + p.stderr
    ok = "Success: True" in out
    res = {"success": ok, "seed_hex": seed, "harness_output": out[-2000:]}
    if ok:
        res["flag"] = FLAG
    return jsonify(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
