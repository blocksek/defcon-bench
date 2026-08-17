#!/usr/bin/env python3
"""black-talon reference client — full solve against the REAL orchestrator service.

Intended technique (see solvers/black-talon SOLUTION.md): the proactive-reshare
committee never dedups the "new user" (client/src/main.rs:434 selection, :780 add,
Users::add:1094 bare push). A malicious committee member re-selects itself, growing
one extra committee slot per completed round, until it holds `threshold` seats and
harvests that many shares of the reshared polynomial -> recovers the 64-char secret
-> GOODBYE -> orchestrator asks for the guess -> flag.

Against the SHIPPED 5-of-10 parameters this needs 4 growth rounds + 1 harvest round.
Design notes (reverse-engineered from the handout source):
  * A reshare round only starts when some committee member is INACTIVE
    (main.rs:642 aborts PROPOSE otherwise). Bots quit at random (~0.0001/loop), so
    completed rounds are quit-gated; failed rounds are aborted+retried instantly
    without consuming the dead member.
  * Selection is `active_users[XOR(valid revealed shares) % len]` (main.rs:434).
    We STEER it with reveal-last rushing: per-slot commit values 2^0..2^{k-1} mean
    our subset-XOR covers every residue 0..2^k-1, so with k slots we control a
    2^k/L fraction of outcomes (k>=6 => always). Bots reveal only after all active
    members commit, and the 3s Begin timer (main.rs:411) leaves ample time to see
    every reveal before choosing our subset.
  * Zero blinders (NGC with all-ones commits, r-shares of 0) pass is_share_valid
    trivially and keep P'(0)=secret intact, so our harvested n-shares + the public
    t reconstruct the secret regardless of us never sending n-shares.
Env knobs: BT_ATTEMPTS (games to try, default 2), BT_GAME_BUDGET (seconds per game,
default 1000).
"""
import os, re, socket, sys, time, threading, random

HOST, PORT = os.environ["CHAL_HOST"], int(os.environ["CHAL_PORT"])


def b36(n):
    if n == 0: return "0"
    d = "0123456789abcdefghijklmnopqrstuvwxyz"; s = ""; n = int(n)
    while n > 0: s = d[n % 36] + s; n //= 36
    return s


def p36(s): return int(s, 36)


class Conn:
    """Mid-stream splice: the orchestrator already ran CONNECT/JOIN for us."""

    def __init__(self, host, port):
        self.s = socket.create_connection((host, port), timeout=60)
        self.f = self.s.makefile("rwb", buffering=0)
        self.msgs, self.ctrl = [], []
        self.lock = threading.Lock()
        self.alive = True
        self.dead = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _r(self): return self.f.readline().decode("utf-8", "replace").rstrip("\n")
    def _w(self, s): self.f.write((s + "\n").encode())

    def _loop(self):
        while self.alive:
            try: l = self._r()
            except Exception: break
            if l == "": break
            with self.lock:
                (self.msgs if l.startswith("MSGFROM ") else self.ctrl).append(l)
        self.dead = True

    def chan(self, ch, payload): self._w(f"MSG {ch} {payload}")
    def dm(self, to, payload): self._w(f"MSG @{to} {payload}")

    def drain(self):
        with self.lock:
            m = self.msgs[:]; self.msgs.clear(); return m

    def peek(self, ch, timeout=4.0):
        """PEEK <channel> -> list of active user names (join order), or None."""
        with self.lock: self.ctrl.clear()
        try: self._w(f"PEEK {ch}")
        except Exception: return None
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                for l in self.ctrl:
                    if l.startswith("USERS "):
                        return l[6:].split(" ")
            time.sleep(0.02)
        return None

    def close(self):
        self.alive = False
        try: self.s.close()
        except Exception: pass


