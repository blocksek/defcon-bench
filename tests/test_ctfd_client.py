"""CTFd client tests against a fake HTTP session (no live server)."""

from ctfbench.ctfd import CTFdClient, import_challenges
from ctfbench.models import Challenge


class FakeResp:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}
        self.text = text

    def json(self):
        return self._json


class FakeSession:
    """Programmable session: routes (method, path-substring) -> FakeResp."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def _resolve(self, method, url, kw):
        self.calls.append((method, url, kw))
        for (m, needle), resp in self.routes.items():
            if m == method and needle in url:
                return resp
        return FakeResp(404, {"success": False, "message": "no route"})

    def get(self, url, **kw):
        return self._resolve("GET", url, kw)

    def post(self, url, **kw):
        return self._resolve("POST", url, kw)


def _client(routes, factory=None):
    return CTFdClient("http://ctfd.test", admin_token="tok",
                      session=FakeSession(routes), session_factory=factory)


def test_create_challenge_and_flag():
    routes = {
        ("POST", "/api/v1/challenges"): FakeResp(200, {"success": True, "data": {"id": 7}}),
        ("POST", "/api/v1/flags"): FakeResp(200, {"success": True, "data": {"id": 1}}),
    }
    c = _client(routes)
    cid = c.create_challenge(name="OMGzip", category="reversing",
                             description="d", value=100)
    assert cid == 7
    c.add_static_flag(cid, "flag{x}")
    # assert the flag payload shape
    flag_call = [k for k in c.s.calls if k[0] == "POST" and "/flags" in k[1]][0]
    body = flag_call[2]["json"]
    assert body["challenge_id"] == 7 and body["type"] == "static" and body["content"] == "flag{x}"


def test_admin_auth_header_present():
    c = _client({("GET", "/api/v1/challenges"): FakeResp(200, {"success": True, "data": []})})
    c.list_challenges()
    call = c.s.calls[0]
    assert call[2]["headers"]["Authorization"] == "Token tok"


def test_import_challenges_idempotent():
    # First call: challenge absent -> created. Second: present -> reused.
    state = {"created": False}

    class Sess(FakeSession):
        def get(self, url, **kw):
            self.calls.append(("GET", url, kw))
            data = [{"id": 5, "name": "OMGzip"}] if state["created"] else []
            return FakeResp(200, {"success": True, "data": data})

        def post(self, url, **kw):
            self.calls.append(("POST", url, kw))
            if "/challenges" in url:
                state["created"] = True
                return FakeResp(200, {"success": True, "data": {"id": 5}})
            return FakeResp(200, {"success": True, "data": {"id": 1}})

    c = CTFdClient("http://ctfd.test", admin_token="tok", session=Sess({}))
    ch = Challenge.from_dict({
        "id": "2023-omgzip", "name": "OMGzip", "category": "reversing",
        "description": "d", "flag": {"value": "flag{x}"},
    })
    m1 = import_challenges(c, [ch])
    assert m1 == {"2023-omgzip": 5}
    posts_after_first = sum(1 for k in c.s.calls if k[0] == "POST" and "/challenges" in k[1])
    m2 = import_challenges(c, [ch])  # already exists -> no new create
    assert m2 == {"2023-omgzip": 5}
    posts_after_second = sum(1 for k in c.s.calls if k[0] == "POST" and "/challenges" in k[1])
    assert posts_after_second == posts_after_first  # idempotent


def test_login_and_attempt_flow():
    login_html = '<input name="nonce" value="deadbeef">'
    chal_html = "window.init = {'csrfNonce': \"cafef00d\"}"
    attempt_resp = FakeResp(200, {"success": True,
                                  "data": {"status": "correct", "message": "gg"}})

    def factory():
        return FakeSession({
            ("GET", "/login"): FakeResp(200, text=login_html),
            ("POST", "/login"): FakeResp(200, text=""),
            ("GET", "/challenges"): FakeResp(200, text=chal_html),
            ("POST", "/api/v1/challenges/attempt"): attempt_resp,
        })

    c = _client({}, factory=factory)
    sess = c.login_user("gpt-4o", "pw")
    status, message = sess.attempt(7, "flag{ok}")
    assert status == "correct" and message == "gg"
    # CSRF header carried the nonce from the authenticated page
    attempt_call = [k for k in sess.s.calls if "attempt" in k[1]][0]
    assert attempt_call[2]["headers"]["CSRF-Token"] == "cafef00d"
    assert attempt_call[2]["json"] == {"challenge_id": 7, "submission": "flag{ok}"}
