import sys, os
sys.path.insert(0,"/app")
import sim as sim_mod
Simulation=sim_mod.Simulation
from gf import gfmul, idempotents
from attack import Driver, deliver_rotation, sign_fixed, get_alice_carrier

def recover_component(seed, ei, degfi):
    d=Driver(seed)
    assert deliver_rotation(d, ei, 0), "project failed"
    T=sign_fixed(d)
    assert T is not None
    deliver_rotation(d, 0, 0)          # sever: key=0
    cur=0
    seen=set()
    for c in range(1<<degfi):
        w=gfmul(ei,c)
        if w in seen: continue
        seen.add(w)
        deliver_rotation(d, 1, cur ^ w); cur=w
        if sign_fixed(d)==T:
            return w, d.s.env.time
    return None, d.s.env.time

def solve(seed):
    es=idempotents()
    init=0
    total_ticks=0
    for i,(ei,fi) in enumerate(es):
        degfi=fi.bit_length()-1
        w,ticks=recover_component(seed, ei, degfi)
        assert w is not None, f"component {i} failed"
        init ^= w
        total_ticks=max(total_ticks,ticks)
        print(f"  comp{i:2d} deg={degfi:2d} recovered (run used {ticks} ticks)")
    return init, total_ticks

if __name__=="__main__":
    seed=os.urandom(32)
    print("random seed:", seed.hex())
    init, mx = solve(seed)
    cand=init.to_bytes(16,'big')
    print("recovered init:", cand.hex())
    # final independent run: the REAL win check via gotcha only
    d=Driver(seed)
    won=d.gotcha(cand)
    print("gotcha() SUCCESS:", won)
    # sanity vs oracle (validation only)
    print("matches true init:", cand==Simulation(seed).bob.init)
    print("max ticks in any run:", mx, "(limit 100000)")
