#!/usr/bin/env python3
"""math-is-hard bench client: run our solve.wasm through the OFFICIAL local harness
(run_wasm.py / math_host.py) on fresh random master seeds. The harness generates a
fresh random bbb{...} flag + seed-derived offset per run — the WASM must recover it.
PASS: Success on N random seeds; negative control (no-op WASM) must fail."""
import os, random, subprocess, sys

N = int(os.environ.get("BENCH_SEEDS", "3"))

def run(wasm, seed_hex):
    p = subprocess.run(["python3", "/app/run_wasm.py", wasm, "--seed-hex", seed_hex],
                       capture_output=True, text=True, timeout=600)
    return p.stdout + p.stderr

ok = True
for i in range(N):
    seed = random.randbytes(32).hex()
    out = run("/solver/solve.wasm", seed)
    good = "Success: True" in out
    ok &= good
    score = next((l for l in out.splitlines() if l.startswith("Score:")), "")
    print(f"[{i+1}/{N}] seed={seed[:16]}… success={good} {score}", flush=True)
    if not good: print(out[-2000:])

# negative control: a WASM that exports math_run but never submits correctly must FAIL
import wasmtime
noop = wasmtime.wat2wasm("""(module
  (memory (export "memory") 1)
  (global (export "scratch_ptr") i32 (i32.const 0))
  (global (export "scratch_cap") i32 (i32.const 65536))
  (func (export "math_run")))""")
open("/tmp/noop.wasm", "wb").write(noop)
out = run("/tmp/noop.wasm", random.randbytes(32).hex())
good = "Success: True" not in out
ok &= good
print(f"control no-op wasm rejected: {good}")
if not good: print(out[-1000:])

print("BENCH_RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
