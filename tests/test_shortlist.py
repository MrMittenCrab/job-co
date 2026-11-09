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


def test_shortlist_does_not_create_unknown_jobs(tmp_path):
    store = setup_store(tmp_path)
    with pytest.raises(ValueError, match="Unknown shortlist"):
        store.shortlist(manifest("new-role"))
    assert len(store.list()) == 5
