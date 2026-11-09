"""An AI-authored shortlist changes only existing Check actions."""
import json

import pytest

from career_job_manager import cli
from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore


def setup_store(tmp_path):
    store = CareerStore(tmp_path / "career")
    for id, action in (
        ("check", "Check"),
        ("apply", "Apply"),
        ("wait", "Wait"),
        ("take", "Take"),
        ("archive", "Archive"),
    ):
        store.add(ApplicationRecord(
            id=id, company="Employer " + id, job="Research",
            action=action, import_id="external-" + id,
            when="2026-fall", deadline="2026-11-13", next="ASAP",
            target="https://example.org/action", brief="Do not rewrite",
            portal="https://example.org/candidate", contact="Recruiter",
        ))
    return store


def manifest(*ids):
    return {"schema_version": 1, "shortlist": list(ids)}


def test_promote_only_check_preserve_other_actions_and_fields(tmp_path):
    store = setup_store(tmp_path)
    before = {job["id"]: job for job in store.export_data()["jobs"]}
    count = store.shortlist(manifest("external-check", "apply", "wait", "take", "archive"))
    assert count == (1, 4)
    after = {job["id"]: job for job in store.export_data()["jobs"]}
    for id, previous in before.items():
        if id == "check":
            assert after[id] == {**previous, "action": "Apply"}
        else:
            assert after[id] == previous
    assert store.shortlist(manifest("check", "apply", "wait", "take", "archive")) == (0, 5)


def test_unknown_id_aborts_everything_without_partial_application(tmp_path):
    store = setup_store(tmp_path)
    snapshot = store.metadata_path.read_bytes()
    with pytest.raises(ValueError, match="Unknown shortlist job ID"):
        store.shortlist(manifest("check", "missing-id"))
    assert store.metadata_path.read_bytes() == snapshot


@pytest.mark.parametrize("bad", [
    None, [], {},
    {"schema_version": 1, "shortlist": "check"},
    {"schema_version": 2, "shortlist": ["check"]},
    {"schema_version": True, "shortlist": ["check"]},
    {"schema_version": 1, "shortlist": ["check", "check"]},
    {"schema_version": 1, "shortlist": ["check", 42]},
    {"schema_version": 1, "shortlist": [" check"]},
    {"schema_version": 1, "shortlist": [""]},
    {"schema_version": 1, "shortlist": ["check"], "jobs": []},
])
def test_invalid_manifest_fails_without_changes(tmp_path, bad):
    store = setup_store(tmp_path)
    snapshot = store.metadata_path.read_bytes()
    with pytest.raises(ValueError):
        store.shortlist(bad)
    assert store.metadata_path.read_bytes() == snapshot


def test_empty_shortlist_is_safe_noop(tmp_path):
    store = setup_store(tmp_path)
    snapshot = store.metadata_path.read_bytes()
    assert store.shortlist(manifest()) == (0, 0)
    assert store.metadata_path.read_bytes() == snapshot


def test_duplicate_alias_same_record_is_counted_once(tmp_path):
    store = setup_store(tmp_path)
    assert store.shortlist(manifest("check", "external-check")) == (1, 0)


def test_cli_explicit_path(tmp_path, monkeypatch, capsys):
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    file = tmp_path / "promotion.json"
    file.write_text(json.dumps(manifest("check", "wait")), encoding="utf-8")
    cli.main(["shortlist", str(file)])
    assert file.exists()  # An explicitly chosen file outside Downloads is retained.
    assert store.get("check").action == "Apply"
    assert store.get("wait").action == "Wait"
    assert "1 moved Check" in capsys.readouterr().out


def test_cli_default_download_path(tmp_path, monkeypatch):
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    from pathlib import Path
    original_home = Path.home
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "jobco-shortlist.json").write_text(
        json.dumps(manifest("external-check")), encoding="utf-8",
    )
    cli.main(["shortlist"])
    assert store.get("check").action == "Apply"
    assert not (downloads / "jobco-shortlist.json").exists()


def test_shortlist_does_not_create_unknown_jobs(tmp_path):
    store = setup_store(tmp_path)
    with pytest.raises(ValueError, match="Unknown shortlist"):
        store.shortlist(manifest("new-role"))
    assert len(store.list()) == 5


def test_shortlist_explicit_json_inside_downloads_is_deleted(tmp_path, monkeypatch):
    from pathlib import Path
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    file = downloads / "special-shortlist.json"
    file.write_text(json.dumps(manifest("check", "wait")), encoding="utf-8")
    cli.main(["shortlist", str(file)])
    assert not file.exists()
    assert store.get("check").action == "Apply"
    assert store.get("wait").action == "Wait"


