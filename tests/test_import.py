import asyncio
import json
from datetime import date, datetime

import pytest

from career_job_manager import cli, model
from career_job_manager.model import ApplicationRecord, sort_records
from career_job_manager.presentation import FORM_FIELDS, render_home_lines
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp, FieldRow, HomeScreen


def opportunity(**changes):
    return {'id': 'hsbc-markets-hk', 'company': 'HSBC', 'role': 'Markets Graduate',
            'when': '2026-09..2026-10', **changes}


def payload(*jobs):
    return {'schema_version': 1, 'jobs': list(jobs)}


@pytest.mark.parametrize('action', ['Go', 'Wait', 'Applied', 'Email', 'Check', ' Go ', ''])
@pytest.mark.parametrize('legacy', [False, True])
def test_import_preserves_existing_actions_verbatim_on_create_update_and_repeat(tmp_path, action, legacy):
    store = CareerStore(tmp_path)
    records = [
        {'id': 'manual', 'company': 'CPIC', 'job': 'Analyst', 'action': action},
        {'id': 'matched', 'company': 'Company A', 'job': 'Analyst',
         'action': action, 'import_id': 'company-a'},
    ]
    if legacy:
        for record in records:
            record['status'] = 'Application'
    # Seed persisted values directly: imports must also preserve Actions that
    # are not offered by the current manual-edit dropdown.
    store.metadata_path.write_text(json.dumps({'version': 6, 'applications': records}))
    new = opportunity(id='company-c', company='Company C')
    matched = opportunity(id='company-a', company='Company A Updated')

    for jobs, counts in [(payload(new), (1, 0)),
                         (payload(matched, new), (0, 1)),
                         (payload(matched, new), (0, 0))]:
        assert store.import_jobs(jobs).jobs == counts
        saved = json.loads(store.metadata_path.read_text())['jobs']
        assert {record['company']: record['action'] for record in saved} == {
            'CPIC': action,
            ('Company A' if counts == (1, 0) else 'Company A Updated'): action,
            'Company C': 'Check',
        }


def test_import_create_update_preserve_action_and_coexist(tmp_path):
    store = CareerStore(tmp_path)
    store.add(ApplicationRecord(id='manual', company='Manual', job='Analyst'))
    job = opportunity(url='https://example.com', description='Full description\nSecond line')
    assert store.import_jobs(payload(job)).jobs == (1, 0)
    imported = next(r for r in store.list() if r.import_id == job['id'])
    assert (imported.action, imported.portal, imported.description_text) == (
        'Check', 'https://example.com', 'Full description\nSecond line')
    assert imported.brochure == ''  # Existing attachment slot is independent.
    assert imported.when == '2026-09..2026-10'
    store.update(imported.id, {'action': 'Email', 'contact': 'Jane'})
    changed = opportunity(company='HSBC HK', role='Markets Analyst', when='2026-11',
                          deadline='2026-11-30', url='https://new.example', description='Updated')
    assert store.import_jobs(payload(changed)).jobs == (0, 1)
    assert store.import_jobs(payload(changed)).jobs == (0, 0)
    saved = store.get(imported.id)
    assert (saved.company, saved.job, saved.when, saved.deadline) == (
        'HSBC HK', 'Markets Analyst', '2026-11', '2026-11-30')
    assert (saved.action, saved.contact, saved.portal, saved.description_text) == (
        'Email', 'Jane', 'https://new.example', 'Updated')
    assert store.import_jobs(payload(opportunity(id='another', company='Other'))).jobs == (1, 0)
    assert len(store.list()) == 3
    assert store.get('manual').action == 'Apply'
    assert store.get(imported.id).action == 'Email'


def test_distinct_ids_with_same_company_role_are_not_matched(tmp_path):
    store = CareerStore(tmp_path)
    manual = store.add(ApplicationRecord(id='manual', company='HSBC', job='Markets Graduate'))
    store.import_jobs(payload(opportunity(), opportunity(id='another-year', when='2027-fall')))
    assert len(store.list()) == 3
    imported = next(r for r in store.list() if r.import_id == 'hsbc-markets-hk')
    source = tmp_path / 'resume.pdf'
    source.write_text('resume')
    store.update(imported.id, {}, resume_source=source)
    store.import_jobs(payload(opportunity(company='HSBC HK')))
    assert store.get(imported.id).resume.startswith('HSBC-HK_')
    store.delete(imported.id)
    assert len(store.list()) == 2
    assert store.get(manual.id).company == 'HSBC'


@pytest.mark.parametrize('field', ['id', 'company', 'role', 'when'])
@pytest.mark.parametrize('value', [None, '', '  ', 12])
def test_import_required_fields_are_nonempty_strings(tmp_path, field, value):
    store = CareerStore(tmp_path)
    job = opportunity(**{field: value})
    with pytest.raises(ValueError, match=field):
        store.import_jobs(payload(job))
    del job[field]
    with pytest.raises(ValueError, match=field):
        store.import_jobs(payload(job))
    assert store.list() == []


