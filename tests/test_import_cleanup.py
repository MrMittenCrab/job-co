"""Job import and shortlist remove only successfully consumed Downloads JSON."""
import json
from pathlib import Path

import pytest

from career_job_manager import cli
from career_job_manager.store import CareerStore


def payload():
    return {
        "schema_version": 1,
        "jobs": [
            {
                "id": "sample-equity-research-2027",
                "company": "Sample Capital",
                "role": "Equity Research Intern",
                "when": "2026-11",
                "deadline": "2026-11-30",
            }
        ],
    }


def test_job_import_success_deletes_downloaded_json(tmp_path, monkeypatch, capsys):
    store = CareerStore(tmp_path / "career")
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    source = downloads / "jobco-import.json"
    source.write_text(json.dumps(payload()), encoding="utf-8")

    cli.main(["import", str(source)])

    assert not source.exists()
    assert len(store.list()) == 1
    assert store.list()[0].import_id == "sample-equity-research-2027"
    assert "Removed" in capsys.readouterr().out


def test_job_import_failure_preserves_downloaded_source(tmp_path, monkeypatch):
    store = CareerStore(tmp_path / "career")
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    source = downloads / "jobco-import.json"
    source.write_text('{"schema_version":1,"jobs":"not a list"}', encoding="utf-8")
    snapshot = store.metadata_path.read_bytes()

    with pytest.raises(SystemExit):
        cli.main(["import", str(source)])

    assert source.exists()
    assert store.metadata_path.read_bytes() == snapshot


def test_invalid_json_file_is_not_removed(tmp_path, monkeypatch):
    store = CareerStore(tmp_path / "career")
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    source = downloads / "jobco-import.json"
    source.write_text("{not-valid-json", encoding="utf-8")

    with pytest.raises(SystemExit):
        cli.main(["import", str(source)])

    assert source.exists()


def test_successful_import_outside_downloads_keeps_json(tmp_path, monkeypatch):
    store = CareerStore(tmp_path / "career")
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    source = tmp_path / "backup-import.json"
    source.write_text(json.dumps(payload()), encoding="utf-8")

    cli.main(["import", str(source)])

    assert source.exists()
    assert len(store.list()) == 1


def test_successful_company_import_also_cleans_downloads(tmp_path, monkeypatch):
    store = CareerStore(tmp_path / "career")
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    source = downloads / "import-again.json"
    source.write_text(json.dumps(payload()), encoding="utf-8")

    cli.company_main(["import", str(source)])

    assert not source.exists()
    assert len(store.list()) == 1


def test_import_cleanup_failure_warns_but_import_remains_successful(
    tmp_path, monkeypatch, capsys,
):
    store = CareerStore(tmp_path / "career")
    monkeypatch.setattr(cli, "CareerStore", lambda: store)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    source = downloads / "jobco-import.json"
    source.write_text(json.dumps(payload()), encoding="utf-8")
    original_unlink = Path.unlink

    def fail_cleanup(path, *args, **kwargs):
        if path == source:
            raise PermissionError("locked file")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    cli.main(["import", str(source)])

    assert source.exists()
    assert len(store.list()) == 1
    captured = capsys.readouterr()
    assert "1 created" in captured.out
    assert "could not remove" in captured.err
