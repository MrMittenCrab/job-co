"""Weekly read-only export uses effective Next and keeps full export available."""
from datetime import date
import json

from career_job_manager.model import ApplicationRecord
from career_job_manager.weekly import weekly_agenda
from career_job_manager.store import CareerStore
from career_job_manager import cli


def record(id, *, action="Apply", next="", deadline="", when="2026-fall"):
    return ApplicationRecord(
        id=id, company=f"Company {id}", job="Research",
        action=action, next=next, deadline=deadline, when=when,
        portal=f"https://example.org/{id}", brief=f"Note {id}",
    )


def test_this_week_end_includes_asap_overdue_manual_and_sunday():
    today = date(2026, 11, 9)
    records = [
        record("asap", next="ASAP", action="Take"),
        record("overdue", next="2026-11-02", action="Email"),
        record("sun", next="2026-11-15 23:59", action="Take"),
        record("mon", next="2026-11-16", action="Apply"),
        record("future", deadline="2027-spring", action="Check"),
        record("vague", deadline="2026-fall", action="Check"),
        record("close", deadline="2026-11-13", action="Apply"),
        record("expired", deadline="2026-10-01", action="Apply"),
        record("archived", next="ASAP", action="Archive"),
        record("wait", action="Wait"),
    ]
    result = weekly_agenda(records, today=today)
    assert result["as_of"] == "2026-11-09"
    assert result["week_ending"] == "2026-11-15"
    assert result["format"] == "jobco-weekly-agenda"
    ids = [r["id"] for r in result["items"]]
    assert ids == ["overdue", "asap", "close", "wait", "vague", "sun"]
    assert "expired" not in ids
    assert "archived" not in ids


def test_export_marks_generated_next_and_does_not_change_stored_deadline():
    source = record("spring", deadline="2027-spring", next="", when="2026-fall")
    result = weekly_agenda([source], today=date(2027, 3, 10))
    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["deadline"] == "2027-spring"
    assert row["next"] == "2027-03-14"
    assert row["next_source"] == "automatic"
    assert row["portal"] == "https://example.org/spring"
    assert source.next == ""
    assert source.deadline == "2027-spring"


def test_asap_only_next_and_manual_overdue_reminders_are_preserved():
    result = weekly_agenda(
        [record("old", action="Wait", next="2026-11-03"),
         record("old-auto", action="Apply", deadline="2026-10-31")],
        today=date(2026, 11, 9),
    )
    assert [item["id"] for item in result["items"]] == ["old"]


def test_export_cli_two_word_alias_and_custom_destination(tmp_path, monkeypatch):
    store = CareerStore(tmp_path / "career")
    store.add(record("asap", action="Take", next="ASAP"))
    store.add(record("future", action="Apply", next="2028-01-01"))
    monkeypatch.setattr(cli, "CareerStore", lambda: store)

    path = tmp_path / "weekly.json"
    cli.main(["export", "this", "week", "--output", str(path)])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "jobco-weekly-agenda"
    assert [r["id"] for r in data["items"]] == ["asap"]


def test_export_cli_hyphen_alias_and_existing_full_export(tmp_path, monkeypatch):
    store = CareerStore(tmp_path / "career")
    store.add(record("asap", action="Take", next="ASAP"))
    monkeypatch.setattr(cli, "CareerStore", lambda: store)

    weekly = tmp_path / "this-week.json"
    cli.main(["export", "this-week", "--output", str(weekly)])
    data = json.loads(weekly.read_text(encoding="utf-8"))
    assert data["format"] == "jobco-weekly-agenda"

    full = tmp_path / "all.json"
    cli.main(["export", str(full)])
    snapshot = json.loads(full.read_text(encoding="utf-8"))
    assert "jobs" in snapshot
    assert "companies" in snapshot
    assert len(snapshot["jobs"]) == 1
    assert "items" not in snapshot


def test_wait_after_closing_is_included_for_review_but_unsubmitted_expired_is_not():
    today = date(2027, 1, 4)
    agenda = weekly_agenda([
        record("waiting", action="Wait", deadline="2026-12-31"),
        record("unsubmitted", action="Apply", deadline="2026-12-31"),
        record("future-wait", action="Wait", deadline="2027-02-01"),
        record("manually-follow-up", action="Wait", next="ASAP",
               deadline="2027-02-01"),
    ], today=today)
    ids = [entry["id"] for entry in agenda["items"]]
    assert ids == ["manually-follow-up", "waiting"]
    waiting = next(entry for entry in agenda["items"] if entry["id"] == "waiting")
    assert waiting["action"] == "Wait"
    assert waiting["next"] == "ASAP"
    assert waiting["deadline"] == "2026-12-31"
    assert waiting["next_source"] == "automatic"
