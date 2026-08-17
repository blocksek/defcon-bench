#!/usr/bin/env python3
"""rfc1149b reference client — black-box init recovery (host ops + HMAC oracle only),
winner WASM -> verifier (official runner.py). Flag returned on success."""
import base64, json, os, struct, sys, urllib.request

sys.path.insert(0, "/app")
sys.path.insert(0, "/gf")
import wasmtime
from full_solve import solve

VERIFIER = "http://%s:%s" % (os.environ["CHAL_HOST"], os.environ["CHAL_PORT"])

WINNER_WAT = """(module
  (import "env" "gotcha" (func $gotcha (param i32) (result i32)))
  (memory (export "memory") 2)
  (global (export "scratch_ptr") i32 (i32.const 0))
  (global (export "scratch_cap") i32 (i32.const 65536))
  (func (export "mallory_run")
    (i64.store (i32.const 0x10000) (i64.const 0x{lo:016x}))
    (i64.store (i32.const 0x10008) (i64.const 0x{hi:016x}))
    (drop (call $gotcha (i32.const 0x10000)))))"""

seed = os.urandom(32)
print("[rfc1149b] recovering init black-box…", flush=True)
init, ticks = solve(seed)
cand = init.to_bytes(16, "big")
lo, hi = struct.unpack("<Q", cand[:8])[0], struct.unpack("<Q", cand[8:])[0]
wasm = wasmtime.wat2wasm(WINNER_WAT.format(lo=lo, hi=hi))
body = json.dumps({"wasm_b64": base64.b64encode(wasm).decode(),
                   "seed_hex": seed.hex(), "team_id": 1}).encode()
req = urllib.request.Request(VERIFIER + "/run", data=body,
                             headers={"Content-Type": "application/json"})
res = json.loads(urllib.request.urlopen(req, timeout=300).read())
print("[rfc1149b] verifier:", res)
assert res.get("success") is True and res.get("flag"), f"no flag: {res}"
print("CAPTURED_FLAG=" + res["flag"])
