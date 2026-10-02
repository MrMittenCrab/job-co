import asyncio
from copy import deepcopy
import json
import tomllib
from pathlib import Path

import pytest
from rich.text import Text

from career_job_manager import cli
from career_job_manager.company import *
from career_job_manager.company_ui import CompanyScreen, CompanyTable, widths_for, table_row
from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp, HomeScreen, ApplicationList, ConfirmDelete


def client(name='Client', **changes):
    return {'client': name, 'segment': 'Public fund', 'service': 'Equities',
            'observations': [observation('2024', 100, 20), observation('2025', 100, 25)],
            'value': 'Research', 'benefit': 'HIDDEN BENEFIT', **changes}


def observation(period, wallet, capture, currency='CNY'):
    return {'period': period, 'wallet': {'amount': wallet, 'currency': currency},
            'capture': {'amount': capture, 'currency': currency}}


def company(**changes):
    return {'id': 'co', 'name': 'Company', 'aliases': ['Alias'], 'clients': [client()],
            'delivery': [{'section': s, 'entity': 'Entity ' + s, 'type': TYPES[s][0],
                          'detail': 'Detail ' + s, 'evidence': [{'source': 'test'}]} for s in SECTIONS], **changes}


def seed(tmp_path):
    store = CareerStore(tmp_path)
    store.import_jobs({'jobs': [{'id': 'a', 'company': 'Alias', 'job': 'Analyst', 'service': 'Equities'},
                                {'id': 'b', 'company': 'Company', 'job': 'Other'},
                                {'id': 'c', 'company': 'Elsewhere', 'job': 'Analyst'}],
                       'companies': [company()]})
    return store


def test_legacy_combined_unknown_and_roundtrip(tmp_path):
    store = CareerStore(tmp_path)
    store.metadata_path.write_text(json.dumps({'applications': [{'id': 'old', 'company': 'Old', 'job': 'Role', 'future': {'a': 1}}], 'future_root': [1]}))
    assert store.get('old').to_dict()['future'] == {'a': 1}
    store.update('old', {'job': 'Updated'})
    assert store.export_data()['future_root'] == [1]
    store.import_jobs({'companies': [company(future_company={'a': 1})], 'jobs': [], 'other': 2})
    exported = store.export_data()
    assert exported['jobs'][0]['future'] == {'a': 1}
    assert exported['companies'][0]['future_company'] == {'a': 1}
    other = CareerStore(tmp_path / 'other')
    other.import_jobs(exported)
    assert other.export_data()['other'] == 2
    assert len(other.companies()) == 2
    assert resolve(other.companies(), name='Old')['clients'] == []


def test_identity_alias_and_empty(tmp_path):
    store = seed(tmp_path)
    companies = store.companies()
    assert len(companies) == 2
    assert resolve(companies, 'co', 'Elsewhere')['name'] == 'Company'
    assert resolve(companies, name=' ALIAS ')['id'] == 'co'
    assert resolve(companies, name='Ｃｏｍｐａｎｙ')['id'] == 'co'
    assert aggregate(resolve(companies, name='Elsewhere')) == ('0', '-', '-', '-', '-')


def test_merge_clients_observations_delivery(tmp_path):
    store = seed(tmp_path)
    incoming = company(name='Renamed', clients=[client(observations=[{'period': '2025', 'capture': {'amount': 30, 'currency': 'CNY'}, 'evidence': ['new']}], future=True)],
                       delivery=[{'section': 'control', 'entity': 'ENTITY CONTROL', 'type': TYPES['control'][0], 'detail': 'New', 'unknown': True}])
    store.import_jobs({'companies': [incoming]})
    store.import_jobs({'companies': [incoming]})
    co = resolve(store.companies(), 'co')
    assert 'Company' in co['aliases']
    assert len(co['clients']) == 1
    row = co['clients'][0]
    assert len(row['observations']) == 2
    assert share(row) == .3
    assert row['benefit'] == 'HIDDEN BENEFIT'
    assert row['future']
    assert len(co['delivery']) == 3
    assert co['delivery'][0]['evidence'] == [{'source': 'test'}]
    assert co['delivery'][0]['unknown']


