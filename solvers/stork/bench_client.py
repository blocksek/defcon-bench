#!/usr/bin/env python3
"""stork reference client — SERVICE HEALTH check (full exploit is still open work,
see solutions/stork/FINDINGS.md). Verifies the service speaks the real protocol:
banner -> base64 bytecode -> runs the VM. Prints SERVICE_OK on success."""
import base64, os, socket, sys

host, port = os.environ["CHAL_HOST"], int(os.environ["CHAL_PORT"])
prog = open("/solvers/stork/print.bin", "rb").read()

s = socket.create_connection((host, port), timeout=30)
f = s.makefile("rwb", buffering=0)
banner = f.readline().decode("utf-8", "replace")
assert "base64" in banner.lower(), f"unexpected banner: {banner!r}"
f.write(base64.b64encode(prog) + b"\n\n")
out = b""
s.settimeout(30)
try:
    while True:
        chunk = s.recv(4096)
        if not chunk: break
        out += chunk
except socket.timeout:
    pass
text = out.decode("utf-8", "replace")
print("service replied:", text[:200])
assert "hello from stork VM" in text, "VM did not run our bytecode"
print("SERVICE_OK")
