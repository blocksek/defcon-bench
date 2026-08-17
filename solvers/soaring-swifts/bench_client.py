#!/usr/bin/env python3
"""soaring-swifts reference client — full solve over TCP against the real service.
3 rounds: base64 checker ELF -> Z3 symbolic recovery -> submit secret -> flag."""
import base64, os, socket, sys
sys.path.insert(0, "/solvers/soaring-swifts")
import solver

host, port = os.environ["CHAL_HOST"], int(os.environ["CHAL_PORT"])
s = socket.create_connection((host, port), timeout=120)
f = s.makefile("rwb", buffering=0)

def read_challenge():
    seen_bar = 0
    b64 = None
    while True:
        line = f.readline()
        if not line: return None
        line_s = line.rstrip(b"\n").decode("ascii", "replace")
        if line_s.startswith("Challenge"):
            print("  [server]", line_s, flush=True)
        elif line_s and set(line_s) == {"="}:
            seen_bar += 1
        elif seen_bar == 1 and len(line_s) > 40:
            b64 = line_s
        if seen_bar == 2:
            return b64

for rnd in range(3):
    b64 = read_challenge()
    if b64 is None:
        print("  [!] server ended early"); sys.exit(1)
    data = base64.b64decode(b64)
    print(f"  [client] round {rnd+1}: {len(data)}-byte checker, solving…", flush=True)
    secret = solver.solve(data, verbose=False)
    print(f"  [client] recovered: {secret}", flush=True)
    f.write(secret.encode() + b"\n")

rest = b""
s.settimeout(30)
try:
    while True:
        chunk = s.recv(4096)
        if not chunk: break
        rest += chunk
except socket.timeout:
    pass
text = rest.decode("utf-8", "replace")
print("  [server tail]:", text[-400:])
import re
m = re.search(r"bbb\{[^}]+\}", text)
assert m, "no flag in server output"
print("CAPTURED_FLAG=" + m.group(0))