def test_share_momentum_missing_comparability():
    row = client()
    assert share(row) == .25
    assert momentum(row) == pytest.approx(5)
    assert display_delta(momentum(row)) == '+5.0pp'
    for change in ({'wallet': {'amount': 0, 'currency': 'CNY'}},
                   {'capture': {'amount': None, 'currency': 'CNY'}},
                   {'capture': {'amount': 10, 'currency': 'USD'}},
                   {'capture': {'amount': 10, 'currency': 'CNY', 'unit': 'shares'}},
                   {'capture': {'amount': 10, 'currency': 'CNY', 'service': 'Other'}},
                   {'capture': {'amount': 10, 'currency': 'CNY', 'period': '2024'}}):
        bad = client(observations=[{**observation('2025', 100, 25), **change}], momentum='up')
        assert share(bad) is None
        assert momentum(bad) == 'up'
    assert share(client(observations=[observation('2025', 100, 0)])) == 0
    assert money(None) == '-'
    assert display_delta(None) == '-'
    assert momentum(client(observations=[observation('2024', 100, 20, 'USD'), observation('2025', 100, 25)])) is None
    assert momentum(client(observations=[observation('2024-12', 100, 20), observation('2025', 100, 25)])) is None


def test_aggregation():
    rows = [client('A', segment='Public fund', observations=[observation('2025', 100, 30)]),
            client('B', segment='Hedge fund', observations=[observation('2025', 100, 22)], value='Access'),
            client('C', segment='Insurance', observations=[observation('2025', 100, 20)]),
            client('D', segment='Other', observations=[observation('2025', 100, 28)])]
    assert aggregate(company(clients=rows)) == ('4', 'Public fund · Hedge fund', '25.0%', '-', 'Research')
    rows[3]['observations'][0]['capture']['amount'] = 10
    assert aggregate(company(clients=rows))[1] == 'Public fund · Hedge fund'
    assert aggregate(company(clients=[client(), client('B', observations=[observation('2025', 100, 50)], momentum='down')]))[3] == '+5.0pp'
    rows = [client(str(i), observations=[], momentum=m, value=None) for i, m in enumerate(('up', 'up', 'flat'))]
    assert aggregate(company(clients=rows))[3:] == ('↑', '-')
    rows.pop()
    rows[1]['momentum'] = 'down'
    assert aggregate(company(clients=rows))[3] == '-'
    rows = [client('same', service='A', segment='Z', observations=[], value='Trust'), client('same', service='B', segment='A', observations=[], value='Access')]
    assert aggregate(company(clients=rows)) == ('1', 'A · Z', '-', '-', 'Access')
    rows = [client('A', segment='A', observations=[observation('2025', 100, 50)]), client('B', segment='B', observations=[observation('2025', 100, 50)])]
    assert aggregate(company(clients=rows))[1] == 'A · B'  # strictly greater than 50%
    rows[0]['observations'][0]['capture']['amount'] = 60
    assert aggregate(company(clients=rows))[1] == 'A'


def test_matching_priorities():
    row = client(coverage=['Chips'], geography=['HK'], segment='Fund')
    jobs = [ApplicationRecord(id='1', company='A', job='Equities', coverage=['Chips']),
            ApplicationRecord(id='2', company='A', job='Other', service='Equities'),
            ApplicationRecord(id='3', company='A', job='Other', geography=['HK']),
            ApplicationRecord(id='4', company='A', job='Other', client_segment='Fund'),
            ApplicationRecord(id='5', company='A', job='Other', value='Research'),
            ApplicationRecord(id='6', company='A', job='Equities'),
            ApplicationRecord(id='7', company='A', job='Nothing')]
    assert [j.id for j in sorted(jobs, key=lambda j: relevance(j, row))] == ['2', '1', '3', '4', '5', '6', '7']
    other = dict(row, benefit='Nothing')
    assert relevance(jobs[-1], row) == relevance(jobs[-1], other)