@pytest.mark.parametrize('changes', [
    {'action': 'Apply'}, {'Action': 'Check'},
    {'when': '2026'}, {'when': '2026-13'}, {'when': '2026-02-30'},
    {'when': '2026-autumn'}, {'when': '2026-10..2026-09'},
    {'when': '2026-9'}, {'when': '0000-fall'}, {'deadline': 'not a date'},
    {'url': None}, {'description': []},
])
def test_invalid_import_is_rejected_before_any_jobs_are_written(tmp_path, changes):
    store = CareerStore(tmp_path)
    with pytest.raises(ValueError):
        store.import_jobs(payload(opportunity(id='valid', company='Valid'), opportunity(**changes)))
    assert store.list() == []


@pytest.mark.parametrize('data', [[], {}, {'schema_version': 2, 'jobs': []},
    {'schema_version': True, 'jobs': []}, {'schema_version': 1, 'jobs': {}},
    {'schema_version': 1, 'jobs': [None]}, payload(opportunity(), opportunity())])
def test_invalid_envelope_and_duplicate_ids(tmp_path, data):
    with pytest.raises(ValueError):
        CareerStore(tmp_path).import_jobs(data)


@pytest.mark.parametrize('value, start, display', [
    ('2026-10-31', date(2026, 10, 31), '31 Oct'),
    ('2026-10', date(2026, 10, 1), '~Oct'),
    ('2026-09..2026-10', date(2026, 9, 1), '~Sep–Oct'),
    ('2026-spring', date(2026, 3, 1), '~Spring'),
    ('2026-summer', date(2026, 6, 1), '~Summer'),
    ('2026-fall', date(2026, 9, 1), '~Fall'),
    ('2026-winter', date(2026, 12, 1), '~Winter'),
])
def test_timing_start_and_compact_display(value, start, display):
    from career_job_manager.timing import timing_start, display_when
    assert timing_start(value) == start
    assert display_when(value) == display


def test_import_sort_uses_deadline_before_when(tmp_path):
    store = CareerStore(tmp_path)
    jobs = [opportunity(id=key, company=key, when=when, **extra) for key, when, extra in [
        ('winter', '2026-winter', {}), ('exact-late', '2026-10-31', {}),
        ('month', '2026-10', {}), ('spring', '2026-spring', {}),
        ('range', '2026-08..2026-09', {'deadline': '2026-12-31'}),
        ('summer', '2026-summer', {}), ('fall', '2026-fall', {}),
        ('exact-early', '2026-10-02', {}),
    ]]
    store.import_jobs(payload(*jobs))
    store.add(ApplicationRecord(id='manual', company='manual', job='Analyst', deadline='2026-09-15'))
    records = store.list()
    assert [r.company for r in records] == [
        'manual', 'exact-early', 'exact-late', 'range', 'month', 'spring', 'summer', 'fall', 'winter']
    lines = render_home_lines(records)
    assert lines[0] == '  Deadline        Company           Program                         Action'
    assert lines[4][2:18].strip() == '31 Dec'
    assert lines[8][2:18].strip() == '~Fall'
    for line, record in zip(lines[1:], records):
        assert line[18:36].strip() == record.company
        assert line[36:68].strip() == record.job
        assert line[68:].strip() == record.action


@pytest.mark.parametrize('today, expected', [
    (datetime(2026, 1, 15), '2025-winter'), (datetime(2026, 2, 28), '2025-winter'),
    (datetime(2026, 3, 1), '2026-spring'), (datetime(2026, 6, 1), '2026-summer'),
    (datetime(2026, 9, 19), '2026-fall'), (datetime(2026, 12, 1), '2026-winter'),
])
def test_manual_and_legacy_undated_season_is_persisted(tmp_path, monkeypatch, today, expected):
    from career_job_manager import timing
    monkeypatch.setattr(timing, 'current_season', lambda: timing.season_for_date(today.date()))
    store = CareerStore(tmp_path)
    store.metadata_path.write_text(json.dumps({'version': 6, 'applications': [
        {'id': 'old', 'company': 'Legacy', 'job': 'Analyst', 'action': 'Email', 'target': 'keep'}]}))
    assert store.get('old').when == expected
    store.add(ApplicationRecord(id='manual', company='Manual', job='Analyst'))
    assert store.get('manual').when == expected
    assert store.get('manual').deadline == ''
    monkeypatch.setattr(timing, 'current_season', lambda: '2028-fall')
    assert CareerStore(tmp_path).get('old').when == expected
    assert store.get('manual').when == expected
    assert store.get('old').target == 'keep'
    store.update('manual', {'deadline': '2027-04-01'})
    assert sort_records([store.get('manual'), store.get('old')])[0].id == 'manual'


