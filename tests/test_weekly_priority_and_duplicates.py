"""Explicit weekly scheduling, tie ordering, and safe duplicate detection."""
from datetime import date
import json

import pytest

from career_job_manager import cli
from career_job_manager.duplicates import find_duplicates
from career_job_manager.model import ApplicationRecord, default_next, next_value, sort_records
from career_job_manager.store import CareerStore


TODAY = date(2026, 11, 18)
SUNDAY = "2026-11-22"


def app(identifier, action, deadline="", next="", company="Verition"):
    return ApplicationRecord(
        id=identifier, company=company, job="2027 Investment Internship",
        action=action, deadline=deadline, next=next, when="2026-fall",
    )


@pytest.mark.parametrize("action", ["Take", "Apply", "Wait"])
@pytest.mark.parametrize(("deadline", "expected"), [
    ("", SUNDAY),
    ("2027-02-01", SUNDAY),
    ("2026-11-20", "2026-11-20"),
    ("2026-11-22 17:00", "2026-11-22 17:00"),
    ("2026-11-15", "2026-11-15"),
    ("2026-10", "2026-10-31"),
    ("2027-spring", SUNDAY),
])
def test_weekly_actions_use_minimum_of_sunday_and_deadline(action, deadline, expected):
    record = app(action.casefold(), action, deadline=deadline, next="2028-01-01")
    assert next_value(record, TODAY) == expected
    assert default_next(record, TODAY) == expected
    assert record.deadline == deadline
    assert record.next == "2028-01-01"


def test_manual_asap_does_not_override_weekly_schedule():
    for action in ("Take", "Apply", "Wait"):
        assert next_value(app(action, action, next="ASAP"), TODAY) == SUNDAY


def test_same_next_orders_take_before_apply_before_wait():
    items = [
        app("wait", "Wait"), app("apply", "Apply"), app("take", "Take"),
        app("check", "Check", next=SUNDAY),
    ]
    ordered = sort_records(items, today=TODAY)
    assert [r.id for r in ordered] == ["take", "apply", "wait", "check"]


def test_earlier_deadline_precedes_action_precedence():
    items = [app("take", "Take"), app("wait", "Wait", deadline="2026-11-19")]
    assert [r.id for r in sort_records(items, today=TODAY)] == ["wait", "take"]


def test_duplicate_report_finds_verition_with_alternate_name_and_id():
    first = app("manual", "Wait", company="Verition")
    second = ApplicationRecord(
        id="imported", import_id="verition-2027-investment-internship-apac-hk-5264435007",
        company="Verition Fund Management",
        job="2027 Investment Internship (APAC) — Hong Kong", action="Check",
        when="2026-10-14",
        portal="https://job-boards.greenhouse.io/veritiongroupllcinternships/jobs/5264435007",
    )
    matches = find_duplicates([first, second])
    assert len(matches) == 1
    assert matches[0].reason == "same employer and programme; different IDs"


def test_import_blocks_semantic_duplicate_without_changing_applications(tmp_path):
    store = CareerStore(tmp_path / "data")
    manual = app("manual", "Wait", company="Verition")
    manual.contact = "Existing recruiter"
    store.add(manual)
    before = store.export_data()
    incoming = {"schema_version": 1, "jobs": [{
        "id": "verition-2027-investment-internship-apac-hk-5264435007",
        "company": "Verition Fund Management",
        "role": "2027 Investment Internship (APAC) — Hong Kong",
        "when": "2026-10-14",
        "url": "https://job-boards.greenhouse.io/veritiongroupllcinternships/jobs/5264435007",
    }]}
    with pytest.raises(ValueError, match="Potential duplicate"):
        store.import_jobs(incoming)
    assert store.export_data() == before
    assert store.get("manual").action == "Wait"
    assert store.get("manual").contact == "Existing recruiter"


def test_import_same_id_is_safe_update(tmp_path):
    store = CareerStore(tmp_path / "data")
    incoming = {"schema_version": 1, "jobs": [{
        "id": "verition-2027", "company": "Verition Fund Management",
        "role": "2027 Investment Internship (APAC) — Hong Kong",
        "when": "2026-10-14",
    }]}
    assert store.import_jobs(incoming).jobs == (1, 0)
    assert store.import_jobs(incoming).jobs == (0, 0)
    assert len(store.list()) == 1


def test_distinct_intake_years_can_coexist(tmp_path):
    store = CareerStore(tmp_path / "data")
    incoming = {"schema_version": 1, "jobs": [
        {"id": "verition-2027", "company": "Verition",
         "role": "2027 Investment Internship", "when": "2026-10"},
        {"id": "verition-2028", "company": "Verition Fund Management",
         "role": "2028 Investment Internship", "when": "2027-10"},
    ]}
    assert store.import_jobs(incoming).jobs == (2, 0)


def test_distinct_cities_are_not_automatically_treated_as_duplicate():
    first = ApplicationRecord(
        id="hk", company="Verition Fund Management",
        job="2027 Investment Internship — Hong Kong", when="2026-10",
    )
    second = ApplicationRecord(
        id="sg", company="Verition", job="2027 Investment Internship — Singapore",
        when="2026-10",
    )
    assert find_duplicates([first, second]) == []


def test_shared_campus_recruitment_portal_is_not_a_duplicate_vacancy():
    event = ApplicationRecord(
        id="pwc-event", company="PwC", job="Campus Event", action="Archive",
        deadline="2026-09-28",
        portal="https://app.mokahr.com/m/campus-recruitment/pwc/148260?locale=en-US#/events?page=1",
    )
    programme = ApplicationRecord(
        id="pwc-graduate", company="PwC", job="Graduate Program 2027", action="Archive",
        deadline="2026-09-28",
        portal="https://app.mokahr.com/m/campus-recruitment/pwc/148260#/jobs?location=Hongkong",
    )
    assert find_duplicates([event, programme]) == []


def test_identical_greenhouse_vacancy_with_tracking_query_is_duplicate():
    original = ApplicationRecord(
        id="verition-a", company="Verition",
        job="Investment Internship APAC 2027",
        portal="https://job-boards.greenhouse.io/veritiongroupllcinternships/jobs/5264435007",
    )
    tracked = ApplicationRecord(
        id="verition-b", company="Verition Fund Management",
        job="2027 Investment Internship (APAC) — Hong Kong",
        portal="https://job-boards.greenhouse.io/veritiongroupllcinternships/jobs/5264435007?gh_src=Trackr",
    )
    matches = find_duplicates([original, tracked])
    assert len(matches) == 1
    assert matches[0].reason == "identical vacancy application URL"


def test_read_only_duplicates_command_preserves_records(tmp_path, monkeypatch, capsys):
    store = CareerStore(tmp_path / "data")
    store.add(app("manual", "Wait"))
    store.add(app("other", "Check", company="Verition Fund Management"))
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    before = json.dumps(store.export_data(), sort_keys=True)
    cli.main(["duplicates"])
    stdout = capsys.readouterr().out
    assert "Found 1 possible duplicate" in stdout
    assert "manual" in stdout and "other" in stdout
    assert json.dumps(store.export_data(), sort_keys=True) == before
