"""Regression coverage for the two visible scheduling fields: Next and Deadline."""
from datetime import date

import pytest

from career_job_manager.model import (
    ApplicationRecord,
    default_next, end_of_current_week, next_value, normalize_deadline,
    normalize_next, sort_records,
)
from career_job_manager.store import CareerStore


def record(id="a", **changes):
    values = {"id": id, "company": "HSBC", "job": "Investment Specialist",
              "action": "Apply", "when": "2026-fall"}
    values.update(changes)
    return ApplicationRecord(**values)


def test_week_ends_on_sunday_and_recalculates_without_storing_next():
    old = record(deadline="2026-fall")
    assert end_of_current_week(date(2026, 11, 9)) == date(2026, 11, 15)
    assert default_next(old, date(2026, 11, 9)) == "2026-11-15"
    assert default_next(old, date(2026, 11, 16)) == "2026-11-22"
    assert old.next == ""


def test_current_month_and_current_season_close_get_a_weekly_review():
    today = date(2026, 11, 9)
    for cutoff in ("2026-11", "2026-fall", "Fall 2026", "2026-11-30"):
        app = record(deadline=normalize_deadline(cutoff))
        assert next_value(app, today) == "2026-11-15"


def test_weekly_default_never_exceeds_earlier_application_deadline():
    today = date(2026, 11, 9)
    assert default_next(record(deadline="2026-11-13"), today) == "2026-11-13"
    assert default_next(record(deadline="2026-11-09"), today) == "2026-11-09"
    assert default_next(record(deadline="2026-12-01"), today) == "2026-12-01"
    assert default_next(record(deadline="2026-winter"), today) == "2026-12-06"


def test_recruitment_opening_timing_without_closing_date_reviews_weekly():
    today = date(2026, 11, 9)
    assert default_next(record(when="2026-09", deadline=""), today) == "2026-11-15"
    assert default_next(record(when="2026-12", deadline=""), today) == "2026-12-06"


def test_stage_actions_default_to_week_end_not_original_application_cutoff():
    today = date(2026, 11, 9)
    for action in ("Take", "Go", "Respond", "Email"):
        app = record(action=action, deadline="2026-11-13")
        assert default_next(app, today) == "2026-11-15"
        assert app.deadline == "2026-11-13"


def test_wait_uses_original_application_cutoff_as_next_until_user_overrides():
    today = date(2026, 11, 9)
    app = record(action="Wait", deadline="2026-12-31 23:59")
    assert default_next(app, today) == "2026-12-31 23:59"
    assert next_value(app, today) == "2026-12-31 23:59"
    app.next = "2026-11-15"
    assert next_value(app, today) == "2026-11-15"
    assert app.deadline == "2026-12-31 23:59"


def test_wait_after_application_cutoff_requires_review_not_archive():
    from career_job_manager.model import effective_queue_date

    today = date(2027, 1, 4)
    wait = record("wait", action="Wait", deadline="2026-12-31")
    fresh = record("fresh", action="Check", deadline="2027-spring")
    assert default_next(wait, today) == "2026-12-31"
    assert wait.action == "Wait"
    assert effective_queue_date(wait, today) == date(2027, 1, 5)
    assert [r.id for r in sort_records([fresh, wait], today=today)] == ["wait", "fresh"]


def test_wait_vague_future_and_current_deadlines_follow_period_checkpoints():
    assert default_next(
        record(action="Wait", deadline="2027-spring"), date(2026, 11, 9),
    ) == "2027-03-07"
    assert default_next(
        record(action="Wait", deadline="2027-spring"), date(2027, 3, 10),
    ) == "2027-03-14"
    assert default_next(
        record(action="Wait", deadline=""), date(2026, 11, 9),
    ) == "2026-11-15"


def test_asap_only_for_next_and_sorting_uses_next_date():
    today = date(2026, 11, 9)
    asap = record("asap", next="ASAP")
    dated = record("dated", next="2026-11-10", deadline="2026-11-30")
    auto = record("auto", deadline="2026-11-30")
    expired = record("expired", deadline="2026-09-01")
    archive = record("archive", action="Archive", next="ASAP")
    assert [r.id for r in sort_records(
        [archive, expired, auto, dated, asap], today=today,
    )] == ["asap", "dated", "auto", "expired", "archive"]
    assert normalize_next("aSaP") == "ASAP"
    with pytest.raises(ValueError, match="Deadline cannot be ASAP"):
        normalize_deadline("ASAP")


