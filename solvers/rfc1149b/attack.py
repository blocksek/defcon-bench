import sys, os
sys.path.insert(0, "/gf")
import sim as sim_mod
Simulation=sim_mod.Simulation
from gf import gfmul, idempotents, M

ALICE,BOB,CAROL=0,1,2
FIXED_MSG = bytes(27)   # 27-byte constant SIGN payload (no b"BBB")

class Driver:
    """Wraps Simulation exposing ONLY the 5 host operations. Never reads secrets."""
    def __init__(self, seed):
        self.s=Simulation(seed)
        self.held=None
    # ---- host ops (mirror WasmMalloryHost) ----
    def advance(self):
        r=self.s.advance(); return r['state']
    def state(self):   # read-only convenience == what 'advance'/responses expose
        return self.s.state()
    def intercept(self, mid):
        r=self.s.intercept(mid)
        if 'error_code' in r: return None
        self.held=r
        return r
    def edit(self, content, sender, recipient):
        r=self.s.edit(content, sender, recipient)
        return None if 'error_code' in r else r
    def release(self):
        r=self.s.release(); self.held=None
        return None if 'error_code' in r else r
    def gotcha(self, cand):
        try:
            self.s.gotcha(cand); return True
        except Exception:
            return False

def find_msg(st, sender=None, recipient=None, interceptable_only=True):
    for m in st['in_flight']:
        if sender is not None and m['sender']!=sender: continue
        if recipient is not None and m['recipient']!=recipient: continue
        if interceptable_only and not m['interceptable']: continue
        return m
    return None

def get_alice_carrier(d, budget=400):
    """Advance until an Alice->Bob 32B rotation is interceptable; return its id."""
    for _ in range(budget):
        st=d.state()
        m=find_msg(st, ALICE, BOB, True)
        if m: return m['id']
        # neutralize Bob->Alice ACK to keep Alice pumping every 16 ticks
        ack=find_msg(st, BOB, ALICE, True)
        if ack:
            d.intercept(ack['id']); d.edit(b'XXX', BOB, ALICE); d.release(); continue
        d.advance()
    return None

def deliver_rotation(d, mult, offset):
    """Hijack next Alice->Bob carrier -> deliver a rotation mult||offset to Bob."""
    mid=get_alice_carrier(d)
    if mid is None: return False
    d.intercept(mid)
    content=mult.to_bytes(16,'big')+offset.to_bytes(16,'big')
    d.edit(content, ALICE, BOB)
    d.release()
    return True

def sign_fixed(d):
    """Hijack next Alice->Bob carrier -> make it Carol->Bob 'SIGN '+FIXED_MSG (32B),
       then capture Bob's SIGNED tag from the Bob->Carol reply."""
    mid=get_alice_carrier(d)
    if mid is None: return None
    d.intercept(mid)
    content=b"SIGN "+FIXED_MSG      # 5+27 = 32 bytes
    assert len(content)==32
    d.edit(content, CAROL, BOB)
    d.release()
    # wait for Bob->Carol SIGNED reply, intercept, read tag (after last '.')
    for _ in range(60):
        st=d.state()
        m=find_msg(st, BOB, CAROL, True)
        if m:
            r=d.intercept(m['id'])
            c=r['content']
            d.release()   # let it go (irrelevant)
            if c.startswith(b"SIGNED "):
                tok=c[len(b"SIGNED "):]
                return tok.rsplit(b".",1)[1]   # base64 signature part
            return None
        d.advance()
    return None

def recover_component(seed, ei, debug_x=None):
    """Recover w_i = e_i ⊗ init using only host ops on a fresh sim (same seed)."""
    d=Driver(seed)
    # 1) project: first rotation sets keys[1] = e_i ⊗ init
    assert deliver_rotation(d, ei, 0)
    # 2) target signature under keys[1]
    T=sign_fixed(d)
    assert T is not None, "no target sig"
    # 3) brute candidates w = e_i ⊗ c ; set key=w and sign, compare
    deg=(0)
    # enumerate residues c mod f_i: c in [0, 2^deg_fi)
    # image elements w=gfmul(ei,c) ; dedupe
    return d, T

if __name__=="__main__":
    import random
    seed=os.urandom(32)
    truex=int.from_bytes(Simulation(seed).bob.init,'big')  # oracle for validation ONLY
    es=idempotents()
    # quick protocol test on component 0 (deg4): capture T, then brute 16 candidates
    ei,fi=es[0]; degfi=fi.bit_length()-1
    d,T=recover_component(seed, ei)
    print("target tag:", T)
    # brute
    found=None
    prev=0; first=True
    # set key to 0 once (sever), then iterate offsets
    deliver_rotation(d, 0, 0)   # key=0
    cur=0
    for c in range(1<<degfi):
        w=gfmul(ei,c)
        # set key to w: mult=1, offset = cur ^ w  (key = 1*(cur ^ (cur^w)) = w)
        deliver_rotation(d, 1, cur ^ w); cur=w
        S=sign_fixed(d)
        if S==T:
            found=w; break
    print("recovered w0:", hex(found) if found is not None else None)
    print("true    w0:", hex(gfmul(ei, truex)))
    print("MATCH:", found==gfmul(ei,truex))
