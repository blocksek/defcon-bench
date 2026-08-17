#!/usr/bin/env python3
"""ctfd_setup.py — automated CTFd bring-up for a bench run (stdlib only).

Does, in order:
  1. wait for CTFd HTTP
  2. POST /setup (creates admin account)                [fresh instances only]
  3. create one challenge + static flag per flags-file entry (admin session)
  4. create the agent (non-admin) user            (admin session)
  5. create an API token for ADMIN                (admin session)
  6. login as agent and create an API token for the AGENT (agent session —
     CTFd 3.8 creates tokens only for the session user; user_id is ignored)

Gotcha encoded here: CTFd only honors `Authorization: Token` when the request
has `Content-Type: application/json` — including GETs (is_json check). This
client sends it unconditionally.

Reads JSON config from stdin:
  {"ctfd_url","admin_name","admin_password","agent_name","agent_password",
   "challenges": [{"name","category","description","value","flag"}, ...]}
Prints JSON: {"admin_token","agent_token","agent_id","challenge_ids"}
"""
import json, re, sys, time, urllib.request, urllib.parse, http.cookiejar

cfg = json.load(sys.stdin)
BASE = cfg["ctfd_url"].rstrip("/")

def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def req(op, method, path, data=None, headers=None, form=False, token=None):
    h = {"Content-Type": "application/json"}   # ALWAYS (see module docstring)
    h.update(headers or {})
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
    if token:
        h["Authorization"] = "Token " + token
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    return op.open(r, timeout=30)

def nonce(op, path="/"):
    html = req(op, "GET", path).read().decode("utf-8", "replace")
    m = re.search(r"'csrfNonce': \"([a-f0-9]{64})\"", html)
    if not m:
        raise RuntimeError("no csrfNonce at " + path)
    return m.group(1)

def session_api(op, method, path, data=None):
    r = req(op, method, path, data=data, headers={"CSRF-Token": nonce(op)})
    return json.loads(r.read())

admin = make_opener()

# 1. wait for up
for _ in range(120):
    try:
        req(admin, "GET", "/")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("CTFd never came up")

# 2. initial setup (fresh instance only)
html = req(admin, "GET", "/setup").read().decode("utf-8", "replace")
m = re.search(r"'csrfNonce': \"([a-f0-9]{64})\"", html)
if m and "Confirm" not in html:
    req(admin, "POST", "/setup", data={
        "ctf_name": "defcon-bench",
        "ctf_description": "DEF CON 2026 quals agent bench",
        "name": cfg["admin_name"], "email": "admin@bench.local",
        "password": cfg["admin_password"], "user_mode": "users",
        "nonce": m.group(1)}, form=True)

# 3. challenges + flags
ids = {}
for ch in cfg["challenges"]:
    r = session_api(admin, "POST", "/api/v1/challenges", {
        "name": ch["name"], "category": ch["category"],
        "description": ch["description"], "value": ch["value"],
        "state": "visible", "type": "standard"})
    cid = r["data"]["id"]
    ids[ch["name"]] = cid
    session_api(admin, "POST", "/api/v1/flags", {
        "challenge": cid, "content": ch["flag"], "type": "static"})

# 4. agent user
r = session_api(admin, "POST", "/api/v1/users", {
    "name": cfg["agent_name"], "email": "agent@bench.local",
    "password": cfg["agent_password"], "type": "user"})
agent_id = r["data"]["id"]

# 5. admin token (admin session)
r = session_api(admin, "POST", "/api/v1/tokens", {})
admin_token = r["data"]["value"]

# 6. agent token (login as agent first)
agent = make_opener()
n = nonce(agent, "/login")
req(agent, "POST", "/login", data={
    "name": cfg["agent_name"], "password": cfg["agent_password"], "nonce": n}, form=True)
r = session_api(agent, "POST", "/api/v1/tokens", {})
agent_token = r["data"]["value"]

print(json.dumps({"admin_token": admin_token, "agent_token": agent_token,
                  "agent_id": agent_id, "challenge_ids": ids}))
