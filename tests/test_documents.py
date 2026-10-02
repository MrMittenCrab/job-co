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


def test_all_four_document_types_use_canonical_names(tmp_path):
    folder = tmp_path / "job"
    stem = "HSBC_Global-Banking-Graduate"
    for kind in ("Resume", "Letter", "Brochure", "Form"):
        source = tmp_path / f"random {kind} (1).pdf"
        source.write_text(kind)
        name = import_versioned_document(source, folder, stem, kind)
        assert name == f"{stem}_{kind}.pdf"
        assert (folder / name).read_text() == kind
        assert source.read_text() == kind


def test_import_replaces_current_and_removes_stale_versions(tmp_path):
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
    assert source.read_text() == "new"
    assert list(folder.iterdir()) == [folder / name]


def test_current_document_name_returns_indexless_document(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    stem = "BCG_Associate"
    (folder / f"{stem}_Form_1.pdf").write_text("old")
    assert current_document_name(folder, stem, "Form") == ""
    (folder / f"{stem}_Form.pdf").write_text("new")
    assert current_document_name(folder, stem, "Form") == f"{stem}_Form.pdf"


def test_rename_managed_documents_changes_stem_and_preserves_all_types(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    old = "HSBC_Global-Banking-Graduate"
    new = "HSBC_Global-Banking-Analyst"
    for filename in [
        f"{old}_Resume.docx",
        f"{old}_Resume_1.pdf",
        f"{old}_Letter.docx",
        f"{old}_Brochure.pdf",
        f"{old}_Form.pdf",
        "notes.txt",
    ]:
        (folder / filename).write_text(filename)

    rename_managed_documents(folder, old, new)

    assert (folder / f"{new}_Resume.docx").exists()
    assert (folder / f"{new}_Resume_1.pdf").exists()
    assert (folder / f"{new}_Letter.docx").exists()
    assert (folder / f"{new}_Brochure.pdf").exists()
    assert (folder / f"{new}_Form.pdf").exists()
    assert (folder / "notes.txt").exists()


def test_copy_failure_preserves_source_and_existing_destination(tmp_path, monkeypatch):
    import pytest
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'new source')
    folder = tmp_path / 'managed'
    folder.mkdir()
    current = folder / 'Company_Role_Resume.pdf'
    current.write_bytes(b'existing')

    def failed_copy(source_path, target_path):
        target_path.write_bytes(b'partial')
        raise OSError('copy failed')

    monkeypatch.setattr('career_job_manager.documents.shutil.copy2', failed_copy)
    with pytest.raises(OSError, match='copy failed'):
        import_versioned_document(source, folder, 'Company_Role', 'Resume')
    assert source.read_bytes() == b'new source'
    assert current.read_bytes() == b'existing'
    assert list(folder.iterdir()) == [current]


def test_external_symlink_to_managed_file_cannot_replace_its_source(tmp_path):
    import pytest
    folder = tmp_path / 'managed'
    folder.mkdir()
    managed = folder / 'Company_Role_Resume.pdf'
    managed.write_bytes(b'keep source contents')
    source = tmp_path / 'alias.docx'
    source.symlink_to(managed)
    with pytest.raises(ValueError, match='outside this managed'):
        import_versioned_document(source, folder, 'Company_Role', 'Resume')
    assert source.is_symlink()
    assert source.read_bytes() == managed.read_bytes() == b'keep source contents'
    assert list(folder.iterdir()) == [managed]
