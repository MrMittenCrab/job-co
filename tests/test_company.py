import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from career_job_manager.company import (TABLES, cell, departments, ordered_rows,
                                        resolve, revenue_key)
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp


def seed(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs({'companies': [{'id': 'co', 'name': 'Company', 'aliases': ['Alias'],
        'strategy': [{'department': 'Small', 'revenue': '$2mn'},
                     {'department': 'Large', 'revenue': '$1bn'}]}],
        'jobs': [{'id': 'job', 'company_id': 'co', 'company': 'Company', 'job': 'Analyst'}]})
    return store


def test_migration_preserves_jobs_identity_metadata_and_new_data(tmp_path):
    store = seed(tmp_path)
    original = store.export_data()
    original['research_scope'] = {'keep': [1, 2]}
    co = original['companies'][0]
    co.update(evidence=['source'], ownership_bucket='public', research_notes='keep',
              delivery=[{'entity': 'Old', 'section': 'control'}], value={'obsolete': True})
    co['clients'] = [{'client': 'Old', 'service': 'Research', 'observations': [{'wallet': 100}]},
                     {'client': 'New', 'period': '2025', 'engagement': 'Advice', 'role': 'Lead'}]
    original['companies'].append({'id': 'empty', 'name': 'Empty', 'clients': [
        {'client': 'Old', 'service': 'Research'}], 'delivery': []})
    store.metadata_path.write_text(json.dumps(original))
    migrated = CareerStore(tmp_path)
    saved = json.loads(migrated.metadata_path.read_text())
    assert saved['jobs'] == original['jobs']
    assert saved['research_scope'] == original['research_scope']
    co = saved['companies'][0]
    for key in ('id', 'name', 'aliases', 'evidence', 'ownership_bucket', 'research_notes', 'strategy'):
        assert co[key] == original['companies'][0][key]
    assert 'value' not in co and 'delivery' not in co
    assert co['clients'] == [original['companies'][0]['clients'][1]]
    assert all(saved['companies'][1][t] == [] for t in TABLES)
    before = migrated.metadata_path.read_bytes(), migrated.metadata_path.stat().st_mtime_ns
    CareerStore(tmp_path).companies()
    assert (migrated.metadata_path.read_bytes(), migrated.metadata_path.stat().st_mtime_ns) == before


@pytest.mark.parametrize('raw,expected', [
    ('Alpha·Beta', 'Alpha · Beta'), ('Alpha  ·Beta', 'Alpha · Beta'), ('Alpha ·Beta  · Gamma', 'Alpha · Beta · Gamma'),
    ('Alpha ·  · Gamma', 'Alpha · Gamma'), ('Alpha · Beta  ·', 'Alpha · Beta'),
    ('· Alpha', 'Alpha'), (' · · ', '-'), ('', '-'), (None, '-'), ('N/A', '-'),
    ('Undisclosed', '-'), ('N/D', '-'), ('Unknown', '-'), ('Not disclosed', '-'),
    ('Revenue +29.6%, PBT +115.3%; Actual / meaning', 'Revenue +29.6%, PBT +115.3%; Actual / meaning'),
    ('Known · Unknown', 'Known'),
])
def test_cell_format(raw, expected):
    assert cell(raw) == expected


def test_order_and_home_derivation():
    co = {'strategy': [{'department': name, 'revenue': revenue} for name, revenue in
          [('Missing', None), ('Small', 'HK$ 2mn'), ('Large', 'CNY 1bn'),
           ('Bad', 'estimate'), ('Largest', '€1.5tn'), ('Equal', 'USD 2m')]],
          'clients': [{'period': p} for p in ['', '2012–2018', '2025', '2019-2023', None]]}
    before = deepcopy(co)
    assert departments(co) == 'Largest · Large · Small · Equal · Missing · Bad'
    for table in ('makeup', 'direction'):
        co[table] = deepcopy(co['strategy'])
        assert ordered_rows(co, table) == ordered_rows(co, 'strategy')
    assert [r['period'] for r in ordered_rows(co, 'clients')] == ['2025', '2019-2023', '2012–2018', '', None]
    assert co['strategy'] == before['strategy']
    assert departments({}) == '-'
    assert revenue_key('£1b') == revenue_key('£1000m')
    assert revenue_key('¥1t') == revenue_key('¥1000bn')
    assert revenue_key('$1k') == revenue_key('$1,000')
    assert revenue_key('USD $2m') == revenue_key('HK$2mn')
    assert revenue_key('not 100')[0] is True


def test_six_schemas_and_partial_import(tmp_path):
    assert TABLES == {
        'strategy': ('Department', 'Revenue', 'Rank', 'Model'),
        'makeup': ('Department', 'Revenue', 'Scale', 'Mix'),
        'direction': ('Department', 'Revenue', 'Growth', 'Edge'),
        'clients': ('Client', 'Period', 'Engagement', 'Role'),
        'franchise': ('Entity', 'Parent', 'Footprint'),
        'leadership': ('Layer', 'Parent', 'Composition')}
    store = seed(tmp_path)
    store.import_jobs({'companies': [{'id': 'co', 'name': 'Company', 'strategy': [
        {'department': 'Small', 'rank': 'Alpha·Beta', 'evidence': ['keep']}]}]})
    row = resolve(store.companies(), 'co')['strategy'][0]
    assert row['revenue'] == '$2mn' and row['rank'] == 'Alpha · Beta'
    schema = json.loads(Path('schemas/company-intelligence.schema.json').read_text())
    Draft202012Validator(schema).validate(store.export_data())
    other = CareerStore(tmp_path / 'roundtrip')
    other.import_jobs(store.export_data())
    assert other.export_data()['companies'] == store.export_data()['companies']


def test_job_company_entry_defaults_to_strategy(tmp_path):
    async def scenario():
        app = CareerApp(seed(tmp_path))
        async with app.run_test() as pilot:
            await pilot.press('c')
            assert app.screen.view == 'strategy'
            await pilot.press('escape', 'left', 'right', 'c')
            assert app.screen.view == 'strategy'
    asyncio.run(scenario())


@pytest.mark.parametrize('existing_makeup', [False, True])
def test_composition_migration_preserves_rows_and_is_idempotent(tmp_path, existing_makeup):
    store = seed(tmp_path)
    payload = store.export_data()
    co = payload['companies'][0]
    legacy = {'id': 'legacy', 'department': 'Markets', 'revenue': '$1bn',
              'scale': 'Global  ·  Local ·', 'mix': 'Advice', 'evidence': ['source']}
    co['composition'] = [legacy]
    current = {'id': 'current', 'department': 'Banking', 'revenue': '-', 'scale': '-', 'mix': '-'}
    co.pop('makeup', None)
    if existing_makeup:
        co['makeup'] = [current]
    store.metadata_path.write_text(json.dumps(payload))
    migrated = CareerStore(tmp_path).export_data()
    expected = {**legacy, 'scale': 'Global · Local'}
    assert migrated['companies'][0]['makeup'] == ([current] if existing_makeup else []) + [expected]
    assert 'composition' not in migrated['companies'][0]
    assert migrated['jobs'] == payload['jobs']
    before = store.metadata_path.read_bytes(), store.metadata_path.stat().st_mtime_ns
    CareerStore(tmp_path)
    assert (store.metadata_path.read_bytes(), store.metadata_path.stat().st_mtime_ns) == before
    imported = CareerStore(tmp_path / 'imported')
    imported.import_jobs({'companies': [co]})
    assert imported.export_data()['companies'][0]['makeup'] == migrated['companies'][0]['makeup']


def test_home_groups_only_by_strategy_departments(tmp_path):
    async def scenario():
        companies = [
            {'id': 'z', 'name': 'Zulu', 'strategy': [{'department': 'One'}, {'department': 'Two'}]},
            {'id': 'b', 'name': 'beta', 'strategy': [{'department': 'One'}]},
            {'id': 'a', 'name': 'Alpha', 'clients': [{'client': 'Client'}]},
            {'id': 'd', 'name': 'delta', 'strategy': [{'department': '-'}]},
            {'id': 'c', 'name': 'Charlie', 'strategy': [{'department': ' ·  · '}]},
            {'id': 'e', 'name': 'Echo', 'strategy': [{'revenue': '$1bn'}]},
        ]
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': companies, 'jobs': [
            {'id': c['id'], 'company_id': c['id'], 'company': c['name'], 'job': 'Role'}
            for c in companies]})
        app = CareerApp(store, initial_root='company')
        async with app.run_test() as pilot:
            screen = app.screen
            assert [r['name'] for r in screen.rows] == ['beta', 'Zulu', 'Alpha', 'Charlie', 'delta', 'Echo']
            assert [screen.values(r)[1] for r in screen.rows] == ['One', 'One · Two', '-', '-', '-', '-']
            await pilot.press('n')
            assert screen.view == 'company'
    asyncio.run(scenario())


