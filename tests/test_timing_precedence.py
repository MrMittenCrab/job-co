import json

import pytest

from career_job_manager import timing
from career_job_manager.model import ApplicationRecord, sort_records
from career_job_manager.presentation import render_home_lines
from career_job_manager.store import CareerStore


@pytest.mark.parametrize('import_id', ['', 'imported'])
@pytest.mark.parametrize('when', ['', '2026-fall', '2026-10', '2026-09..2026-10'])
def test_exact_deadline_controls_display_and_order(tmp_path, import_id, when):
    store = CareerStore(tmp_path)
    store.add(ApplicationRecord(id='exact', company='Exact', job='Role',
                               deadline='2026-10-31', when=when, import_id=import_id))
    store.update('exact', {'contact': 'Jane'})
    record = store.get('exact')
    assert record.deadline == '2026-10-31'
    assert record.when == when
    earlier = ApplicationRecord(id='earlier', company='Earlier', job='Role', when='2026-10')
    assert [r.id for r in sort_records([record, earlier])] == ['exact', 'earlier']
    assert render_home_lines([record])[1][2:18].strip() == '31 Oct'


@pytest.mark.parametrize('when, label', [
    ('2026-10', '~Oct'), ('2026-09..2026-10', '~Sep–Oct'),
    ('2026-fall', '~Fall'), ('2026-10-31', '31 Oct'), ('', '~Winter'),
])
def test_when_or_season_used_only_without_deadline(tmp_path, monkeypatch, when, label):
    monkeypatch.setattr(timing, 'current_season', lambda: '2026-winter')
    store = CareerStore(tmp_path)
    store.add(ApplicationRecord(id='job', company='Company', job='Role', when=when))
    record = store.get('job')
    assert record.deadline == ''
    assert record.when == (when or '2026-winter')
    assert render_home_lines([record])[1][2:18].strip() == label
    later = ApplicationRecord(id='later', company='Later', job='Role', deadline='2027-03-01')
    expected = ['job', 'later'] if when == '2026-10-31' else ['later', 'job']
    assert [r.id for r in sort_records([later, record])] == expected


def test_migration_only_fills_genuinely_undated_records(tmp_path, monkeypatch):
    monkeypatch.setattr(timing, 'current_season', lambda: '2026-fall')
    store = CareerStore(tmp_path)
    rows = [
        {'id': 'exact', 'company': 'Exact', 'job': 'Role', 'deadline': '2026-10-31 14:30'},
        {'id': 'month', 'company': 'Month', 'job': 'Role', 'when': '2026-10'},
        {'id': 'undated', 'company': 'Undated', 'job': 'Role'},
    ]
    store.metadata_path.write_text(json.dumps({'version': 6, 'applications': rows}))
    store.list()
    saved = {r['id']: r for r in json.loads(store.metadata_path.read_text())['jobs']}
    assert saved['exact']['deadline'] == '2026-10-31 14:30'
    assert saved['exact']['when'] == ''
    assert saved['month']['when'] == '2026-10'
    assert saved['undated']['when'] == '2026-fall'
    assert saved['undated']['deadline'] == ''
    before = store.metadata_path.read_bytes()
    store.list()
    assert store.metadata_path.read_bytes() == before


@pytest.mark.parametrize('extra', [{}, {'deadline': ''}])
def test_reimport_fuzzy_when_preserves_manually_edited_deadline(tmp_path, extra):
    store = CareerStore(tmp_path)
    job = {'id': 'imported', 'company': 'Company', 'role': 'Role', 'when': '2026-10'}
    store.import_jobs({'schema_version': 1, 'jobs': [job]})
    record = store.list()[0]
    store.update(record.id, {'deadline': '2026-10-31 14:30'})
    store.import_jobs({'schema_version': 1, 'jobs': [{**job, 'when': '2026-fall', **extra}]})
    saved = store.get(record.id)
    assert saved.deadline == '2026-10-31 14:30'
    assert render_home_lines([saved])[1][2:18].strip() == '31 Oct 14:30'


@pytest.mark.parametrize('existing, incoming, expected', [
    ('2026-10-31', '2026-fall', '2026-10-31'),
    ('2026-10', '2026-fall', '2026-10'),
    ('2026-10', '2026-09..2026-10', '2026-10'),
    ('2026-fall', '2026-10', '2026-10'),
    ('2026-10', '2026-11', '2026-11'),
])
def test_reimport_preserves_or_improves_timing_precision(tmp_path, existing, incoming, expected):
    store = CareerStore(tmp_path)
    job = {'id': 'imported', 'company': 'Company', 'role': 'Role', 'when': existing}
    store.import_jobs({'schema_version': 1, 'jobs': [job]})
    store.import_jobs({'schema_version': 1, 'jobs': [{**job, 'when': incoming}]})
    assert store.list()[0].when == expected
    assert store.list()[0].deadline == ''


