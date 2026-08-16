from ctfbench.models import Challenge
from ctfbench.scoring import CTFdScorer, LocalScorer, ScoreResult


def _ch(points=100):
    return Challenge.from_dict({
        "id": "c", "name": "C", "category": "misc", "description": "d",
        "points": points, "flag": {"value": "flag{ok}"},
    })


def test_local_scorer_correct_and_wrong():
    ch = _ch(points=150)
    s = LocalScorer()
    good = s.submit(ch, "flag{ok}")
    assert good.correct and good.points == 150 and good.backend == "local"
    bad = s.submit(ch, "flag{no}")
    assert not bad.correct and bad.points == 0
    assert not s.submit(ch, None).correct


class FakeUserSession:
    def __init__(self, status):
        self.status = status
        self.calls = []

    def attempt(self, cid, flag):
        self.calls.append((cid, flag))
        return self.status, "msg"


def test_ctfd_scorer_maps_status():
    ch = _ch(points=300)
    sess = FakeUserSession("correct")
    scorer = CTFdScorer(sess, resolve_id=lambda c: 42)
    res = scorer.submit(ch, "flag{ok}")
    assert res.correct and res.points == 300 and res.backend == "ctfd"
    assert sess.calls == [(42, "flag{ok}")]


def test_ctfd_scorer_already_solved_is_solved():
    res = CTFdScorer(FakeUserSession("already_solved"), lambda c: 1).submit(_ch(), "x")
    assert res.solved and res.correct


def test_ctfd_scorer_unknown_challenge():
    res = CTFdScorer(FakeUserSession("correct"), lambda c: None).submit(_ch(), "x")
    assert not res.correct and res.status == "error"


def test_ctfd_scorer_incorrect():
    res = CTFdScorer(FakeUserSession("incorrect"), lambda c: 1).submit(_ch(), "flag{no}")
    assert not res.correct and res.points == 0