def test_shortlist_validation_failure_keeps_downloaded_file(tmp_path, monkeypatch):
    from pathlib import Path
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    file = downloads / "jobco-shortlist.json"
    file.write_text(json.dumps(manifest("check", "nonexistent")), encoding="utf-8")
    before = store.metadata_path.read_bytes()
    with pytest.raises(SystemExit):
        cli.main(["shortlist"])
    assert file.exists()
    assert store.metadata_path.read_bytes() == before


def test_successful_noop_shortlist_still_removes_downloaded_manifest(tmp_path, monkeypatch):
    from pathlib import Path
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    file = downloads / "jobco-shortlist.json"
    file.write_text(json.dumps(manifest("apply", "wait")), encoding="utf-8")
    cli.main(["shortlist"])
    assert not file.exists()
    assert store.get("apply").action == "Apply"
    assert store.get("wait").action == "Wait"


def test_shortlist_failed_cleanup_does_not_claim_promotion_failed(tmp_path, monkeypatch, capsys):
    from pathlib import Path
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    file = downloads / "jobco-shortlist.json"
    file.write_text(json.dumps(manifest("check")), encoding="utf-8")
    original_unlink = Path.unlink

    def blocked_unlink(path, *args, **kwargs):
        if path == file:
            raise PermissionError("locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", blocked_unlink)
    cli.main(["shortlist"])
    assert store.get("check").action == "Apply"
    assert file.exists()
    output = capsys.readouterr()
    assert "1 moved Check" in output.out
    assert "could not remove" in output.err


def test_shortlist_keeps_non_json_manifest_even_in_downloads(tmp_path, monkeypatch):
    from pathlib import Path
    store = setup_store(tmp_path)
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    file = downloads / "manifest.txt"
    file.write_text(json.dumps(manifest("check")), encoding="utf-8")
    cli.main(["shortlist", str(file)])
    assert file.exists()
    assert store.get("check").action == "Apply"



def test_shortlist_schedules_this_sunday_except_earlier_cutoffs(tmp_path):
    from datetime import date

    store = CareerStore(tmp_path / "scheduled")
    candidates = (
        ("future-exact", "2026-12-31", "2026-11-15"),
        ("future-month", "2026-12", "2026-11-15"),
        ("future-spring", "2027-spring", "2026-11-15"),
        ("deadline-before-sunday", "2026-11-13 19:30", "2026-11-13 19:30"),
        ("expired-exact", "2026-10-25", "2026-10-25"),
        ("expired-month", "2026-09", "2026-09-06"),
        ("unknown", "", "2026-11-15"),
    )
    for ident, cutoff, _ in candidates:
        store.add(ApplicationRecord(
            id=ident, company="C" + ident, job="Analyst",
            action="Check", deadline=cutoff, when="2026-fall",
            next="2027-06-01", brief="original brief",
        ))
    promoted, skipped = store.shortlist(
        manifest(*(ident for ident, _, _ in candidates)),
        today=date(2026, 11, 9),
    )
    assert (promoted, skipped) == (7, 0)
    for ident, cutoff, expected in candidates:
        result = store.get(ident)
        assert result.action == "Apply"
        assert result.next == expected
        assert result.deadline == cutoff
        assert result.brief == "original brief"
    assert store.shortlist(manifest("future-exact"),
                           today=date(2026, 11, 10)) == (0, 1)
    assert store.get("future-exact").next == "2026-11-15"


def test_shortlist_preserves_intentional_asap_and_existing_actions(tmp_path):
    from datetime import date

    store = setup_store(tmp_path)
    store.add(ApplicationRecord(
        id="scheduled", company="Scheduled", job="Analyst",
        action="Check", deadline="2026-12-31", next="2027-02-01",
    ))
    before = {r.id: r.to_dict() for r in store.list()}
    assert store.shortlist(manifest("scheduled", "check", "wait", "apply"),
                           today=date(2026, 11, 9)) == (2, 2)
    assert store.get("scheduled").next == "2026-11-15"
    assert store.get("check").next == "ASAP"
    for ident in ("wait", "apply"):
        assert store.get(ident).to_dict() == before[ident]


def test_shortlist_day_of_week_rolls_next_week(tmp_path):
    from datetime import date

    store = CareerStore(tmp_path / "week")
    store.add(ApplicationRecord(
        id="a", company="Employer", job="Analyst", action="Check",
        deadline="2027-01-01",
    ))
    store.shortlist(manifest("a"), today=date(2026, 11, 16))
    assert store.get("a").next == "2026-11-22"
