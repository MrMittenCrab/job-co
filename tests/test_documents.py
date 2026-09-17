from pathlib import Path

from career_job_manager.documents import (
    current_document_name,
    import_versioned_document,
    rename_managed_documents,
)
from career_job_manager.naming import application_stem


def test_application_stem_normalizes_whitespace_and_unsafe_characters():
    assert application_stem(" HSBC ", "Global   Banking Graduate") == "HSBC_Global-Banking-Graduate"
    assert application_stem("A/B:C", "Role / One") == "ABC_Role-One"
    assert application_stem("腾讯", "策略 管培生") == "腾讯_策略-管培生"


def test_import_ignores_source_name_and_uses_canonical_name(tmp_path):
    source = tmp_path / "Resume FINAL (1).docx"
    source.write_text("new")
    folder = tmp_path / "job"
    name = import_versioned_document(source, folder, "HSBC_Global-Banking-Graduate", "Resume")
    assert name == "HSBC_Global-Banking-Graduate_Resume.docx"
    assert (folder / name).read_text() == "new"


def test_import_shifts_existing_versions_and_keeps_new_current_indexless(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    stem = "HSBC_Global-Banking-Graduate"
    (folder / f"{stem}_Resume.docx").write_text("current")
    (folder / f"{stem}_Resume_1.pdf").write_text("older")
    source = tmp_path / "anything.pdf"
    source.write_text("new")

    name = import_versioned_document(source, folder, stem, "Resume")

    assert name == f"{stem}_Resume.pdf"
    assert (folder / f"{stem}_Resume.pdf").read_text() == "new"
    assert (folder / f"{stem}_Resume_1.docx").read_text() == "current"
    assert (folder / f"{stem}_Resume_2.pdf").read_text() == "older"


def test_current_document_name_returns_indexless_document(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    stem = "BCG_Associate"
    (folder / f"{stem}_Letter_1.docx").write_text("old")
    assert current_document_name(folder, stem, "Letter") == ""
    (folder / f"{stem}_Letter.docx").write_text("new")
    assert current_document_name(folder, stem, "Letter") == f"{stem}_Letter.docx"


def test_rename_managed_documents_changes_stem_and_preserves_versions(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    old = "HSBC_Global-Banking-Graduate"
    new = "HSBC_Global-Banking-Analyst"
    for filename in [
        f"{old}_Resume.docx",
        f"{old}_Resume_1.pdf",
        f"{old}_Letter.docx",
        "notes.txt",
    ]:
        (folder / filename).write_text(filename)

    rename_managed_documents(folder, old, new)

    assert (folder / f"{new}_Resume.docx").exists()
    assert (folder / f"{new}_Resume_1.pdf").exists()
    assert (folder / f"{new}_Letter.docx").exists()
    assert (folder / "notes.txt").exists()