def reconstruct(shares, q):
    """Lagrange interpolation at x=0 over GF(q); shares = {key_int: value_int}."""
    r = 0; xs = list(shares)
    for i in xs:
        yi = shares[i]; num = 1; den = 1
        for j in xs:
            if j != i:
                num = (num * (-j)) % q; den = (den * (i - j)) % q
        r = (r + yi * num * pow(den, -1, q)) % q
    return r % q


def solve(log):
    """Play one fresh game (new orchestrator per connection). Returns flag or None."""
    c = Conn(HOST, PORT)

    # ---- Phase A: learn identity (orchestrator splices us in as the protagonist) ----
    ident = q = g = None; commitments = None; committee = None
    mykey = myshare = None; name = channel = None
    t0 = time.time()
    while time.time() - t0 < 120 and (ident is None or myshare is None or channel is None):
        if c.dead: log("connection died during identity"); return None
        for l in c.drain():
            parts = l.split(" ", 3)
            if len(parts) < 4: continue
            ch, frm, rest = parts[1], parts[2], parts[3]
            tok = rest.split(" ")
            if channel is None and ch != "@": channel = ch
            if tok[0] == "COMMITMENTS":
                ident = tok[1]; q = p36(tok[2]); g = p36(tok[3])
                commitments = [p36(x) for x in tok[4].split(",")]
                committee = tok[5].split(",")
                log("COMMITMENTS ident", ident, "committee", committee)
            elif tok[0] == "SHARE" and ch == "@":
                if ident is None: continue
                mykey = int(tok[2]); myshare = p36(tok[3])
                log("SHARE key", mykey)
        time.sleep(0.1)
    if myshare is None or channel is None:
        log("FAILED to get a share; abandoning this game"); c.close(); return None
    THR = len(commitments)
    name = committee[mykey - 1]
    log("we are", name, "in channel", channel, "THR", THR)

    # ---- Phase B/C: drive reshare rounds, steer selection, grow, harvest ----
    k = committee.count(name)
    phase = "idle"           # idle | reveal | begin | blind
    nonce = None; reveals = {}; our_vals = []; deadline = 0.0
    begin_old = None; harvest_mode = False
    harvested = {}; tval = None
    secret = None
    active = None; last_peek = 0.0; last_propose = 0.0; last_status = time.time()
    got_any = False; silent = 0   # dead-game detection: proposes met with silence
    t_end = time.time() + float(os.environ.get("BT_GAME_BUDGET", "1000"))

    def fresh_active():
        nonlocal active, last_peek
        a = c.peek(channel)
        if a: active = a; last_peek = time.time()
        return active

    def dead_member():
        a = fresh_active()
        if a is None: return None
        for u in committee:
            if u not in a: return u
        return None

    def commit_vals():
        return [1 << i for i in range(k)]   # 2^0..2^{k-1}: subset-XOR covers 0..2^k-1

    def send_commits(n):
        for v in commit_vals():
            c.chan(channel, f"RECOMM {ident} {n} NUC {b36(pow(g, v, q))}")

    def propose():
        nonlocal nonce, phase, reveals, our_vals, deadline, last_propose, got_any
        nonce = str(random.randrange(1, 2**31))
        c.chan(channel, f"RECOMM {ident} {nonce} PROPOSE")
        our_vals = commit_vals()
        send_commits(nonce)
        reveals = {}; phase = "reveal"; deadline = time.time() + 2.5
        last_propose = time.time(); got_any = False

    while secret is None and time.time() < t_end and not c.dead:
        for l in c.drain():
            parts = l.split(" ", 3)
            if len(parts) < 4: continue
            ch, frm, rest = parts[1], parts[2], parts[3]
            tok = rest.split(" ")
            if tok[0] != "RECOMM" or tok[1] != ident: continue
            n = tok[2]; inner = tok[3:]; kind = inner[0]
            if kind == "PROPOSE":
                # adopt the newest round (bots' 100s ticks may pre-empt ours)
                nonce = n; reveals = {}; our_vals = commit_vals()
                send_commits(nonce)
                phase = "reveal"; deadline = time.time() + 2.5
                continue
            if n != nonce: continue          # stale/other round
            got_any = True
            if kind == "NUR" and ch != "@":
                if frm != name: reveals[frm] = int(inner[1])
            elif kind == "BEGIN":
                user = inner[1]; b_old = inner[5].split(",")
                if user == name:
                    begin_old = b_old
                    our_keys = [i + 1 for i, u in enumerate(b_old) if u == name]
                    harvest_mode = (len(our_keys) + 1) >= THR
                    ones = ",".join(["1"] * THR)
                    for kk in our_keys:
                        c.chan(channel, f"RECOMM {ident} {nonce} NGC {kk} {ones} {ones}")
                    time.sleep(0.05)
                    for kk in our_keys:
                        for i, u in enumerate(b_old):
                            c.dm(u, f"RECOMM {ident} {nonce} NGS {kk} {i + 1} 0 R")
                    harvested = {}; tval = None
                    phase = "blind"; deadline = time.time() + 20.0
                    log("*** SELECTED slots", len(our_keys), "->", len(our_keys) + 1,
                        "(harvest)" if harvest_mode else "(grow)")
                else:
                    # honest selection of someone else: kill the round, keep the
                    # dead member available, retry immediately
                    c.chan(channel, f"RECOMM {ident} {nonce} JACCUSE {name}")
                    phase = "idle"; nonce = None
            elif kind == "NGS" and ch == "@":
                if phase == "blind" and harvest_mode and inner[4] == "N":
                    harvested.setdefault(int(inner[2]), {})[int(inner[1])] = p36(inner[3])
            elif kind == "PR" and ch != "@":
                tval = p36(inner[1])
                if phase == "blind":
                    if harvest_mode and len(harvested) >= THR:
                        keys = sorted(harvested)
                        shares = {kk: (sum(harvested[kk].values()) + tval) % q for kk in keys}
                        sec = reconstruct(shares, q)
                        b = sec.to_bytes((sec.bit_length() + 7) // 8, "little")
                        try: s = b.decode()
                        except Exception: s = None
                        if s and re.fullmatch(r"[A-Za-z0-9]{64}", s):
                            secret = s; log("RECOVERED SECRET:", s); break
                        log("reconstruction implausible; continuing")
                    # round completed -> committee grew & dead members were pruned
                    a = fresh_active() or []
                    committee = [u for u in begin_old + [name] if u in a]
                    k = committee.count(name)
                    log("round completed; our slots:", k, "committee size:", len(committee))
                    phase = "idle"; nonce = None
            elif kind == "JACCUSE":
                if phase != "idle": phase = "idle"; nonce = None
        if secret or c.dead: break
        now = time.time()

        # ---- steering decision (reveal-last rushing) ----
        if phase == "reveal":
            a = active if (active and now - last_peek < 5) else fresh_active()
            if a is not None and name in a:
                need = {u for u in committee if u in a and u != name}
                if (need and need <= set(reveals)) or now > deadline:
                    if not got_any:
                        # total silence after our propose: the bots removed the
                        # share (panic collapse) — the game is dead; bail fast
                        silent += 1
                        if silent >= 2:
                            log("proposes met with silence — game dead; bailing")
                            c.close(); return None
                        phase = "idle"; nonce = None
                    else:
                        silent = 0
                        L = len(a); idx = a.index(name)
                        xb = 0
                        for u, v in reveals.items():
                            if u in committee: xb ^= v
                        target = None
                        for s in range(1 << k):
                            if ((xb ^ s) % L) == idx: target = s; break
                        if target is None:
                            c.chan(channel, f"RECOMM {ident} {nonce} JACCUSE {name}")
                            phase = "idle"; nonce = None
                        else:
                            for i in range(k):
                                if (target >> i) & 1:
                                    c.chan(channel, f"RECOMM {ident} {nonce} NUR {1 << i}")
                            phase = "begin"; deadline = now + 6.0
            elif now > deadline + 3:
                phase = "idle"; nonce = None

        # ---- watchdogs ----
        elif phase == "begin" and now > deadline:
            c.chan(channel, f"RECOMM {ident} {nonce} JACCUSE {name}")
            phase = "idle"; nonce = None
        elif phase == "blind" and now > deadline:
            log("blind phase stalled; treating round as aborted")
            phase = "idle"; nonce = None

        # ---- drive: start a round whenever one is possible ----
        if phase == "idle" and active is not None and len(active) < 35 and k < THR:
            # the next completed round would trip the panic check (main.rs:750) —
            # this game can no longer be won; bail fast for a fresh one
            log(f"active {len(active)} below panic floor with {k}/{THR} slots; bailing")
            c.close(); return None
        if phase == "idle" and now - last_propose > 1.5:
            if dead_member() is not None:
                propose()
            elif now - last_peek > 5:
                fresh_active()

        if now - last_status > 30:
            last_status = now
            log("status: slots", k, "/", THR, "phase", phase,
                "active", (len(active) if active else "?"),
                "t+", int(now - t0), "s")
        time.sleep(0.03)

    if not secret:
        log("game budget exhausted without the secret"); c.close(); return None

    # ---- Phase D: end the game; orchestrator asks for our guess ----
    # Protocol quirk (verified): after GOODBYE the network closes the nc side
    # (TATA_AND_FAREWELL), but the orchestrator's stdin-relay thread stays blocked
    # in read_available on OUR still-open socket and never sees the dead flag — a
    # deadlock; the orchestrator never reaches the guess prompt. Sending one extra
    # line (a "poke") unblocks it so the game tears down and the prompt arrives.
    # Only THEN do we send the guess (it must land in the orchestrator's read_line,
    # not the dying nc relay).
    def waitfor(sub, tmo):
        t0 = time.time()
        while time.time() - t0 < tmo:
            with c.lock:
                lines = c.ctrl[:]; c.ctrl.clear()
            if any(sub in l for l in lines): return True
            if c.dead: return False
            time.sleep(0.2)
        return False

    c._w("GOODBYE")
    log("sent GOODBYE; awaiting TATA_AND_FAREWELL…")
    waitfor("TATA_AND_FAREWELL", 20)
    time.sleep(1)
    c._w("")                    # poke: unblock the orchestrator stdin relay
    if not waitfor("What do you do?", 120):
        log("no guess prompt arrived; abandoning"); c.close(); return None
    time.sleep(0.5)
    c._w(secret)
    log("sent guess; reading flag…")
    out = []
    t2 = time.time()
    while time.time() - t2 < 30:
        with c.lock:
            out.extend(c.ctrl); c.ctrl.clear()
        out.extend(c.drain())
        text = "\n".join(out)
        m = re.search(r"bbb\{[^}]+\}", text)
        if m:
            print("CAPTURED_FLAG=" + m.group(0), flush=True)
            c.close()
            return m.group(0)
        if "Ain't your kind" in text or "Keep on movin" in text:
            # orchestrator evaluated the guess and REJECTED it: our harvested
            # shares must have been inconsistent (shouldn't happen) — retry
            log("guess REJECTED — reconstructed secret did not match")
            c.close()
            return None
        time.sleep(0.3)
    log("no flag seen; last lines:", out[-10:])
    c.close()
    return None


def main():
    log = lambda *a: print("[bt]", *a, flush=True)
    attempts = int(os.environ.get("BT_ATTEMPTS", "2"))
    for attempt in range(1, attempts + 1):
        log(f"=== game attempt {attempt}/{attempts} ===")
        try:
            flag = solve(log)
        except Exception as e:
            log("game error:", repr(e)); flag = None
        if flag: return
        # give the previous orchestrator time to reap its 51 clients before the
        # next game spawns (avoids CPU-contention poisoning under qemu-user)
        if attempt < attempts: time.sleep(12)
    log("FAILED to recover secret")
    sys.exit(1)


main()