@pytest.mark.parametrize('reverse_input', [False, True])
def test_stored_deadlines_sort_all_exact_before_fuzzy(tmp_path, reverse_input):
    rows = [
        {'id': 'sep-fuzzy', 'company': 'A', 'job': 'Role', 'when': '2026-09'},
        {'id': 'oct-five', 'company': 'Z', 'job': 'Role', 'deadline': '2026-10-05', 'when': '2026-09'},
        {'id': 'sep-time', 'company': 'Z', 'job': 'Role', 'deadline': '2026-09-23 02:30', 'when': '2026-10'},
        {'id': 'oct-fuzzy', 'company': 'A', 'job': 'Role', 'when': '2026-10'},
        {'id': 'sep-ten', 'company': 'Z', 'job': 'Role', 'deadline': '2026-09-10', 'when': '2026-fall'},
        {'id': 'sep-twenty-one', 'company': 'Z', 'job': 'Role', 'when': '2026-09-21'},
    ]
    store = CareerStore(tmp_path)
    store.metadata_path.write_text(json.dumps({
        'version': 7, 'applications': rows[::-1] if reverse_input else rows,
    }))
    store.list()  # Persist the one-time folder-name migration before testing read-only sorting.
    persisted = json.loads(store.metadata_path.read_text())['jobs']
    for row, saved in zip(rows[::-1] if reverse_input else rows, persisted):
        assert all(saved[key] == value for key, value in row.items())
    before = store.metadata_path.read_bytes()

    ordered = store.list()

    assert [record.id for record in ordered] == [
        'sep-ten', 'sep-twenty-one', 'sep-time', 'oct-five', 'sep-fuzzy', 'oct-fuzzy',
    ]
    assert [line[2:18].strip() for line in render_home_lines(ordered)[1:]] == [
        '10 Sep', '21 Sep', '23 Sep 02:30', '5 Oct', '~Sep', '~Oct',
    ]
    assert store.metadata_path.read_bytes() == before
    assert all(not record.deadline for record in ordered if record.id.endswith('fuzzy'))


@pytest.mark.parametrize('period,last_day,next_day', [
    ('2026-09', '2026-09-30', '2026-10-01'),
    ('2026-12', '2026-12-31', '2027-01-01'),
    ('2024-02', '2024-02-29', '2024-03-01'),
])
def test_last_minute_exact_deadline_precedes_fuzzy_month(period, last_day, next_day):
    records = [
        ApplicationRecord(id='fuzzy', company='A', job='Role', when=period),
        ApplicationRecord(id='next', company='A', job='Role', deadline=next_day),
        ApplicationRecord(id='late', company='Z', job='Role', deadline=last_day + ' 23:59'),
        ApplicationRecord(id='early', company='Z', job='Role', deadline=last_day + ' 02:30'),
    ]
    before = [record.to_dict() for record in records]
    assert [record.id for record in sort_records(records)] == ['early', 'late', 'next', 'fuzzy']
    assert [record.to_dict() for record in records] == before


@pytest.mark.parametrize('exact_field', ['deadline', 'when'])
def test_deadline_display_and_order_match_exact_first_example(tmp_path, exact_field):
    rows = [
        {'id': 'nov', 'when': '2026-11'},
        {'id': 'oct-exact', exact_field: '2026-10-10'},
        {'id': 'sep', 'when': '2026-09'},
        {'id': 'time', 'deadline': '2026-09-23 02:30', 'when': '2026-08'},
        {'id': 'oct', 'when': '2026-10'},
        {'id': 'day', exact_field: '2026-09-21'},
    ]
    store = CareerStore(tmp_path)
    for row in rows:
        store.add(ApplicationRecord(company=row['id'], job='Role', **row))
    before = store.metadata_path.read_bytes()

    assert [line[2:18].strip() for line in render_home_lines(store.list())[1:]] == [
        '21 Sep', '23 Sep 02:30', '10 Oct', '~Sep', '~Oct', '~Nov',
    ]
    assert store.metadata_path.read_bytes() == before
    assert all(store.get(record_id).deadline == '' for record_id in ['sep', 'oct', 'nov'])
