import json

import pytest

from career_job_manager.model import ApplicationRecord
from career_job_manager.naming import application_folder, readable_folder_name
from career_job_manager.store import CareerStore


@pytest.mark.parametrize(('role', 'expected'), [
    ('2027 APAC Graduate Programme - Wealth Management, Investment Advisory - Hong Kong',
     '2027 APAC Graduate Programme'),
    ('Analyst - Hong Kong', 'Analyst'),
    ('London Investment Banking Internship', 'Investment Banking Internship'),
    ('Graduate Programme (UK)', 'Graduate Programme'),
    ('Programme (2027 - Hong Kong)', 'Programme (2027)'),
    ('M&A – Analyst (Credit)', 'M&A – Analyst (Credit)'),
])
def test_readable_role_without_location(tmp_path, role, expected):
    assert application_folder(tmp_path, 'BNP Paribas', role).name == f'BNP Paribas - {expected}'


def test_only_invalid_macos_characters_sanitized():
    assert readable_folder_name('M&G', "Analyst, Credit & Debt (Junior)!") == 'M&G - Analyst, Credit & Debt (Junior)!'
    assert readable_folder_name('A/B:C\x00', 'Role') == 'A B C - Role'


def test_import_ids_never_appear_in_names_and_duplicates_stay_stable(tmp_path):
    store = CareerStore(tmp_path)
    for index in range(3):
        store.add(ApplicationRecord(id=f'opaque-{index}', import_id=f'import-{index}', company='Bank', job='Analyst - Hong Kong'))
    assert [r.folder_name for r in store.list()] == ['Bank - Analyst', 'Bank - Analyst (2)', 'Bank - Analyst (3)']
    store.delete('opaque-0')
    updated = store.update('opaque-1', {'contact': 'Someone'})
    assert updated.folder_name == 'Bank - Analyst (2)'
    assert CareerStore(tmp_path).get('opaque-2').folder_name == 'Bank - Analyst (3)'


def test_distinct_programme_tracks_kept_when_needed(tmp_path):
    store = CareerStore(tmp_path)
    for index, track in enumerate(['Global Markets', 'RISK']):
        store.add(ApplicationRecord(id=str(index), company='BNP Paribas',
                  job=f'2027 APAC Graduate Programme - {track} - Hong Kong'))
    assert store.get('1').folder_name == 'BNP Paribas - 2027 APAC Graduate Programme - RISK'


@pytest.mark.parametrize('kind', ['Resume', 'Letter', 'Form', 'Brochure'])
@pytest.mark.parametrize('stored_path', ['basename', 'absolute', 'relative'])
def test_migration_preserves_documents_and_updates_paths(tmp_path, stored_path, kind):
    store = CareerStore(tmp_path)
    legacy = store.applications_dir / ('Bank_Analyst-Hong-Kong__' + 'a' * 32)
    legacy.mkdir()
    filename = f'Bank_Analyst-Hong-Kong_{kind}.pdf'
    (legacy / filename).write_bytes(b'resume')
    (legacy / 'notes').mkdir()
    (legacy / 'notes' / 'note.txt').write_text('keep')
    name = {'basename': filename, 'absolute': str(legacy / filename),
            'relative': str((legacy / filename).relative_to(tmp_path))}[stored_path]
    record = ApplicationRecord(id='a' * 32, import_id='external', company='Bank', job='Analyst Hong Kong', **{kind.lower(): name})
    store.metadata_path.write_text(json.dumps({'version': 8, 'applications': [record.to_dict()]}))
    occupied = store.applications_dir / 'Bank - Analyst'
    occupied.mkdir()
    (occupied / 'other.txt').write_text('unrelated')
    migrated = store.get(record.id)
    assert migrated.folder_name == 'Bank - Analyst (2)'
    folder = store._folder(migrated)
    assert not legacy.exists()
    assert (folder / getattr(migrated, kind.lower())).read_bytes() == b'resume'
    assert (folder / 'notes' / 'note.txt').read_text() == 'keep'
    assert (occupied / 'other.txt').read_text() == 'unrelated'
    assert CareerStore(tmp_path).get(record.id).folder_name == migrated.folder_name
    updated = store.update(record.id, {'job': 'Associate'})
    assert (store._folder(updated) / getattr(updated, kind.lower())).read_bytes() == b'resume'
    replacement = tmp_path / 'new.docx'
    replacement.write_bytes(b'replacement')
    updated = store.update(record.id, {}, **{f'{kind.lower()}_source': replacement})
    assert (store._folder(updated) / getattr(updated, kind.lower())).read_bytes() == b'replacement'


def test_migration_rolls_back_renames_if_metadata_save_fails(tmp_path, monkeypatch):
    store = CareerStore(tmp_path)
    legacy = store.applications_dir / 'Bank_Analyst__abc'
    legacy.mkdir()
    (legacy / 'notes.txt').write_text('keep')
    row = ApplicationRecord(id='abc', import_id='external', company='Bank', job='Analyst').to_dict()
    original = json.dumps({'version': 8, 'applications': [row]})
    store.metadata_path.write_text(original)
    def fail(records):
        raise OSError('write failed')
    monkeypatch.setattr(store, '_save', fail)
    with pytest.raises(OSError, match='write failed'):
        store.list()
    assert (legacy / 'notes.txt').read_text() == 'keep'
    assert store.metadata_path.read_text() == original


def test_location_edit_keeps_folder_and_managed_documents(tmp_path):
    store = CareerStore(tmp_path / 'Career')
    source = tmp_path / 'resume.pdf'
    source.write_bytes(b'resume')
    record = store.add(ApplicationRecord(id='1', company='Bank', job='Analyst - Hong Kong'), resume_source=source)
    updated = store.update('1', {'job': 'Analyst - Singapore'})
    assert updated.folder_name == record.folder_name == 'Bank - Analyst'
    assert updated.resume != record.resume
    assert (store._folder(updated) / updated.resume).read_bytes() == b'resume'


def test_case_insensitive_collision_does_not_reuse_unmanaged_folder(tmp_path):
    store = CareerStore(tmp_path)
    (store.applications_dir / 'BANK - ANALYST').mkdir()
    record = store.add(ApplicationRecord(id='1', company='Bank', job='Analyst'))
    assert record.folder_name == 'Bank - Analyst (2)'
