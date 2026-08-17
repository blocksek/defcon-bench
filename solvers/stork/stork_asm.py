import struct

def varint(n):
    # readVarInteger: base-128 big-endian, continuation bytes have MSB=1, final MSB=0
    # v=(v<<7)|(b&0x7f); loop while byte has MSB set. So final byte MSB=0.
    assert n >= 0
    if n == 0:
        return b'\x00'
    groups = []
    while n > 0:
        groups.append(n & 0x7f)
        n >>= 7
    groups.reverse()  # big-endian
    out = bytearray()
    for i, g in enumerate(groups):
        if i != len(groups) - 1:
            out.append(g | 0x80)
        else:
            out.append(g)
    return bytes(out)

def zigzag(n):
    # encode signed as varint zigzag: (n<<1) ^ (n>>63)
    u = ((n << 1) ^ (n >> 63)) & 0xFFFFFFFFFFFFFFFF
    return varint(u)

def header():
    h = bytearray()
    h += b'\x1bLua'            # signature
    h += b'\x55'              # version
    h += b'\x00'              # format
    h += bytes([0x19,0x93,0x0d,0x0a,0x1a,0x0a])  # LUAC_DATA
    h += b'\x04'             # instruction size
    h += bytes([0x88,0xa9,0xff,0xff])  # 0xffffa988
    h += b'\x04' + struct.pack('<I', 0x12345678)          # read_lv<uint>
    h += b'\x08' + struct.pack('<q', -0x5678)             # read_lv<ll>
    h += b'\x08' + struct.pack('<d', -370.5)              # read_lv<double>
    return bytes(h)

def lstring(s):
    # NEW string: varint(size=L+1), then (L+1) bytes = content + pad
    if s is None:
        return b'\x00'  # size 0 = no string (back-ref path -> avoid unless None)
    b = s if isinstance(s, bytes) else s.encode()
    L = len(b)
    return varint(L+1) + b + b'\x00'

# constants
def k_nil():   return b'\x00'
def k_false(): return b'\x01'
def k_true():  return b'\x11'
def k_int(n):  return b'\x03' + zigzag(n)
def k_float(x):return b'\x13' + struct.pack('<d', x)
def k_str(s):  return b'\x04' + lstring(s)

def align4(buf):
    while len(buf) % 4 != 0:
        buf.append(0)

class Proto:
    def __init__(self, code=None, consts=None, upvals=None, protos=None,
                 numparams=0, is_vararg=1, maxstack=2, line=0, lastline=0, source=None):
        self.code = code or []      # list of uint32
        self.consts = consts or []  # list of encoded constant bytes
        self.upvals = upvals or []  # list of (instack, idx, kind)
        self.protos = protos or []  # list of Proto
        self.numparams = numparams
        self.is_vararg = is_vararg
        self.maxstack = maxstack
        self.line = line
        self.lastline = lastline
        self.source = source

    def serialize(self, cur_offset):
        # cur_offset = file offset where this proto's bytes begin (for alignment of code)
        out = bytearray()
        out += varint(self.line)
        out += varint(self.lastline)
        out += bytes([self.numparams, self.is_vararg, self.maxstack])
        out += varint(len(self.code))
        # align code start to 4 relative to file
        pos = cur_offset + len(out)
        while pos % 4 != 0:
            out.append(0); pos += 1
        for insn in self.code:
            out += struct.pack('<I', insn & 0xffffffff)
        # constants
        out += varint(len(self.consts))
        for c in self.consts:
            out += c
        # upvalues
        out += varint(len(self.upvals))
        for (a,b,c) in self.upvals:
            out += bytes([a,b,c])
        # protos
        out += varint(len(self.protos))
        for p in self.protos:
            out += p.serialize(cur_offset + len(out))
        # source string
        out += lstring(self.source)
        # debug: 4 zero varints
        out += b'\x00\x00\x00\x00'
        return bytes(out)

def closure(nupvalues, proto, cur_offset):
    out = bytearray()
    out += bytes([nupvalues])
    out += proto.serialize(cur_offset + 1)
    return bytes(out)

def build(closures):
    out = bytearray()
    out += header()
    for (nup, proto) in closures:
        out += closure(nup, proto, len(out))
    return bytes(out)

if __name__ == '__main__':
    import sys
    # header only
    data = header()
    sys.stdout.buffer.write(data)

# ---- Lua 5.4 instruction encoding (VERIFY opcode numbers/masks against run_vm) ----
# iABC: OP[0:7] A[7:15] k[15] B[16:24] C[24:32]
# iABx: OP[0:7] A[7:15] Bx[15:32]
# iAsBx: Bx = sBx + 0xFFFF (OFFSET_sBx = (2^17-1)>>1 = 65535)
# iAx : OP[0:7] Ax[7:32]
# isJ : OP[0:7] sJ[7:32], OFFSET_sJ = (2^25-1)>>1

def iABC(op, a=0, b=0, c=0, k=0):
    return (op & 0x7f) | ((a & 0xff) << 7) | ((k & 1) << 15) | ((b & 0xff) << 16) | ((c & 0xff) << 24)

def iABx(op, a=0, bx=0):
    return (op & 0x7f) | ((a & 0xff) << 7) | ((bx & 0x1ffff) << 15)

def iAsBx(op, a=0, sbx=0):
    return iABx(op, a, sbx + 0xffff)

def iAx(op, ax=0):
    return (op & 0x7f) | ((ax & 0x1ffffff) << 7)

def isJ(op, sj=0):
    OFF = ((1<<25)-1)>>1
    return (op & 0x7f) | (((sj + OFF) & 0x1ffffff) << 7)

# Standard Lua 5.4 opcode numbers (to be confirmed):
OP = {
 'MOVE':0,'LOADI':1,'LOADF':2,'LOADK':3,'LOADKX':4,'LOADFALSE':5,'LFALSESKIP':6,
 'LOADTRUE':7,'LOADNIL':8,'GETUPVAL':9,'SETUPVAL':10,'GETTABUP':11,'GETTABLE':12,
 'GETI':13,'GETFIELD':14,'SETTABUP':15,'SETTABLE':16,'SETI':17,'SETFIELD':18,
 'NEWTABLE':19,'SELF':20,'ADDI':21,'ADDK':22,'SUBK':23,'MULK':24,'MODK':25,'POWK':26,
 'DIVK':27,'IDIVK':28,'BANDK':29,'BORK':30,'BXORK':31,'SHRI':32,'SHLI':33,
 'ADD':34,'SUB':35,'MUL':36,'MOD':37,'POW':38,'DIV':39,'IDIV':40,'BAND':41,'BOR':42,
 'BXOR':43,'SHL':44,'SHR':45,'MMBIN':46,'MMBINI':47,'MMBINK':48,'UNM':49,'BNOT':50,
 'NOT':51,'LEN':52,'CONCAT':53,'CLOSE':54,'TBC':55,'JMP':56,'EQ':57,'LT':58,'LE':59,
 'EQK':60,'EQI':61,'LTI':62,'LEI':63,'GTI':64,'GEI':65,'TEST':66,'TESTSET':67,
 'CALL':68,'TAILCALL':69,'RETURN':70,'RETURN0':71,'RETURN1':72,'FORLOOP':73,'FORPREP':74,
 'TFORPREP':75,'TFORCALL':76,'TFORLOOP':77,'SETLIST':78,'CLOSURE':79,'VARARG':80,'VARARGPREP':81,'EXTRAARG':82,
}
