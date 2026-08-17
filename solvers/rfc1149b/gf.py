# GF(2)[x]/m arithmetic and idempotents for the reducible modulus m used by rfc1149b.
M = 0b111010110110101010100001111011100101101110010011011110111110010111001111100101001001110111110110000001101111110110010001100110111
DEG = 128
assert M.bit_length() == DEG+1

def clmul(a,b):
    r=0
    while b:
        if b&1: r^=a
        b>>=1; a<<=1
    return r
def polymod(a, mod):
    dm = mod.bit_length()-1
    while a.bit_length()-1 >= dm and a:
        a ^= mod << (a.bit_length()-1 - dm)
    return a
def gfmul(a,b):        # multiply mod M
    return polymod(clmul(a,b), M)

def poly_divmod(a, b):
    q=0; db=b.bit_length()-1
    while a.bit_length()-1 >= db and a:
        sh = a.bit_length()-1 - db
        q ^= 1<<sh
        a ^= b<<sh
    return q, a
def poly_egcd(a,b):
    # returns (g, s, t) with s*a + t*b = g  over GF(2)[x]
    old_r,r = a,b
    old_s,s = 1,0
    old_t,t = 0,1
    while r:
        q,_ = poly_divmod(old_r, r)
        old_r, r = r, old_r ^ clmul(q,r)
        old_s, s = s, old_s ^ clmul(q,s)
        old_t, t = t, old_t ^ clmul(q,t)
    return old_r, old_s, old_t

# Factor M (degrees/mult from sympy earlier). Rebuild the prime-power factors as integers.
def factor_M():
    import sympy
    from sympy import Poly, symbols
    x=symbols('x')
    coeffs=[(M>>i)&1 for i in range(M.bit_length()-1,-1,-1)]
    p=Poly(coeffs,x,modulus=2)
    facs=[]
    for f,e in p.factor_list()[1]:
        cs=f.all_coeffs()
        val=0
        for c in cs:
            val=(val<<1)| (int(c)&1)
        facs.append((val, e))   # (irreducible poly as int, multiplicity)
    return facs

def prime_power_factors():
    out=[]
    for pol,e in factor_M():
        # factor integer f_i = pol^e
        fi=1
        for _ in range(e):
            fi=clmul(fi,pol)
        out.append(fi)
    # sanity: product == M
    prod=1
    for fi in out: prod=clmul(prod,fi)
    assert prod==M, (hex(prod),hex(M))
    return out

def idempotents():
    facs=prime_power_factors()
    es=[]
    for fi in facs:
        gi,_=poly_divmod(M, fi)      # cofactor = M/fi (exact)
        g,s,t=poly_egcd(fi,gi)
        assert g==1, hex(g)
        ei=polymod(clmul(t,gi), M)   # ≡0 mod fi? -> t*gi ≡1 mod fi, ≡0 mod gi
        # want e≡1 mod fi and ≡0 mod others(=gi). t*gi ≡ 0 mod gi, and s*fi+t*gi=1 => t*gi≡1 mod fi. good.
        es.append((ei, fi))
    # check sum of idempotents == 1 and orthogonality
    s=0
    for ei,_ in es: s^=ei
    assert s==1, hex(s)
    return es   # list of (e_i, f_i)

if __name__=="__main__":
    es=idempotents()
    print("num components:", len(es))
    for i,(ei,fi) in enumerate(es):
        print(f"comp{i:2d} degfi={fi.bit_length()-1:2d}  e*e==e:{gfmul(ei,ei)==ei}")
    # orthogonality spot check
    print("e0*e1==0:", gfmul(es[0][0], es[1][0])==0)
