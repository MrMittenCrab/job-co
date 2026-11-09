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
    assert default_next(record(deadline="2026-winter"), today) == "2026-12-01"


def test_recruitment_opening_timing_without_closing_date_reviews_weekly():
    today = date(2026, 11, 9)
    assert default_next(record(when="2026-09", deadline=""), today) == "2026-11-15"
    assert default_next(record(when="2026-12", deadline=""), today) == "2026-12-01"


def test_stage_actions_default_to_week_end_not_original_application_cutoff():
    today = date(2026, 11, 9)
    for action in ("Wait", "Take", "Go", "Respond", "Email"):
        app = record(action=action, deadline="2026-11-13")
        assert default_next(app, today) == "2026-11-15"
        assert app.deadline == "2026-11-13"


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
