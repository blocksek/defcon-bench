"""Thin CTFd REST client + high-level helpers for the CTFd scoreboard backend.

Design goals:
  * Admin operations (create challenges/flags/users) authenticate with a CTFd
    access token (``Authorization: Token ...``), which is exempt from CSRF.
  * Competitor operations (submitting a flag as a model's user) go through a
    normal login session and carry CTFd's ``CSRF-Token`` header.
  * The HTTP layer is a session object with ``.get``/``.post`` so tests can
    inject a fake and assert on endpoints/payloads without a live server.

Nothing here imports ``requests`` at module load; the default session is built
lazily so the rest of the harness works without the ``ctfd`` extra installed.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from .models import Challenge

_CSRF_PATTERNS = [
    re.compile(r"['\"]csrfNonce['\"]\s*:\s*['\"]([0-9a-fA-F]+)['\"]"),
    re.compile(r"name=['\"]nonce['\"]\s+value=['\"]([0-9a-fA-F]+)['\"]"),
]


def _extract_nonce(html: str) -> Optional[str]:
    for pat in _CSRF_PATTERNS:
        m = pat.search(html or "")
        if m:
            return m.group(1)
    return None


def _new_session():
    import requests  # lazy; only needed for a live CTFd

    return requests.Session()


class CTFdError(RuntimeError):
    pass


class CTFdClient:
    """Admin-facing CTFd client (token auth)."""

    def __init__(
        self,
        base_url: str,
        admin_token: Optional[str] = None,
        session: Optional[Any] = None,
        timeout: int = 30,
        session_factory: Optional[Callable[[], Any]] = None,
    ):
        self.base = base_url.rstrip("/")
        self.token = admin_token
        self.timeout = timeout
        self.s = session if session is not None else _new_session()
        # Used to mint fresh (cookie-isolated) sessions for competitor logins.
        self._session_factory = session_factory or _new_session

    # -- low level ----------------------------------------------------------

    def _headers(self, json: bool = True) -> dict:
        h: dict[str, str] = {}
        if self.token:
            h["Authorization"] = f"Token {self.token}"
        if json:
            h["Content-Type"] = "application/json"
        return h

    def _get(self, path: str, **kw):
        return self.s.get(self.base + path, timeout=self.timeout, **kw)

    def _post(self, path: str, **kw):
        return self.s.post(self.base + path, timeout=self.timeout, **kw)

    @staticmethod
    def _data(resp) -> Any:
        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise CTFdError(f"non-JSON response ({getattr(resp,'status_code','?')})") from exc
        if not body.get("success", False):
            raise CTFdError(f"CTFd error: {body.get('errors') or body.get('message') or body}")
        return body.get("data")

    # -- admin ops ----------------------------------------------------------

    def ping(self) -> bool:
        try:
            r = self._get("/api/v1/challenges", headers=self._headers(json=False))
            return r.status_code < 500
        except Exception:  # noqa: BLE001
            return False

    def list_challenges(self) -> list[dict]:
        r = self._get("/api/v1/challenges?view=admin", headers=self._headers(json=False))
        return self._data(r) or []

    def find_challenge_id(self, name: str) -> Optional[int]:
        for c in self.list_challenges():
            if c.get("name") == name:
                return c.get("id")
        return None

    def create_challenge(self, *, name: str, category: str, description: str,
                         value: int, state: str = "visible") -> int:
        payload = {
            "name": name,
            "category": category,
            "description": description,
            "value": int(value),
            "state": state,
            "type": "standard",
        }
        r = self._post("/api/v1/challenges", json=payload, headers=self._headers())
        return self._data(r)["id"]

    def add_static_flag(self, challenge_id: int, content: str,
                        case_insensitive: bool = False) -> None:
        payload = {
            "challenge_id": challenge_id,
            "content": content,
            "type": "static",
            "data": "case_insensitive" if case_insensitive else "",
        }
        r = self._post("/api/v1/flags", json=payload, headers=self._headers())
        self._data(r)

    def create_user(self, name: str, password: str, email: Optional[str] = None) -> int:
        payload = {
            "name": name,
            "email": email or f"{name}@bench.local",
            "password": password,
            "type": "user",
            "verified": True,
            "hidden": True,  # keep bench users out of nobody's way; still scored
        }
        r = self._post("/api/v1/users", json=payload, headers=self._headers())
        return self._data(r)["id"]

    def find_user_id(self, name: str) -> Optional[int]:
        r = self._get("/api/v1/users?view=admin", headers=self._headers(json=False))
        for u in (self._data(r) or []):
            if u.get("name") == name:
                return u.get("id")
        return None

    def scoreboard(self) -> list[dict]:
        r = self._get("/api/v1/scoreboard", headers=self._headers(json=False))
        return self._data(r) or []

    # -- competitor login ---------------------------------------------------

    def login_user(self, name: str, password: str) -> "CTFdUserSession":
        """Log in as ``name`` and return a session that can submit flags."""
        sess = self._session_factory()
        login_page = sess.get(self.base + "/login", timeout=self.timeout)
        nonce = _extract_nonce(getattr(login_page, "text", ""))
        if not nonce:
            raise CTFdError("could not read login CSRF nonce")
        sess.post(
            self.base + "/login",
            data={"name": name, "password": password, "nonce": nonce, "_submit": "Submit"},
            timeout=self.timeout,
            allow_redirects=True,
        )
        # Fetch an API CSRF nonce from an authenticated page.
        home = sess.get(self.base + "/challenges", timeout=self.timeout)
        api_nonce = _extract_nonce(getattr(home, "text", "")) or nonce
        return CTFdUserSession(self.base, sess, api_nonce, self.timeout)


class CTFdUserSession:
    """A logged-in competitor session; submits flags to the attempt endpoint."""

    def __init__(self, base: str, session: Any, csrf_nonce: str, timeout: int = 30):
        self.base = base
        self.s = session
        self.nonce = csrf_nonce
        self.timeout = timeout

    def attempt(self, challenge_id: int, flag: str) -> tuple[str, str]:
        """Submit ``flag`` for ``challenge_id``; return (status, message).

        status is CTFd's verdict: ``correct`` | ``incorrect`` |
        ``already_solved`` | ``paused`` | ``ratelimited`` | ``error``.
        """
        headers = {"Content-Type": "application/json", "CSRF-Token": self.nonce}
        r = self.s.post(
            self.base + "/api/v1/challenges/attempt",
            json={"challenge_id": challenge_id, "submission": flag},
            headers=headers,
            timeout=self.timeout,
        )
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            return "error", f"non-JSON response ({getattr(r,'status_code','?')})"
        data = body.get("data") or {}
        return data.get("status", "error"), data.get("message", "")


# --------------------------------------------------------------------------
# High-level orchestration
# --------------------------------------------------------------------------


def import_challenges(client: CTFdClient, challenges: list[Challenge],
                     *, update: bool = False) -> dict[str, int]:
    """Ensure each benchmark challenge exists in CTFd; return id map {ch.id: cid}.

    Idempotent: existing challenges (matched by name) are reused unless already
    present. Registers the ground-truth flag as a static flag.
    """
    mapping: dict[str, int] = {}
    for ch in challenges:
        cid = client.find_challenge_id(ch.name)
        if cid is None:
            cid = client.create_challenge(
                name=ch.name,
                category=ch.category,
                description=_ctfd_description(ch),
                value=ch.points or _default_points(ch.difficulty),
            )
            client.add_static_flag(cid, ch.flag.value)
        mapping[ch.id] = cid
    return mapping


def ensure_user(client: CTFdClient, name: str, password: str) -> int:
    uid = client.find_user_id(name)
    if uid is not None:
        return uid
    return client.create_user(name, password)


def _ctfd_description(ch: Challenge) -> str:
    parts = [ch.description.strip()]
    if ch.is_service:
        parts.append(
            "\n\n(Deployed by the harness; connect to the host/port the runner "
            "provides.)"
        )
    return "\n".join(parts)


def _default_points(difficulty: str) -> int:
    return {
        "trivial": 50, "easy": 100, "medium": 200, "hard": 300,
    }.get(difficulty, 100)
