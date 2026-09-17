from datetime import datetime

import pytest

from career_job_manager.model import (
    ApplicationRecord,
    DEFAULT_ACTIONS,
    STATUSES,
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
        "status": "Application",
        "deadline": "",
        "action": "Apply",
        "apply": "",
        "contact": "",
        "description": "",
        "resume": "",
        "letter": "",
    }
    data.update(overrides)
    return ApplicationRecord(**data)


def test_required_fields_reject_blank_company_and_job():
    with pytest.raises(ValueError, match="Company"):
        make_record(company="   ").validate()
    with pytest.raises(ValueError, match="Job"):
        make_record(job="").validate()


def test_status_is_fixed():
    assert STATUSES == (
        "Application",
        "Applied",
        "Assessment",
        "Interview",
        "Offer",
        "Closed",
    )
    with pytest.raises(ValueError, match="Status"):
        make_record(status="Phone Screen").validate()


def test_default_actions_match_target():
    assert DEFAULT_ACTIONS["Application"] == "Apply"
    assert DEFAULT_ACTIONS["Applied"] == "Wait"
    assert DEFAULT_ACTIONS["Assessment"] == "Complete"
    assert DEFAULT_ACTIONS["Interview"] == "Attend"
    assert DEFAULT_ACTIONS["Offer"] == "Respond"
    assert DEFAULT_ACTIONS["Closed"] == "None"


def test_deadline_normalization_accepts_date_and_datetime():
    assert normalize_deadline("2026-09-18") == "2026-09-18"
    assert normalize_deadline(" 2026-09-18 23:59 ") == "2026-09-18 23:59"
    assert normalize_deadline("") == ""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        normalize_deadline("Sep 18")


def test_deadline_display_is_compact():
    assert display_deadline("2026-09-18") == "Sep 18"
    assert display_deadline("2026-09-18 23:59") == "Sep 18 23:59"
    assert display_deadline("") == "—"


def test_sort_records_uses_deadline_and_puts_undated_last():
    records = [
        make_record(id="c", company="Cathay", deadline=""),
        make_record(id="b", company="HSBC", deadline="2026-09-20 18:00"),
        make_record(id="a", company="P&G", deadline="2026-09-18 23:59"),
    ]
    assert [record.id for record in sort_records(records)] == ["a", "b", "c"]


def test_filter_records_searches_only_company_job_status_contact_and_keeps_order():
    records = [
        make_record(id="2", company="HSBC", deadline="2026-09-20", contact="Jane Smith"),
        make_record(
            id="1",
            company="BCG",
            job="Associate Analyst",
            status="Interview",
            deadline="2026-09-18",
            description="HSBC appears only in description",
        ),
    ]
    assert [r.id for r in filter_records(records, "hsbc")] == ["2"]
    assert [r.id for r in filter_records(records, "analyst")] == ["1"]
    assert [r.id for r in filter_records(records, "INTERVIEW")] == ["1"]
    assert [r.id for r in filter_records(records, "jane")] == ["2"]
    assert filter_records(records, "description") == []
    assert [r.id for r in filter_records(records, "")] == ["1", "2"]