def test_navigation_rendering_edit_delete(tmp_path):
    async def scenario():
        store = seed(tmp_path)
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(150, 35)) as pilot:
            screen = app.screen
            assert screen.view == 'company'
            assert 'CLIENTS' in screen.query_one(CompanyTable).render().plain
            await pilot.press('enter')
            assert screen.view == 'company'
            await pilot.press('right')
            assert screen.view == 'value'
            rendered = screen.query_one(CompanyTable).render().plain
            assert 'CAPTURE' in rendered and '25.0%' in rendered
            assert 'HIDDEN BENEFIT' not in rendered
            await pilot.press('d')
            assert screen.view == 'delivery'
            rendered = screen.query_one(CompanyTable).render().plain
            headers = [line for line in rendered.splitlines() if 'ENTITY' in line]
            assert len(headers) == 3 and len(set(headers)) == 1
            lines = [line for line in rendered.splitlines() if 'Detail ' in line]
            assert len({Text(line[:line.index('Detail')]).cell_len for line in lines}) == 1
            await pilot.press('right', 'right', 'ctrl+a', *'Named Person', 'enter')
            assert screen.selected()['entity'] == 'Named Person'
            await pilot.press('down', 'right', 'down', 'right')
            assert screen.selected()['type'] == 'Largest shareholder'
            await pilot.press('down', 'right', 'ctrl+a', *'20%', 'enter', 'left')
            assert screen.selected()['detail'] == '20%'
            await pilot.press('a', *'New Person', 'enter', 'down', 'right', 'down', 'right', 'left')
            assert len(resolve(store.companies(), 'co')['delivery']) == 4
            await pilot.press('d')
            assert isinstance(app.screen, ConfirmDelete)
            await pilot.press('n')
            assert len(resolve(store.companies(), 'co')['delivery']) == 4
            await pilot.press('d', 'y')
            assert len(resolve(store.companies(), 'co')['delivery']) == 3
            await pilot.press('v')
            assert screen.view == 'value'
            await pilot.press('j')
            assert isinstance(app.screen, HomeScreen)
            jobs = app.screen.query_one(ApplicationList).records
            assert [j.id for j in jobs] == ['a', 'b']
            await pilot.press('c')
            assert app.screen.view == 'value'
            assert app.screen.company['id'] == 'co'
            await pilot.press('left')
            assert app.screen.view == 'company'
    asyncio.run(scenario())


def test_empty_sections_search_space_and_resize(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.save_company(company(name='中' * 70, clients=[client('Long client ' * 30)], delivery=[]))
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(80, 14)) as pilot:
            screen = app.screen
            assert '…' in screen.query_one(CompanyTable).render().plain
            await pilot.press('space')
            assert 0 in screen.expanded
            await pilot.press('space', '/', *'missing')
            assert not screen.rows
            await pilot.press('escape', 'right', 'space')
            assert screen.view == 'value' and 0 in screen.expanded
            assert 'HIDDEN BENEFIT' not in screen.query_one(CompanyTable).render().plain
            await pilot.resize_terminal(100, 18)
            await pilot.press('d', 'down', 'a', *'Branch One', 'enter', 'down', 'right', 'down', 'down', 'right', 'left')
            assert resolve(store.companies(), 'co')['delivery'][0]['section'] == 'operate'
            await pilot.press('v', 'left')
            assert screen.view == 'company'
    asyncio.run(scenario())


