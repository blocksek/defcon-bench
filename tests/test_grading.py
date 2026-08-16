from ctfbench.grading import combine, grade_submission, grade_transcript
from ctfbench.models import Flag


def test_grade_submission_correct():
    flag = Flag(value="flag{ok}")
    g = grade_submission(flag, "flag{ok}")
    assert g.solved and g.matched_flag == "flag{ok}"


def test_grade_submission_wrong_and_none():
    flag = Flag(value="flag{ok}")
    assert not grade_submission(flag, "flag{nope}").solved
    assert not grade_submission(flag, None).solved


def test_grade_transcript_scan():
    flag = Flag(value="flag{leak}")
    assert grade_transcript(flag, "...flag{leak}...").solved
    assert not grade_transcript(flag, "nothing").solved


def test_combine_prefers_solve():
    flag = Flag(value="flag{ok}")
    wrong = grade_submission(flag, "flag{no}")
    right = grade_transcript(flag, "flag{ok}")
    assert combine(wrong, right).solved
    assert not combine(wrong, grade_transcript(flag, "x")).solved
