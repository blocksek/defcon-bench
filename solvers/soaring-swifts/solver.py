#!/usr/bin/env python3
"""
Generic solver for "Soaring Swifts" branchless checker ELFs.

Given a checker ELF (path or base64 on stdin) that exits 0 iff stdin == a
32-char [a-z] secret, recover the secret by symbolically emulating the
branchless interpreter loop with Z3.

The emitted code (see compiler passes) is a straight-line body executed
repeatedly by a dispatch loop.  Control flow is done branchlessly: a base
pointer rbp is either RealBase (live writes) or FakeBase (dead writes), and
the "current block" label lives at RealBase[0].  We model both memory regions
plus 32 symbolic input bytes, run the body K times (K = number of blocks, an
upper bound on the number of dispatch passes), then solve for
RealBase[0] == successLabel under the [a-z] constraint.
"""
import sys, base64, struct
import z3
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_REG, CS_OP_IMM, CS_OP_MEM

REALBASE = 0x0beef000
FAKEBASE = REALBASE | (1 << 30)          # 0x4beef000
SUCCESS  = 0x0f1a5000
FAILURE  = 0x0eadf1a5
MASK64   = (1 << 64) - 1

# ---------------------------------------------------------------- ELF loading
def load_text(data):
    assert data[:4] == b"\x7fELF", "not an ELF"
    e_entry = struct.unpack_from("<Q", data, 24)[0]
    e_phoff = struct.unpack_from("<Q", data, 32)[0]
    e_phentsize = struct.unpack_from("<H", data, 54)[0]
    e_phnum = struct.unpack_from("<H", data, 56)[0]
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags = struct.unpack_from("<II", data, off)
        p_offset, p_vaddr = struct.unpack_from("<QQ", data, off + 8)
        p_filesz = struct.unpack_from("<Q", data, off + 32)[0]
        if p_type == 1:  # PT_LOAD
            segs.append((p_vaddr, p_offset, p_filesz, p_flags))
    # find the segment containing e_entry
    for p_vaddr, p_offset, p_filesz, p_flags in segs:
        if p_vaddr <= e_entry < p_vaddr + p_filesz:
            code = data[p_offset:p_offset + p_filesz]
            return e_entry, p_vaddr, code
    raise RuntimeError("no LOAD segment with entry")

def disasm(data):
    e_entry, base_va, code = load_text(data)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    insns = list(md.disasm(code, base_va))
    # keep only from entry onward
    out = [i for i in insns if i.address >= e_entry]
    return out

# --------------------------------------------------------------- Z3 helpers
def bv(v):
    return z3.BitVecVal(v & MASK64, 64)

def bsr64(x):
    # index of most-significant set bit; 0 when x==0 (unused in that case)
    r = z3.BitVecVal(0, 64)
    for i in range(64):
        r = z3.If(z3.Extract(i, i, x) == 1, z3.BitVecVal(i, 64), r)
    return r

def tzcnt64(x):
    r = z3.BitVecVal(64, 64)
    for i in reversed(range(64)):
        r = z3.If(z3.Extract(i, i, x) == 1, z3.BitVecVal(i, 64), r)
    return r

def popcnt64(x):
    return z3.Sum([z3.ZeroExt(63, z3.Extract(i, i, x)) for i in range(64)])

def concrete(e):
    """Return python int if e is a concrete bitvector value, else None."""
    s = z3.simplify(e)
    if z3.is_bv_value(s):
        return s.as_long()
    return None

# register canonicalisation: map any sub-register to its 64-bit base
_CANON = {}
_R64 = ["rax","rbx","rcx","rdx","rsi","rdi","rbp","rsp"]
for r in _R64:
    _CANON[r] = r
    _CANON["e"+r[1:]] = r
_SUB = {"rax":["ax","al"],"rbx":["bx","bl"],"rcx":["cx","cl"],"rdx":["dx","dl"],
        "rsi":["si","sil"],"rdi":["di","dil"],"rbp":["bp","bpl"],"rsp":["sp","spl"]}
for full, subs in _SUB.items():
    for s in subs:
        _CANON[s] = full
for n in range(8, 16):
    _CANON[f"r{n}"] = f"r{n}"
    _CANON[f"r{n}d"] = f"r{n}"
    _CANON[f"r{n}w"] = f"r{n}"
    _CANON[f"r{n}b"] = f"r{n}"

def canon(name):
    return _CANON.get(name, name)

