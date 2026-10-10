import json

from career_job_manager import cli


def test_company_merge_reporting(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HOME', str(tmp_path))
    path = tmp_path / 'import.json'

    def run(company, expected):
        path.write_text(json.dumps({'companies': [company]}))
        cli.company_main(['import', str(path)])
        assert capsys.readouterr().out == expected + '\n'

    company = {'id': 'co', 'name': 'Company', 'aliases': ['Alias'], 'clients': []}
    run(company, 'Companies: 1 created, 0 updated.')
    run(company, 'Companies: 0 created, 0 updated.')
    run({**company, 'future': 'changed'}, 'Companies: 0 created, 1 updated.')
    run({'id': 'different', 'name': 'Alias'}, 'Companies: 0 created, 1 updated.')
    run({'id': 'different', 'name': 'Alias'}, 'Companies: 0 created, 0 updated.')


def test_job_and_mixed_reporting(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HOME', str(tmp_path))
    path = tmp_path / 'import.json'

    def run(payload, expected):
        path.write_text(json.dumps(payload))
        cli.main(['import', str(path)])
        assert capsys.readouterr().out == expected

    job = {'id': 'one', 'company': 'A', 'job': 'Analyst'}
    companies = [{'id': 'a', 'name': 'A'}, {'id': 'b', 'name': 'B'}]
    run({'jobs': [job], 'companies': companies},
        'Jobs: 1 created, 0 updated.\nCompanies: 2 created, 0 updated.\n')
    jobs = [{**job, 'job': 'Changed'}, {**job, 'id': 'two'}, {**job, 'id': 'three'}]
    run({'jobs': jobs}, 'Jobs: 2 created, 1 updated.\n')
    run({'jobs': jobs}, 'Jobs: 0 created, 0 updated.\n')
    jobs = [{**job, 'job': 'Changed again'}, {**job, 'id': 'four'}, {**job, 'id': 'five'}]
    run({'jobs': jobs, 'companies': [dict(c, future=True) for c in companies] + [{'name': 'C'}]},
        'Jobs: 2 created, 1 updated.\nCompanies: 1 created, 2 updated.\n')


def test_counts_follow_nested_merges_and_protected_fields(tmp_path):
    from career_job_manager.store import CareerStore

    store = CareerStore(tmp_path)
    company = {'id': 'co', 'name': 'Company', 'clients': [
        {'client': 'Client', 'period': '2025', 'engagement': 'Research'}],
        'franchise': [{'entity': 'Branch', 'footprint': 'Old'}]}
    assert store.import_jobs({'companies': [company]}).companies == (1, 0)
    changed = {**company, 'clients': [
        {'client': 'Client', 'period': '2025', 'engagement': 'Advisory'}],
        'franchise': [{'entity': 'Branch', 'footprint': 'New'}]}
    assert store.import_jobs({'companies': [changed]}).companies == (0, 1)
    assert store.import_jobs({'companies': [changed]}).companies == (0, 0)
    job = {'id': 'job', 'company': 'Company', 'job': 'Analyst', 'action': 'Check'}
    assert store.import_jobs({'jobs': [job]}).jobs == (1, 0)
    assert store.import_jobs({'jobs': [{**job, 'action': 'Apply', 'folder_name': 'ignored'}]}).jobs == (0, 0)