def test_legacy_asap_migrates_to_next_without_relabeling_other_dates():
    old = ApplicationRecord.from_dict({
        "id": "jpm", "company": "JPMAM", "job": "Research",
        "action": "Wait", "deadline": "ASAP", "when": "2026-fall",
    })
    assert old.deadline == ""
    assert old.next == "ASAP"
    old2 = ApplicationRecord.from_dict({
        "id": "hsbc", "company": "HSBC", "job": "Investment",
        "action": "Take", "deadline": "2026-11-15", "when": "2026-fall",
    })
    assert old2.deadline == "2026-11-15"
    assert old2.next == ""


def test_import_retains_explicit_next_and_does_not_mutate_deadline_on_action_change(tmp_path):
    store = CareerStore(tmp_path / "career")
    payload = {"schema_version": 1, "jobs": [{
        "id": "hsbc-2027", "company": "HSBC", "role": "Investment Specialist",
        "when": "2026-fall", "deadline": "2026-11-13",
    }]}
    store.import_jobs(payload)
    old = next(r for r in store.list() if r.import_id == "hsbc-2027")
    assert old.next == ""
    changed = store.update(old.id, {"action": "Take", "next": "ASAP"})
    assert changed.deadline == "2026-11-13"
    assert changed.next == "ASAP"
    store.import_jobs(payload)
    reloaded = store.get(old.id)
    assert reloaded.action == "Take"
    assert reloaded.next == "ASAP"
    assert reloaded.deadline == "2026-11-13"


def test_manual_edit_can_clear_next_to_restore_auto_weekly_default(tmp_path):
    store = CareerStore(tmp_path / "career")
    store.add(record("manual", deadline="2026-fall", next="ASAP"))
    updated = store.update("manual", {"next": ""})
    assert updated.next == ""
    assert default_next(updated, date(2026, 11, 9)) == "2026-11-15"


@pytest.mark.parametrize(("period", "today", "expected"), [
    ("2027-spring", date(2026, 11, 9), "2027-03-07"),
    ("2027-spring", date(2027, 3, 1), "2027-03-07"),
    ("2027-spring", date(2027, 3, 10), "2027-03-14"),
    ("2027-spring", date(2027, 3, 17), "2027-03-21"),
    ("2027-spring", date(2027, 5, 30), "2027-05-30"),
    ("2027-10", date(2026, 11, 9), "2027-10-03"),
    ("2027-10", date(2027, 10, 5), "2027-10-10"),
    ("2027-10..2027-12", date(2026, 11, 9), "2027-10-03"),
    ("2026-winter", date(2026, 11, 9), "2026-12-06"),
    ("2026-winter", date(2027, 1, 11), "2027-01-17"),
])
def test_future_and_active_vague_deadline_uses_correct_week_end(period, today, expected):
    app = record(deadline=period)
    assert default_next(app, today) == expected
    assert app.deadline == period  # A generated Next never rewrites Deadline.
    assert app.next == ""


@pytest.mark.parametrize(("opening", "today", "expected"), [
    ("2027-spring", date(2026, 11, 9), "2027-03-07"),
    ("2027-spring", date(2027, 3, 10), "2027-03-14"),
    ("2027-10", date(2026, 11, 9), "2027-10-03"),
    ("2027-10..2027-12", date(2026, 11, 9), "2027-10-03"),
    ("2027-03-01", date(2026, 11, 9), "2027-03-01"),
])
def test_future_vague_recruitment_opening_uses_first_sunday_but_exact_is_unchanged(
    opening, today, expected,
):
    app = record(deadline="", when=opening)
    assert default_next(app, today) == expected
    assert app.next == ""


def test_manually_set_next_never_rolls_with_future_vague_deadline():
    app = record(deadline="2027-spring", next="2027-04-12")
    assert next_value(app, date(2026, 11, 9)) == "2027-04-12"
    assert next_value(app, date(2027, 3, 17)) == "2027-04-12"
