from datetime import date, datetime

import pytest

from career_job_manager.model import (
    ApplicationRecord,
    ACTIONS,
    action_uses_target,
    display_deadline,
    filter_records,
    normalize_deadline,
    sort_records,
)


def make_record(**overrides):
    data = {
        "id": "1",
        "company": "HSBC",
        "job": "Global Banking Graduate",
        "deadline": "",
        "action": "Apply",
        "target": "https://example.com/apply",
        "portal": "",
        "contact": "",
        "brochure": "",
        "form": "",
        "resume": "",
        "letter": "",
    }
    data.update(overrides)
    return ApplicationRecord(**data)


def test_required_fields_reject_blank_company_and_job():
    with pytest.raises(ValueError, match="Company"):
        make_record(company="   ").validate()
    with pytest.raises(ValueError, match="Program"):
        make_record(job="").validate()


def test_action_is_selected_and_validated():
    for action in ACTIONS:
        record = make_record(action=action)
        record.validate()
        assert record.action == action
    with pytest.raises(ValueError, match="Action"):
        make_record(action="Unknown").validate()


def test_target_visibility_depends_on_selected_action():
    for action in ("Apply", "Take", "Go", "Respond", "Email"):
        assert action_uses_target(action)
    for action in ("Wait", "Archive"):
        record = make_record(action=action, target="stale URL")
        record.validate()
        assert record.target == ""
        assert not action_uses_target(action)


def test_old_apply_field_migrates_to_optional_portal_and_action_rederives():
    record = ApplicationRecord.from_dict({
        "id": "legacy",
        "company": "HSBC",
        "job": "Analyst",
        "status": "Interview",
        "deadline": "",
        "action": "Attend",
        "apply": "https://old.example/portal",
        "contact": "",
        "brochure": "",
        "resume": "",
        "letter": "",
    })
    record.validate()
    assert record.portal == "https://old.example/portal"
    assert record.action == "Go"
    assert record.form == ""
    assert "apply" not in record.to_dict()


def test_deadline_normalization_accepts_date_and_datetime():
    assert normalize_deadline("2026-09-18") == "2026-09-18"
    assert normalize_deadline(" 2026-09-18 23:59 ") == "2026-09-18 23:59"
    assert normalize_deadline("") == ""
    assert normalize_deadline("Sep 18") == f"{datetime.now().year}-09-18"


def test_deadline_display_is_compact():
    assert display_deadline("2026-09-18") == "18 Sep"
    assert display_deadline("2026-09-18 23:59") == "18 Sep 23:59"
    assert display_deadline("") == "—"


def test_sort_records_uses_deadline_and_season_for_undated():
    records = [
        make_record(id="c", company="Cathay", deadline="", when="2026-fall"),
        make_record(id="b", company="HSBC", deadline="2026-09-20 18:00"),
        make_record(id="a", company="P&G", deadline="2026-09-18 23:59"),
    ]
    assert [record.id for record in sort_records(records)] == ["a", "b", "c"]


@pytest.mark.parametrize("action", ["Apply", "Wait", "Take", "Go", "Respond", "Email"])
@pytest.mark.parametrize("timing", [
    {"deadline": "2027-10-01"},
    {"when": "2027-fall"},
])
@pytest.mark.parametrize("query", ["", "HSBC"])
def test_active_actions_precede_check_regardless_of_time(action, timing, query):
    records = [
        make_record(id="check", action="Check", deadline="2026-01-01"),
        make_record(id="active", action=action, **timing),
        make_record(id="archive", action="Archive", deadline="2025-01-01"),
    ]
    assert [record.id for record in filter_records(records, query)] == [
        "archive", "active", "check",
    ]


@pytest.mark.parametrize("action", ["Apply", "Check", "Archive"])
def test_action_groups_preserve_exact_then_fuzzy_time_order(action):
    records = [
        make_record(id="fuzzy", action=action, when="2026-01"),
        make_record(id="late", action=action, deadline="2026-10-01"),
        make_record(id="early", action=action, deadline="2026-09-01"),
    ]
    assert [record.id for record in sort_records(records)] == ["early", "late", "fuzzy"]


def test_filter_records_searches_company_job_action_contact_and_keeps_order():
    records = [
        make_record(id="2", company="HSBC", deadline="2026-09-20", contact="Jane Smith"),
        make_record(
            id="1",
            company="BCG",
            job="Associate Analyst",
            action="Go",
            deadline="2026-09-18",
            brochure="BCG_Associate-Analyst_Brochure.pdf",
        ),
    ]
    assert [r.id for r in filter_records(records, "hsbc")] == ["2"]
    assert [r.id for r in filter_records(records, "analyst")] == ["1"]
    assert [r.id for r in filter_records(records, "GO")] == ["1"]
    assert [r.id for r in filter_records(records, "jane")] == ["2"]
    assert filter_records(records, "description") == []
    assert [r.id for r in filter_records(records, "")] == ["1", "2"]


