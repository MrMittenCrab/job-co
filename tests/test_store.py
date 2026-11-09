import json

import pytest

from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore


def make_record(**overrides):
    data = {
        "id": "app-1",
        "company": "HSBC",
        "job": "Global Banking Graduate",
        "deadline": "2026-09-30",
        "action": "Apply",
        "target": "https://example.com/apply",
        "portal": "https://example.com/portal",
        "contact": "",
        "brochure": "",
        "form": "",
        "resume": "",
        "letter": "",
    }
    data.update(overrides)
    return ApplicationRecord(**data)


def test_add_persists_v8_and_imports_all_document_types(tmp_path):
    store = CareerStore(tmp_path / "Career")
    sources = {}
    for kind in ("resume", "letter", "brochure", "form"):
        path = tmp_path / f"{kind} (1).pdf"
        path.write_text(kind)
        sources[f"{kind}_source"] = path

    saved = store.add(make_record(), **sources)

    stem = "HSBC_Global-Banking-Graduate"
    assert saved.resume == f"{stem}_Resume.pdf"
    assert saved.letter == f"{stem}_Letter.pdf"
    assert saved.brochure == f"{stem}_Brochure.pdf"
    assert saved.form == f"{stem}_Form.pdf"
    folder = store._folder(saved)
    assert all((folder / getattr(saved, kind)).exists() for kind in ("resume", "letter", "brochure", "form"))
    payload = json.loads(store.metadata_path.read_text())
    assert payload["version"] == 8


def test_update_company_or_job_renames_folder_and_all_documents(tmp_path):
    store = CareerStore(tmp_path / "Career")
    resume = tmp_path / "resume.docx"
    description = tmp_path / "description.pdf"
    form = tmp_path / "form.pdf"
    resume.write_text("resume")
    description.write_text("description")
    form.write_text("form")
    store.add(make_record(), resume_source=resume, brochure_source=description, form_source=form)

    updated = store.update("app-1", {"job": "Global Banking Analyst"})

    old_folder = store.applications_dir / "HSBC - Global Banking Graduate"
    new_folder = store.applications_dir / "HSBC - Global Banking Analyst"
    assert not old_folder.exists()
    assert new_folder.exists()
    assert updated.resume == "HSBC_Global-Banking-Analyst_Resume.docx"
    assert updated.brochure == "HSBC_Global-Banking-Analyst_Brochure.pdf"
    assert updated.form == "HSBC_Global-Banking-Analyst_Form.pdf"


def test_replacing_form_replaces_old_current(tmp_path):
    store = CareerStore(tmp_path / "Career")
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.docx"
    first.write_text("first")
    second.write_text("second")
    store.add(make_record(), form_source=first)

    updated = store.update("app-1", {}, form_source=second)
    folder = store.applications_dir / "HSBC - Global Banking Graduate"

    assert updated.form == "HSBC_Global-Banking-Graduate_Form.docx"
    assert (folder / updated.form).read_text() == "second"
    assert list(folder.iterdir()) == [folder / updated.form]
    assert first.read_text() == "first"
    assert second.read_text() == "second"


def test_duplicate_company_job_folder_uses_readable_suffix(tmp_path):
    store = CareerStore(tmp_path / "Career")
    first = store.add(make_record(id="1"))
    second = store.add(make_record(id="2"))
    assert first.folder_name == "HSBC - Global Banking Graduate"
    assert second.folder_name == "HSBC - Global Banking Graduate (2)"


def test_delete_removes_metadata_and_application_folder(tmp_path):
    store = CareerStore(tmp_path / "Career")
    store.add(make_record())
    folder = store.applications_dir / "HSBC - Global Banking Graduate"
    assert folder.exists()

    store.delete("app-1")

    assert store.list() == []
    assert not folder.exists()


def test_store_loads_legacy_apply_as_portal_and_resaves_v8(tmp_path):
    root = tmp_path / "Career"
    root.mkdir()
    (root / "Applications").mkdir()
    legacy = {
        "version": 1,
        "applications": [{
            "id": "legacy",
            "company": "HSBC",
            "job": "Analyst",
                "deadline": "2026-09-30",
            "action": "Apply",
            "apply": "https://example.com/portal",
            "contact": "",
            "brochure": "",
            "resume": "",
            "letter": "",
        }],
    }
    (root / "applications.json").write_text(json.dumps(legacy))

    store = CareerStore(root)
    record = store.list()[0]
    assert record.portal == "https://example.com/portal"
    assert record.form == ""

    store.update("legacy", {"contact": "Jane"})
    payload = json.loads(store.metadata_path.read_text())
    assert payload["version"] == 8
    assert payload["jobs"][0]["portal"] == "https://example.com/portal"
    assert "apply" not in payload["jobs"][0]