# --------------------------------------------------------------- Emulator
class Emu:
    def __init__(self, inbytes):
        self.reg = {}                 # name -> BV64
        for r in ["rax","rbx","rcx","rdx","rsi","rdi","rbp","rsp",
                  "r8","r9","r10","r11","r12","r13","r14","r15"]:
            self.reg[r] = bv(0)
        self.reg["rbp"] = bv(REALBASE)
        self.reg["r13"] = bv(0)       # input base marker (value unused)
        self.real = {}                # offset -> BV64
        self.fake = {}
        self.inbytes = inbytes        # list of 32 BV8

    # ---- register access with width-aware sub-register handling
    def rget(self, name, size):
        full = self.reg[canon(name)]
        if size == 8:
            return full
        if size == 4:
            return z3.ZeroExt(32, z3.Extract(31, 0, full))
        if size == 2:
            return z3.ZeroExt(48, z3.Extract(15, 0, full))
        if size == 1:
            return z3.ZeroExt(56, z3.Extract(7, 0, full))
        raise RuntimeError(f"bad reg size {size}")

    def rset(self, name, val, size):
        base = canon(name)
        val = z3.simplify(val)
        if size == 8:
            self.reg[base] = val
        elif size == 4:                       # 32-bit write zero-extends
            self.reg[base] = z3.simplify(z3.ZeroExt(32, z3.Extract(31, 0, val)))
        elif size == 2:
            self.reg[base] = z3.simplify(
                z3.Concat(z3.Extract(63, 16, self.reg[base]), z3.Extract(15, 0, val)))
        elif size == 1:
            self.reg[base] = z3.simplify(
                z3.Concat(z3.Extract(63, 8, self.reg[base]), z3.Extract(7, 0, val)))
        else:
            raise RuntimeError(f"bad reg size {size}")

    # ---- input word: 8 little-endian bytes starting at byte offset `off`
    def input_word(self, off):
        parts = []
        for k in range(8):
            idx = off + k
            b = self.inbytes[idx] if 0 <= idx < len(self.inbytes) else z3.BitVecVal(0,8)
            parts.append(b)
        # little-endian: byte0 is least significant
        w = z3.Concat(list(reversed(parts)))
        return w

    # ---- memory region resolution for [base + disp]
    def mem_read(self, base, disp):
        base = canon(base) if base else base
        if base == "r13":
            return self.input_word(disp)
        val = self.reg[base]
        c = concrete(val)
        if c is not None:
            if c == REALBASE:
                return self.real.get(disp, bv(0))
            if c == FAKEBASE:
                return self.fake.get(disp, bv(0))
            raise RuntimeError(f"unexpected concrete mem base {hex(c)}")
        # symbolic -> must be rbp in {REALBASE, FAKEBASE}
        cond = (val == bv(REALBASE))
        return z3.simplify(z3.If(cond, self.real.get(disp, bv(0)),
                                       self.fake.get(disp, bv(0))))

    def mem_write(self, base, disp, value):
        value = z3.simplify(value)
        base = canon(base) if base else base
        if base == "r13":
            raise RuntimeError("write to input region")
        val = self.reg[base]
        c = concrete(val)
        if c is not None:
            if c == REALBASE:
                self.real[disp] = value
            elif c == FAKEBASE:
                self.fake[disp] = value
            else:
                raise RuntimeError(f"unexpected concrete mem base {hex(c)}")
            return
        cond = (val == bv(REALBASE))
        self.real[disp] = z3.simplify(z3.If(cond, value, self.real.get(disp, bv(0))))
        self.fake[disp] = z3.simplify(z3.If(cond, self.fake.get(disp, bv(0)), value))

    # ---- operand fetch (capstone operand -> BV64)
    def opval(self, insn, op):
        if op.type == CS_OP_REG:
            return self.rget(insn.reg_name(op.reg), op.size)
        if op.type == CS_OP_IMM:
            return bv(op.imm)
        if op.type == CS_OP_MEM:
            base = insn.reg_name(op.mem.base) if op.mem.base != 0 else None
            disp = op.mem.disp
            if op.mem.index != 0:
                raise RuntimeError("indexed mem unsupported")
            return self.mem_read(base, disp)
        raise RuntimeError("bad operand type")

    def opset(self, insn, op, value):
        if op.type == CS_OP_REG:
            self.rset(insn.reg_name(op.reg), value, op.size)
        elif op.type == CS_OP_MEM:
            base = insn.reg_name(op.mem.base) if op.mem.base != 0 else None
            disp = op.mem.disp
            self.mem_write(base, disp, value)
        else:
            raise RuntimeError("cannot write operand")

    # ---- execute one instruction
    def step(self, insn):
        m = insn.mnemonic
        ops = insn.operands
        if m in ("mov","movabs"):
            self.opset(insn, ops[0], self.opval(insn, ops[1])); return
        if m in ("add",):
            self.opset(insn, ops[0], self.opval(insn,ops[0]) + self.opval(insn,ops[1])); return
        if m in ("sub",):
            self.opset(insn, ops[0], self.opval(insn,ops[0]) - self.opval(insn,ops[1])); return
        if m in ("imul",):
            self.opset(insn, ops[0], self.opval(insn,ops[0]) * self.opval(insn,ops[1])); return
        if m in ("and",):
            self.opset(insn, ops[0], self.opval(insn,ops[0]) & self.opval(insn,ops[1])); return
        if m in ("or",):
            self.opset(insn, ops[0], self.opval(insn,ops[0]) | self.opval(insn,ops[1])); return
        if m in ("xor",):
            self.opset(insn, ops[0], self.opval(insn,ops[0]) ^ self.opval(insn,ops[1])); return
        if m in ("not",):
            self.opset(insn, ops[0], ~self.opval(insn,ops[0])); return
        if m in ("shl","sal"):
            cnt = self.opval(insn,ops[1]) & bv(0x3f)
            self.opset(insn, ops[0], self.opval(insn,ops[0]) << cnt); return
        if m in ("shr",):
            cnt = self.opval(insn,ops[1]) & bv(0x3f)
            self.opset(insn, ops[0], z3.LShR(self.opval(insn,ops[0]), cnt)); return
        if m in ("sar",):
            cnt = self.opval(insn,ops[1]) & bv(0x3f)
            self.opset(insn, ops[0], self.opval(insn,ops[0]) >> cnt); return
        if m == "bsr":
            self.opset(insn, ops[0], bsr64(self.opval(insn,ops[1]))); return
        if m == "tzcnt":
            self.opset(insn, ops[0], tzcnt64(self.opval(insn,ops[1]))); return
        if m == "popcnt":
            self.opset(insn, ops[0], popcnt64(self.opval(insn,ops[1]))); return
        raise RuntimeError(f"unhandled insn: {m} {insn.op_str}")