def test_job_detail_c_and_empty_company(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='job', company='Empty Co', job='Role'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            assert isinstance(app.screen, HomeScreen)
            await pilot.press('right', 'c')
            assert isinstance(app.screen, CompanyScreen)
            assert app.screen.view == 'value' and app.screen.rows == []
    asyncio.run(scenario())


def test_launchers_and_shared_import_export(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(cli.platform, 'system', lambda: 'Darwin')
    launched = []
    monkeypatch.setattr(CareerApp, 'run', lambda self, **kw: launched.append((self.initial_root, self.store.metadata_path, kw)))
    cli.main([])
    cli.company_main([])
    assert [x[0] for x in launched] == ['job', 'company']
    assert launched[0][1:] == launched[1][1:]
    source = tmp_path / 'import.json'
    source.write_text(json.dumps({'jobs': [], 'companies': [company()]}))
    cli.company_main(['import', str(source)])
    out = tmp_path / 'export.json'
    cli.main(['export', str(out)])
    assert json.loads(out.read_text())['companies'][0]['id'] == 'co'
    scripts = tomllib.loads(Path('pyproject.toml').read_text())['project']['scripts']
    assert scripts['job'] == 'career_job_manager.cli:main'
    assert scripts['company'] == 'career_job_manager.cli:company_main'


def test_unknown_normalized_metadata_and_no_stored_share(tmp_path):
    store = CareerStore(tmp_path)
    row = client(share=.99)
    row['observations'][0]['share'] = .99
    store.import_jobs({'schema_version': 1, 'jobs': [{'id': 'one', 'company': 'Co', 'role': 'Role',
        'when': '2026-fall', 'extra': 'future', '_unknown': 'also future',
        'service': 'Equities', 'coverage': ['Chips'], 'future': {'one': 1}}], 'companies': [company(clients=[row])]})
    store.import_jobs({'schema_version': 1, 'jobs': [{'id': 'one', 'company': 'Co', 'role': 'Role',
        'when': '2026-fall', 'future': {'two': 2}, 'coverage': ['Energy']}]})
    saved = store.list()[0].to_dict()
    assert saved['future'] == {'one': 1, 'two': 2}
    assert saved['extra'] == 'future' and saved['_unknown'] == 'also future'
    assert saved['coverage'] == ['Chips', 'Energy']
    raw = store.export_data()['companies'][0]['clients'][0]
    assert 'share' not in raw and all('share' not in o for o in raw['observations'])
    assert raw['benefit'] == 'HIDDEN BENEFIT'


def test_reverse_matching_scroll_and_terminal_default(tmp_path):
    async def scenario():
        store = seed(tmp_path)
        co = resolve(store.companies(), 'co')
        co['clients'] = [client('Unrelated', service='Other'), client('Match', service='Equities')]
        co['delivery'] = [{'section': s, 'entity': f'{s} Person {i}', 'type': TYPES[s][0], 'detail': None}
                          for s in SECTIONS for i in range(10)]
        store.save_company(co)
        app = CareerApp(store)
        async with app.run_test(size=(110, 14)) as pilot:
            await pilot.press('c')
            screen = app.screen
            assert screen.rows[0]['client'] == 'Match'
            await pilot.press('space')
            assert not screen.expanded  # no physical truncation
            await pilot.press('d', *(['down'] * 29))
            await pilot.pause()
            assert screen.selected()['entity'] == 'source Person 9'
            strips = app.screen._compositor.render_strips()
            assert any('source Person 9' in strip.text for strip in strips)
            for strip in strips:
                for segment in strip:
                    if segment.style and segment.style.bgcolor:
                        assert segment.style.bgcolor.is_default
            await pilot.press('right', 'right', 'ctrl+a', *'qdvc text', 'enter', 'left')
            assert screen.selected()['entity'] == 'qdvc text'
    asyncio.run(scenario())


def test_stable_inferred_ids_and_weight_fallback():
    assert company_union([{'name': 'No ID'}], [])[0]['id'] == company_union([{'name': 'No ID'}], [])[0]['id']
    rows = [client('A', segment='Fund', value='Research', observations=[observation('2025', 100, 99, 'USD')]),
            client('B', segment='Insurer', value='Access', observations=[observation('2025', 100, 1, 'CNY')]),
            client('C', segment='Insurer', value='Access', observations=[observation('2025', 100, 1, 'CNY')])]
    assert aggregate(company(clients=rows))[1] == 'Insurer'
    assert aggregate(company(clients=rows))[-1] == 'Access'
    rows = [client('A', observations=[observation('2025', 100, 80)], value='Research'),
            client('B', observations=[observation('2025', 100, 10)], value='Access'),
            client('C', observations=[observation('2025', 100, 10)], value='Access')]
    assert aggregate(company(clients=rows))[-1] == 'Research'
    rows[0]['observations'].insert(0, observation('2024', 100, 70))
    rows[1]['observations'].insert(0, observation('2024', 100, 8))
    assert aggregate(company(clients=rows))[3] == '+6.0pp'