@pytest.mark.parametrize('rank,expected', [(None, 'First · Second'), ('-', 'First · Second'),
                                         ('First · Second', 'First · Second'),
                                         ('Current', 'Current · First · Second')])
def test_position_migration_and_rank_round_trip(tmp_path, rank, expected):
    store = seed(tmp_path)
    payload = store.export_data()
    row = payload['companies'][0]['strategy'][0]
    row.pop('rank', None)
    row.update(position='First·Second', evidence=['keep'])
    if rank is not None:
        row['rank'] = rank
    store.metadata_path.write_text(json.dumps(payload))
    migrated = CareerStore(tmp_path)
    exported = migrated.export_data()
    actual = exported['companies'][0]['strategy'][0]
    assert actual == {**{k: v for k, v in row.items() if k not in ('position', 'rank')}, 'rank': expected}
    assert exported['jobs'] == payload['jobs']
    assert 'position' not in migrated.metadata_path.read_text()
    before = migrated.metadata_path.read_bytes(), migrated.metadata_path.stat().st_mtime_ns
    CareerStore(tmp_path).export_data()
    assert (migrated.metadata_path.read_bytes(), migrated.metadata_path.stat().st_mtime_ns) == before
    imported = CareerStore(tmp_path / 'round-trip')
    imported.import_jobs(exported)
    assert imported.export_data()['companies'] == exported['companies']
    assert 'position' not in imported.metadata_path.read_text()
    imported.import_jobs({'companies': [{'id': 'co', 'name': 'Company', 'strategy': [
        {'department': row['department'], 'rank': 'Updated·Rank'}]}]})
    assert imported.export_data()['companies'][0]['strategy'][0]['rank'] == 'Updated · Rank'


def test_legacy_position_import_emits_rank(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs({'companies': [{'name': 'Company', 'strategy': [
        {'department': 'Desk', 'position': 'Legacy'}]}]})
    row = store.export_data()['companies'][0]['strategy'][0]
    assert row['rank'] == 'Legacy' and 'position' not in row
