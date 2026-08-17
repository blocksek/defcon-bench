import os, sys
sys.path.insert(0,"/app")
import sim as sim_mod
Simulation=sim_mod.Simulation
from full_solve import solve
from attack import Driver
for t in range(3):
    seed=os.urandom(32)
    init,mx=solve(seed)
    cand=init.to_bytes(16,'big')
    won=Driver(seed).gotcha(cand)
    print(f"seed={seed.hex()[:16]}..  init={cand.hex()}  gotcha={won}  maxticks={mx}")
