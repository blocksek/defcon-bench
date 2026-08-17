#!/usr/bin/env python3
"""math-is-hard reference client — submit solve.wasm to the verifier (official
harness on a fresh random seed+flag); flag returned on success."""
import base64, json, os, urllib.request

VERIFIER = "http://%s:%s" % (os.environ["CHAL_HOST"], os.environ["CHAL_PORT"])
wasm = open("/solvers/math-is-hard/solve.wasm", "rb").read()
print("[mih] submitting solve.wasm to verifier (one run ≈ 25-35 min under emulation)…", flush=True)
body = json.dumps({"wasm_b64": base64.b64encode(wasm).decode()}).encode()
req = urllib.request.Request(VERIFIER + "/run", data=body,
                             headers={"Content-Type": "application/json"})
res = json.loads(urllib.request.urlopen(req, timeout=4300).read())
print("[mih] verifier success:", res.get("success"))
if not res.get("success"):
    print(res.get("harness_output", "")[-1500:])
assert res.get("success") and res.get("flag"), "no flag"
print("CAPTURED_FLAG=" + res["flag"])
