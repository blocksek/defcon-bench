#!/usr/bin/env python3
"""rfc1149b bench client: recover Bob's init BLACK-BOX (host ops + HMAC oracle only),
build a winner WASM, and submit it to the OFFICIAL runner.py service — like the real KoTH.
PASS: success=true on fresh random seeds, and the all-zero-init control is rejected."""
import base64, json, os, struct, sys, urllib.request

sys.path.insert(0, "/app")
sys.path.insert(0, "/gf")
import wasmtime
from full_solve import solve

RUNNER = os.environ.get("RUNNER_URL", "http://rfc1149b:8080")
TOKEN = os.environ.get("RUNNER_AUTH_TOKEN", "s3cret")
SEEDS = int(os.environ.get("BENCH_SEEDS", "2"))

WINNER_WAT = """(module
  (import "env" "gotcha" (func $gotcha (param i32) (result i32)))
  (memory (export "memory") 2)
  (global (export "scratch_ptr") i32 (i32.const 0))
  (global (export "scratch_cap") i32 (i32.const 65536))
  (func (export "mallory_run")
    (i64.store (i32.const 0x10000) (i64.const 0x{lo:016x}))
    (i64.store (i32.const 0x10008) (i64.const 0x{hi:016x}))
    (drop (call $gotcha (i32.const 0x10000)))))"""

def winner_wasm(init: bytes) -> bytes:
    lo, hi = struct.unpack("<Q", init[:8])[0], struct.unpack("<Q", init[8:])[0]
    return wasmtime.wat2wasm(WINNER_WAT.format(lo=lo, hi=hi))

def post_run(wasm: bytes, seed: bytes) -> dict:
    body = json.dumps({"wasm_b64": base64.b64encode(wasm).decode(),
                       "seed_hex": seed.hex(), "team_id": 1}).encode()
    req = urllib.request.Request(RUNNER + "/run", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

ok = True
for i in range(SEEDS):
    seed = os.urandom(32)
    print(f"[{i+1}/{SEEDS}] seed={seed.hex()[:16]}… recovering init black-box…", flush=True)
    init, ticks = solve(seed)
    cand = init.to_bytes(16, "big")
    res = post_run(winner_wasm(cand), seed)
    good = res.get("success") is True
    ok &= good
    print(f"    init={cand.hex()}  official-runner success={res.get('success')}  (ticks<={ticks})")
    if res.get("error"): print("    error:", res["error"])

# negative control: all-zero init must be REJECTED by the official runner
ctl = post_run(winner_wasm(bytes(16)), os.urandom(32))
print(f"control zero-init: success={ctl.get('success')} (must be False)")
ok &= (ctl.get("success") is False)

print("BENCH_RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
