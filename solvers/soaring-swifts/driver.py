#!/usr/bin/env python3
"""End-to-end client: drives chal.py, solves each round with solver.py."""
import subprocess, sys, base64, os
sys.path.insert(0, "/chal")
import solver

env = dict(os.environ)
env["FLAG"] = "bbb{s0aring_sw1fts_branchless_re_demo}"
env["NUM_CHALLENGES"] = "3"

p = subprocess.Popen(["python3", "/chal/chal.py"], cwd="/build",
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)

def read_challenge():
    """Read lines until we've captured the base64 block; return b64 string."""
    seen_bar = 0
    b64 = None
    while True:
        line = p.stdout.readline()
        if line == "":
            return None
        line_s = line.rstrip("\n")
        if line_s.startswith("Challenge"):
            print("  [server]", line_s)
        elif set(line_s) == {"="} and line_s:
            seen_bar += 1
        elif seen_bar == 1 and len(line_s) > 40:
            b64 = line_s
        if seen_bar == 2:
            return b64

for rnd in range(3):
    b64 = read_challenge()
    if b64 is None:
        print("  [!] no challenge / server ended"); break
    data = base64.b64decode(b64)
    print(f"  [client] round {rnd+1}: got {len(data)}-byte checker ELF, solving...")
    secret = solver.solve(data, verbose=False)
    print(f"  [client] recovered secret: {secret}")
    # consume the "Enter your guess: " prompt (no newline) then send
    p.stdin.write(secret + "\n"); p.stdin.flush()

# read remaining output (Correct!/flag)
rest = p.stdout.read()
print("  [server tail]:")
for l in rest.splitlines():
    print("   ", l)
p.wait()