def test_deadline_accepts_human_month_day_with_current_year(monkeypatch):
    from career_job_manager import model

    class FixedDateTime(model.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 17, 12, 0)

    monkeypatch.setattr(model, "datetime", FixedDateTime)
    assert model.normalize_deadline("Sep 25") == "2026-09-25"
    assert model.normalize_deadline("25 Sep") == "2026-09-25"
    assert model.normalize_deadline("Sep 25 14:00") == "2026-09-25 14:00"
    assert model.normalize_deadline("Sep 25 2pm") == "2026-09-25 14:00"


def test_deadline_tolerates_commas_and_odd_spacing(monkeypatch):
    from career_job_manager import model

    class FixedDateTime(model.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 17, 12, 0)

    monkeypatch.setattr(model, "datetime", FixedDateTime)
    assert model.normalize_deadline("  Sep   25 ,   2 pm ") == "2026-09-25 14:00"
    assert model.normalize_deadline("Sep 25, 2:30pm") == "2026-09-25 14:30"
    assert model.normalize_deadline("Sep, 25") == "2026-09-25"
    assert model.normalize_deadline("25,   Sep,  2027  ,  9:05 am") == "2027-09-25 09:05"


def test_deadline_keeps_iso_inputs_working():
    assert normalize_deadline("2027-01-15") == "2027-01-15"
    assert normalize_deadline("2027-01-15 08:30") == "2027-01-15 08:30"


def test_description_text_is_independent_from_description_file():
    record = make_record(
        brochure="HSBC_Global-Banking-Graduate_Brochure.pdf",
        description_text="  Full pasted job description.  ",
    )
    record.validate()
    assert record.brochure == "HSBC_Global-Banking-Graduate_Brochure.pdf"
    assert record.description_text == "Full pasted job description."


def test_legacy_records_default_description_text_to_empty():
    record = ApplicationRecord.from_dict({
        "id": "legacy-desc",
        "company": "HSBC",
        "job": "Analyst",
        "deadline": "",
        "action": "Wait",
        "target": "",
        "portal": "",
        "contact": "",
        "description": "HSBC_Analyst_Brochure.pdf",
        "form": "",
        "resume": "",
        "letter": "",
    })
    assert record.description_text == ""


def test_wait_expired_deadline_is_ordered_after_today_without_editing_deadline():
    today = date(2026, 10, 27)
    records = [
        make_record(id="old", company="A", action="Apply", deadline="2026-10-20"),
        make_record(id="wait", company="B", action="Wait", deadline="2026-09-01"),
        make_record(id="next", company="C", action="Apply", deadline="2026-10-29"),
        make_record(id="future-wait", company="D", action="Wait", deadline="2026-12-01"),
    ]
    assert [r.id for r in sort_records(records, today=today)] == [
        "next", "old", "wait", "future-wait",
    ]
    assert records[1].deadline == "2026-09-01"
    records[1].action = "Apply"
    assert [r.id for r in sort_records(records, today=today)] == [
        "next", "wait", "old", "future-wait",
    ]


def test_wait_approximate_past_timing_is_pinned_after_today():
    today = date(2026, 10, 27)
    records = [
        make_record(id="old", company="A", when="2026-09", action="Apply"),
        make_record(id="wait", company="B", when="2026-09", action="Wait"),
        make_record(id="future", company="C", when="2026-11", action="Apply"),
    ]
    assert [r.id for r in sort_records(records, today=today)] == [
        "old", "wait", "future",
    ]
    assert records[1].when == "2026-09"


def test_weekly_application_deadlines_precede_existing_action_groups():
    today = date(2026, 11, 9)
    records = [
        make_record(id="far-apply", action="Apply", deadline="2026-12-01"),
        make_record(id="urgent-check", action="Check", deadline="2026-11-11"),
        make_record(id="urgent-apply", action="Apply", deadline="2026-11-14"),
        make_record(id="later-check", action="Check", deadline="2026-12-02"),
        make_record(id="nonapplication", action="Take", deadline="2026-11-10"),
        make_record(id="overdue-check", action="Check", deadline="2026-11-08"),
        make_record(id="no-deadline-check", action="Check", when="2026-11"),
    ]
    assert [r.id for r in sort_records(records, today=today)] == [
        "urgent-check", "urgent-apply", "nonapplication", "far-apply",
        "overdue-check", "later-check", "no-deadline-check",
    ]


def test_weekly_window_is_inclusive_and_requires_actual_deadline():
    today = date(2026, 11, 9)
    from career_job_manager.model import application_due_this_week
    assert application_due_this_week(make_record(action="Check", deadline="2026-11-09"), today)
    assert application_due_this_week(make_record(action="Apply", deadline="2026-11-16"), today)
    assert not application_due_this_week(make_record(action="Apply", deadline="2026-11-17"), today)
    assert not application_due_this_week(make_record(action="Apply", deadline="2026-11-08"), today)
    assert not application_due_this_week(make_record(action="Check", when="2026-11"), today)
    assert not application_due_this_week(make_record(action="Wait", deadline="2026-11-11"), today)
    assert not application_due_this_week(make_record(action="Archive", deadline="2026-11-11"), today)