# --------------------------------------------------------------- driver
def find_body(insns):
    # body starts right after `mov rbp, REALBASE`; ends at `mov rax, REALBASE`
    # that is followed by `mov rax, [rax]`.
    start = end = None
    for idx, ins in enumerate(insns):
        if ins.mnemonic in ("mov","movabs") and len(ins.operands) == 2:
            o0, o1 = ins.operands
            if (o0.type == CS_OP_REG and canon(ins.reg_name(o0.reg)) == "rbp"
                    and o1.type == CS_OP_IMM and (o1.imm & MASK64) == REALBASE):
                start = idx + 1
            if (start is not None and end is None
                    and o0.type == CS_OP_REG and canon(ins.reg_name(o0.reg)) == "rax"
                    and o1.type == CS_OP_IMM and (o1.imm & MASK64) == REALBASE):
                # confirm next is mov rax,[rax]
                nxt = insns[idx+1]
                if nxt.mnemonic == "mov" and nxt.operands[1].type == CS_OP_MEM:
                    end = idx
                    break
    assert start is not None and end is not None, "could not locate body"
    return insns[start:end]

def count_blocks(body):
    # Enable emits `mov r8, REALBASE`
    n = 0
    for ins in body:
        if ins.mnemonic in ("mov","movabs") and len(ins.operands) == 2:
            o0, o1 = ins.operands
            if (o0.type == CS_OP_REG and canon(ins.reg_name(o0.reg)) == "r8"
                    and o1.type == CS_OP_IMM and (o1.imm & MASK64) == REALBASE):
                n += 1
    return n

def solve(data, secret_len=32, verbose=True):
    insns = disasm(data)
    body = find_body(insns)
    nblocks = count_blocks(body)
    K = max(nblocks, 1) + 1
    if verbose:
        print(f"[*] {len(insns)} insns, body={len(body)} insns, "
              f"blocks={nblocks}, iterating K={K}", file=sys.stderr)

    inbytes = [z3.BitVec(f"in_{i}", 8) for i in range(secret_len)]
    emu = Emu(inbytes)
    for it in range(K):
        for ins in body:
            emu.step(ins)

    rb0 = emu.real.get(0, bv(0))
    s = z3.Solver()
    for b in inbytes:
        s.add(b >= ord('a'), b <= ord('z'))
    s.add(rb0 == bv(SUCCESS))
    if verbose:
        print("[*] solving...", file=sys.stderr)
    if s.check() != z3.sat:
        print("[!] UNSAT", file=sys.stderr)
        return None
    mdl = s.model()
    out = bytes(mdl[b].as_long() for b in inbytes)
    return out.decode()

def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    else:
        raw = sys.stdin.buffer.read()
        data = base64.b64decode(raw)
    sec = solve(data)
    if sec is not None:
        print(sec)

if __name__ == "__main__":
    main()