def test_description_text_and_description_file_are_stored_together(tmp_path):
    store = CareerStore(tmp_path / "Career")
    source = tmp_path / "job description (1).pdf"
    source.write_text("file contents")
    record = make_record(description_text="Pasted description text")

    saved = store.add(record, brochure_source=source)

    assert saved.brochure == "HSBC_Global-Banking-Graduate_Brochure.pdf"
    assert saved.description_text == "Pasted description text"
    payload = json.loads(store.metadata_path.read_text())
    assert payload["jobs"][0]["description_text"] == "Pasted description text"


def test_update_description_text_does_not_replace_description_file(tmp_path):
    store = CareerStore(tmp_path / "Career")
    source = tmp_path / "description.pdf"
    source.write_text("file contents")
    store.add(make_record(description_text="old text"), brochure_source=source)

    updated = store.update("app-1", {"description_text": "new pasted text"})

    assert updated.description_text == "new pasted text"
    assert updated.brochure == "HSBC_Global-Banking-Graduate_Brochure.pdf"
    folder = store.applications_dir / "HSBC - Global Banking Graduate"
    assert (folder / updated.brochure).read_text() == "file contents"


def test_legacy_asap_record_list_and_edit_preserve_original_value(tmp_path):
    store = CareerStore(tmp_path / "Career")
    payload = store._document()
    payload["jobs"] = [{
        "id": "jpm-legacy", "company": "J.P. Morgan Asset Management",
        "job": "China Seasonal Research Analyst", "deadline": "ASAP",
        "action": "Wait", "when": "2026-fall",
        "folder_name": "JPM - China Seasonal Research",
    }]
    store._write(payload)

    records = store.list()  # Previously raised ValueError during sorting.
    assert len(records) == 1
    assert records[0].deadline == ""
    assert records[0].next == "ASAP"

    changed = store.update("jpm-legacy", {"action": "Check"})
    assert changed.action == "Check"
    assert changed.deadline == ""
    assert changed.next == "ASAP"

    corrected = store.update("jpm-legacy", {"next": "", "brief": "Original schedule listed ASAP"})
    assert corrected.next == ""
    assert corrected.brief == "Original schedule listed ASAP"
    assert store.get("jpm-legacy").deadline == ""


def test_legacy_asap_record_rejects_new_invalid_deadline_on_edit(tmp_path):
    store = CareerStore(tmp_path / "Career")
    payload = store._document()
    payload["jobs"] = [{
        "id": "jpm-legacy", "company": "JPMAM", "job": "Research",
        "deadline": "ASAP", "action": "Wait", "when": "2026-fall",
        "folder_name": "JPM - Research",
    }]
    store._write(payload)
    with pytest.raises(ValueError, match="Deadline examples"):
        store.update("jpm-legacy", {"deadline": "SOMEDAY"})
    assert store.get("jpm-legacy").deadline == ""
    assert store.get("jpm-legacy").next == "ASAP"


def test_update_next_does_not_change_application_deadline(tmp_path):
    store = CareerStore(tmp_path / "Career")
    store.add(make_record(id="next-test", deadline="2026-11-13", next="ASAP"))
    changed = store.update("next-test", {"action": "Take", "next": "2026-11-12"})
    assert changed.deadline == "2026-11-13"
    assert changed.next == "2026-11-12"
    assert store.get("next-test").action == "Take"


def test_manual_next_does_not_get_overwritten_by_import(tmp_path):
    store = CareerStore(tmp_path / "Career")
    payload = {"schema_version": 1, "jobs": [
        {"id": "hsbc-2027", "company": "HSBC", "role": "Investment Specialist",
         "when": "2026-fall", "deadline": "2026-11-13"}
    ]}
    store.import_jobs(payload)
    old = next(r for r in store.list() if r.import_id == "hsbc-2027")
    assert old.deadline == "2026-11-13"
    assert old.next == ""
    store.update(old.id, {"action": "Take", "next": "ASAP"})
    store.import_jobs(payload)
    now = store.get(old.id)
    assert now.action == "Take"
    assert now.next == "ASAP"
    assert now.deadline == "2026-11-13"
