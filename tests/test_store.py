import json
from pathlib import Path

import pytest

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore


def make_record(**overrides):
    data = {
        "id": "app-1",
        "company": "HSBC",
        "job": "Global Banking Graduate",
        "status": "Application",
        "deadline": "2026-09-30",
        "action": "Apply",
        "apply": "https://example.com",
        "contact": "",
        "description": "",
        "resume": "",
        "letter": "",
    }
    data.update(overrides)
    return ApplicationRecord(**data)


def test_add_persists_human_readable_json_and_imports_documents(tmp_path):
    store = CareerStore(tmp_path / "Career")
    resume = tmp_path / "Resume (1).docx"
    resume.write_text("resume")
    letter = tmp_path / "Letter FINAL.docx"
    letter.write_text("letter")

    saved = store.add(make_record(), resume_source=resume, letter_source=letter)

    assert saved.resume == "HSBC_Global-Banking-Graduate_Resume.docx"
    assert saved.letter == "HSBC_Global-Banking-Graduate_Letter.docx"
    assert (store.applications_dir / "HSBC_Global-Banking-Graduate" / saved.resume).exists()
    payload = json.loads(store.metadata_path.read_text())
    assert payload["version"] == 1
    assert payload["applications"][0]["company"] == "HSBC"
    assert "\n  " in store.metadata_path.read_text()


def test_update_company_or_job_renames_folder_and_documents(tmp_path):
    store = CareerStore(tmp_path / "Career")
    resume = tmp_path / "resume.docx"
    resume.write_text("resume")
    store.add(make_record(), resume_source=resume)

    updated = store.update("app-1", {"job": "Global Banking Analyst"})

    old_folder = store.applications_dir / "HSBC_Global-Banking-Graduate"
    new_folder = store.applications_dir / "HSBC_Global-Banking-Analyst"
    assert not old_folder.exists()
    assert new_folder.exists()
    assert updated.resume == "HSBC_Global-Banking-Analyst_Resume.docx"
    assert (new_folder / updated.resume).exists()


def test_replacing_resume_versions_old_current(tmp_path):
    store = CareerStore(tmp_path / "Career")
    first = tmp_path / "first.docx"
    first.write_text("first")
    second = tmp_path / "second.pdf"
    second.write_text("second")
    store.add(make_record(), resume_source=first)

    updated = store.update("app-1", {}, resume_source=second)
    folder = store.applications_dir / "HSBC_Global-Banking-Graduate"

    assert updated.resume == "HSBC_Global-Banking-Graduate_Resume.pdf"
    assert (folder / "HSBC_Global-Banking-Graduate_Resume.pdf").read_text() == "second"
    assert (folder / "HSBC_Global-Banking-Graduate_Resume_1.docx").read_text() == "first"


def test_duplicate_company_job_folder_is_rejected(tmp_path):
    store = CareerStore(tmp_path / "Career")
    store.add(make_record(id="1"))
    with pytest.raises(ValueError, match="already exists"):
        store.add(make_record(id="2"))


def test_delete_removes_metadata_and_application_folder(tmp_path):
    store = CareerStore(tmp_path / "Career")
    store.add(make_record())
    folder = store.applications_dir / "HSBC_Global-Banking-Graduate"
    assert folder.exists()

    store.delete("app-1")

    assert store.list() == []
    assert not folder.exists()
