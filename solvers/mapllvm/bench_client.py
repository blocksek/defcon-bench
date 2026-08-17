#!/usr/bin/env python3
"""mapllvm reference client — SERVICE HEALTH check (full exploit is open work,
see solutions/mapllvm/FINDINGS.md). Verifies the hosted compiler pipeline works:
send a small program, expect it to compile+run and report an exit code."""
import os, socket

host, port = os.environ["CHAL_HOST"], int(os.environ["CHAL_PORT"])
s = socket.create_connection((host, port), timeout=60)
f = s.makefile("rwb", buffering=0)
banner = f.readline().decode("utf-8", "replace") + f.readline().decode("utf-8", "replace")
assert "compiler" in banner.lower(), f"unexpected banner: {banner!r}"
# NB: the '>>> ' prompt is printed by input() with no trailing newline — send directly.
prog = b"(+ 40 2)\n"
f.write(prog)
out = b""
s.settimeout(60)
try:
    while True:
        chunk = s.recv(4096)
        if not chunk: break
        out += chunk
except socket.timeout:
    pass
text = out.decode("utf-8", "replace")
print("service replied:", text[:300])
assert "Exit code:" in text, "no exit code reported — pipeline broken"
print("SERVICE_OK")
