import json
from pathlib import Path

import pytest

from career_job_manager.store import CareerStore


def test_default_root(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    assert CareerStore().root == tmp_path / 'Documents/Developer/job&co/data'


def test_migration_preserves_raw_metadata_documents_and_is_repeatable(tmp_path):
    from career_job_manager.migration import migrate_data
    source, target = tmp_path / 'legacy', tmp_path / 'data'
    (source / 'Applications/Original').mkdir(parents=True)
    (source / 'Applications/Original/resume.pdf').write_bytes(b'resume')
    payload = {'jobs': [{'id': 'original', 'action': 'Check', 'history': ['old']}],
               'companies': [{'id': 'co', 'name': 'Company'}], 'unknown': {'keep': True}}
    (source / 'applications.json').write_text(json.dumps(payload))
    migrate_data(source, target)
    (target / 'Applications/Original/resume.pdf').chmod(0o444)
    migrate_data(source, target)
    assert json.loads((target / 'applications.json').read_text()) == payload
    assert (target / 'Applications/Original/resume.pdf').read_bytes() == b'resume'
    assert (source / 'Applications/Original/resume.pdf').read_bytes() == b'resume'
    assert list(target.parent.glob('migration-backups/*/legacy'))


def test_migration_reconciles_disjoint_destination_and_refuses_conflicts(tmp_path):
    from career_job_manager.migration import migrate_data
    source, target = tmp_path / 'legacy', tmp_path / 'data'
    for root, record in ((source, {'id': 'a', 'action': 'Check'}), (target, {'id': 'b'})):
        root.mkdir()
        (root / 'applications.json').write_text(json.dumps({'jobs': [record], 'companies': []}))
    migrate_data(source, target)
    assert {r['id'] for r in json.loads((target / 'applications.json').read_text())['jobs']} == {'a', 'b'}
    before = (target / 'applications.json').read_bytes()
    (source / 'applications.json').write_text(json.dumps({'jobs': [{'id': 'a', 'action': 'different'}]}))
    with pytest.raises(ValueError, match='conflict'):
        migrate_data(source, target)
    assert (target / 'applications.json').read_bytes() == before


def test_document_conflict_does_not_change_metadata_or_files(tmp_path):
    from career_job_manager.migration import migrate_data
    source, target = tmp_path / 'legacy', tmp_path / 'data'
    for root, content in ((source, b'old'), (target, b'new')):
        (root / 'Applications').mkdir(parents=True)
        (root / 'Applications/document.pdf').write_bytes(content)
        (root / 'applications.json').write_text('{"jobs": [], "companies": []}')
    before = (target / 'applications.json').read_bytes()
    with pytest.raises(ValueError, match='document conflict'):
        migrate_data(source, target)
    assert (target / 'Applications/document.pdf').read_bytes() == b'new'
    assert (target / 'applications.json').read_bytes() == before


def test_cli_migration_requires_explicit_source(monkeypatch, tmp_path):
    from career_job_manager import cli, migration
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    calls = []
    monkeypatch.setattr(migration, 'migrate_data', lambda source, target: calls.append((source, target)))
    cli.main(['migrate', str(tmp_path / 'archive')])
    assert calls == [(tmp_path / 'archive', tmp_path / 'Documents/Developer/job&co/data')]
    with pytest.raises(SystemExit):
        cli.main(['migrate'])
