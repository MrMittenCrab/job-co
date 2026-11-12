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
    for cutoff in ("2026-11", "2026-fall", "Fall 2026"):
        app = record(deadline=normalize_deadline(cutoff))
        assert next_value(app, today) == "2026-11-15"
    assert next_value(record(deadline="2026-11-30"), today) == "2026-11-30"


def test_weekly_default_never_exceeds_earlier_application_deadline():
    today = date(2026, 11, 9)
    assert default_next(record(deadline="2026-11-13"), today) == "2026-11-13"
    assert default_next(record(deadline="2026-11-09"), today) == "2026-11-09"
    assert default_next(record(deadline="2026-12-01"), today) == "2026-12-01"
    assert default_next(record(deadline="2026-winter"), today) == "2026-12-06"


def test_recruitment_opening_timing_without_closing_date_reviews_weekly():
    today = date(2026, 11, 9)
    assert default_next(record(when="2026-09", deadline=""), today) == "2026-09-06"
    assert default_next(record(when="2026-12", deadline=""), today) == "2026-12-06"


def test_stage_actions_follow_original_exact_deadline_unless_next_overridden():
    today = date(2026, 11, 9)
    for action in ("Apply", "Check", "Wait", "Take", "Go", "Respond", "Email"):
        app = record(action=action, deadline="2026-11-13")
        assert default_next(app, today) == "2026-11-13"
        assert app.deadline == "2026-11-13"
        app.next = "ASAP"
        assert next_value(app, today) == "ASAP"


def test_wait_uses_original_application_cutoff_as_next_until_user_overrides():
    today = date(2026, 11, 9)
    app = record(action="Wait", deadline="2026-12-31 23:59")
    assert default_next(app, today) == "2026-12-31 23:59"
    assert next_value(app, today) == "2026-12-31 23:59"
    app.next = "2026-11-15"
    assert next_value(app, today) == "2026-11-15"
    assert app.deadline == "2026-12-31 23:59"


def test_wait_after_application_cutoff_becomes_auto_asap_not_archive():
    from career_job_manager.model import effective_queue_date, today_position

    today = date(2027, 1, 4)
    wait = record("wait", action="Wait", deadline="2026-12-31")
    fresh = record("fresh", action="Check", deadline="2027-spring")
    assert default_next(wait, today) == "ASAP"
    assert next_value(wait, today) == "ASAP"
    assert wait.action == "Wait"
    assert wait.next == ""  # Automatic Next is never persisted into manual Next.
    assert wait.deadline == "2026-12-31"
    assert effective_queue_date(wait, today) == today
    ordered = sort_records([fresh, wait], today=today)
    assert [r.id for r in ordered] == ["wait", "fresh"]
    assert today_position(ordered, today=today) == 0


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
    )] == ["expired", "asap", "dated", "auto", "archive"]
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


@pytest.mark.parametrize(("cutoff", "today", "expected"), [
    ("2026-09", date(2026, 11, 9), "2026-09-06"),
    ("2026-fall", date(2027, 3, 10), "2026-09-06"),
    ("2026-10..2026-11", date(2027, 1, 4), "2026-10-04"),
    ("2027-spring", date(2026, 11, 9), "2027-03-07"),
    ("2027-spring", date(2027, 3, 10), "2027-03-14"),
])
def test_vague_period_always_resolves_to_specific_calendar_date(cutoff, today, expected):
    for action in ("Apply", "Wait", "Take", "Check"):
        app = record(action=action, deadline=cutoff)
        assert next_value(app, today) == ("ASAP" if action == "Wait" and today > date(2026, 11, 30) and cutoff.startswith("2026-") else expected)
        assert app.next == ""
        assert app.deadline == cutoff


def test_strict_chronological_sort_and_today_position():
    from career_job_manager.model import today_position, effective_queue_date
    today = date(2026, 11, 9)
    records = [
        record("future", action="Wait", deadline="2026-12-31"),
        record("old", action="Wait", deadline="2026-09-01"),
        record("yesterday", action="Apply", deadline="2026-11-08"),
        record("asap", action="Take", next="ASAP", deadline="2026-10-01"),
        record("today", action="Apply", deadline="2026-11-09"),
        record("tomorrow", action="Check", deadline="2026-11-10"),
        record("archive", action="Archive", next="ASAP"),
    ]
    result = sort_records(records, today=today)
    assert [r.id for r in result] == [
        "yesterday", "asap", "old", "today", "tomorrow", "future", "archive",
    ]
    assert today_position(result, today=today) == 1
    assert effective_queue_date(result[2], today) == today
    assert today_position(result[:1], today=today) == 0


def test_past_vague_opening_period_never_remains_unclear():
    today = date(2026, 11, 9)
    assert default_next(record(when="2026-09", deadline=""), today) == "2026-09-06"
    assert default_next(record(when="2026-fall", deadline=""), today) == "2026-11-15"
    assert default_next(record(when="2026-01-01", deadline=""), today) == "2026-11-15"



@pytest.mark.parametrize(("cutoff", "today", "expected"), [
    ("2026-11-09", date(2026, 11, 9), "2026-11-09"),
    ("2026-11-09", date(2026, 11, 10), "ASAP"),
    ("2026-11-09 18:00", date(2026, 11, 9), "2026-11-09 18:00"),
    ("2026-11-09 18:00", date(2026, 11, 10), "ASAP"),
    ("2026-11", date(2026, 11, 12), "2026-11-15"),
    ("2026-11", date(2026, 11, 30), "2026-11-30"),
    ("2026-11", date(2026, 12, 1), "ASAP"),
    ("2026-fall", date(2026, 11, 12), "2026-11-15"),
    ("2026-fall", date(2026, 11, 30), "2026-11-30"),
    ("2026-fall", date(2026, 12, 1), "ASAP"),
    ("2026-10..2026-11", date(2026, 11, 12), "2026-11-15"),
    ("2026-10..2026-11", date(2026, 12, 1), "ASAP"),
    ("2026-12", date(2026, 11, 12), "2026-12-06"),
])
def test_wait_asap_only_when_confirmed_application_deadline_has_expired(cutoff, today, expected):
    wait = record(action="Wait", deadline=cutoff)
    assert default_next(wait, today) == expected
    assert next_value(wait, today) == expected
    assert wait.deadline == cutoff
    assert wait.next == ""


def test_wait_without_confirmed_deadline_does_not_infer_expiration_from_opening():
    today = date(2026, 11, 12)
    assert default_next(record(action="Wait", deadline="", when="2026-09"), today) == "2026-09-06"
    assert default_next(record(action="Wait", deadline="unknown", when="2026-09"), today) == "2026-11-15"
    assert default_next(record(action="Wait", deadline="", when="2026-fall"), today) == "2026-11-15"


def test_manual_next_overrides_expired_wait_and_other_actions_never_auto_asap():
    today = date(2026, 11, 12)
    for manual in ("2026-11-19", "ASAP", "2026-10-01"):
        wait = record(action="Wait", deadline="2026-10-01", next=manual)
        assert default_next(wait, today) == "ASAP"
        assert next_value(wait, today) == manual
        assert wait.deadline == "2026-10-01"
    for action in ("Apply", "Take", "Go", "Email", "Respond", "Check"):
        other = record(action=action, deadline="2026-10-01")
        assert default_next(other, today) == "2026-10-01"