def test_import_cli_does_not_launch_ui(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(cli.CareerApp, 'run', lambda *a, **k: pytest.fail('opened UI'))
    path = tmp_path / 'jobs.json'
    path.write_text(json.dumps(payload(opportunity())))
    cli.main(['import', str(path)])
    assert '1 created' in capsys.readouterr().out
    cli.main(['import', str(path)])
    assert 'Jobs: 0 created, 0 updated.' in capsys.readouterr().out
    assert len(CareerStore().list()) == 1
    path.write_text('{invalid')
    with pytest.raises(SystemExit) as exc:
        cli.main(['import', str(path)])
    assert exc.value.code == 2


def test_imported_job_uses_normal_form_and_dropdown(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs(payload(opportunity(url='https://example.com', description='Full text')))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            screen = app.screen
            assert tuple(row.field for row in screen.query(FieldRow)) == FORM_FIELDS
            assert screen._row('Portal').value == 'https://example.com'
            assert screen._row('Target').value == ''
            assert screen._row('Target').display
            assert screen._row('DescriptionText').value == 'Full text'
            row = screen._row('Action')
            row.focus()
            await pilot.pause()
            await pilot.press('right')
            assert row.selected_option() == 'Check'
            assert '> Check' in row.render().plain
            await pilot.press('down', 'down')
            assert row.selected_option() == 'Apply'
            assert row.value == 'Check'
            await pilot.press('enter')
            assert row.value == 'Apply'
            assert not row.selector_open
            await pilot.press('left')
            assert isinstance(app.screen, HomeScreen)
            store.import_jobs(payload(opportunity()))
            assert store.list()[0].action == 'Apply'
    asyncio.run(scenario())


def test_empty_import_fields_clear_text_but_preserve_deadline(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs(payload(opportunity(deadline='2026-10-31', url='https://example.com', description='Keep')))
    original = store.list()[0]
    store.update(original.id, {'action': 'Archive'})
    store.import_jobs(payload(opportunity()))
    saved = store.get(original.id)
    assert (saved.action, saved.deadline, saved.portal, saved.description_text) == (
        'Archive', '2026-10-31', 'https://example.com', 'Keep')
    store.import_jobs(payload(opportunity(deadline='', url='', description='')))
    saved = store.get(original.id)
    assert (saved.action, saved.deadline, saved.portal, saved.description_text) == ('Archive', '2026-10-31', '', '')


def test_manual_deadline_edits_control_placement_without_changing_import_timing(tmp_path):
    store = CareerStore(tmp_path)
    store.add(ApplicationRecord(id='manual', company='Manual', job='Analyst',
                                action='Check', when='2026-fall'))
    store.import_jobs(payload(opportunity(when='2026-10', deadline='2026-12-31')))
    imported = next(r for r in store.list() if r.import_id)
    assert [r.id for r in store.list()] == [imported.id, 'manual']
    store.update('manual', {'deadline': '2026-11-01'})
    store.update(imported.id, {'deadline': '2027-01-01'})
    assert [r.id for r in store.list()] == ['manual', imported.id]
    store.update('manual', {'deadline': ''})
    assert [r.id for r in store.list()] == [imported.id, 'manual']
    assert store.get('manual').when == '2026-fall'


def test_timing_crosses_year_boundaries_without_inventing_deadlines(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs(payload(
        opportunity(id='feb', company='February', when='2027-02'),
        opportunity(id='winter', company='Winter', when='2026-winter'),
        opportunity(id='range', company='Range', when='2026-11..2027-02'),
    ))
    assert [r.company for r in store.list()] == ['February', 'Range', 'Winter']
    assert all(r.deadline == '' for r in store.list())
    assert render_home_lines(store.list())[2][2:18].strip() == '~Nov–Feb'


def test_legacy_migration_retains_record_data_and_documents(tmp_path):
    store = CareerStore(tmp_path)
    source = tmp_path / 'resume.pdf'
    source.write_text('existing document')
    store.add(ApplicationRecord(id='old', company='Legacy', job='Analyst', action='Email',
                               target='person@example.com', description_text='Keep text'),
              resume_source=source)
    old = json.loads(store.metadata_path.read_text())
    record = old['jobs'][0]
    record.pop('when')
    record.pop('import_id')
    current_folder = store.applications_dir / record.pop('folder_name')
    current_folder.rename(store.applications_dir / 'Legacy_Analyst')
    old['applications'] = old.pop('jobs')
    old['version'] = 6
    store.metadata_path.write_text(json.dumps(old))
    loaded = store.get('old').to_dict()
    assert {key: loaded[key] for key in record} == record
    assert (store.applications_dir / loaded['folder_name'] / record['resume']).read_text() == 'existing document'
    first_read = store.metadata_path.read_bytes()
    CareerStore(tmp_path).list()
    assert store.metadata_path.read_bytes() == first_read
