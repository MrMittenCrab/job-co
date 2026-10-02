import asyncio
import json
from unittest.mock import Mock

import pytest

from career_job_manager.model import ACTIONS, ApplicationRecord, sort_records
from career_job_manager.presentation import FILE_FIELDS, FORM_FIELDS, DESCRIPTION_TEXT_FIELD, TEXT_FIELDS
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp, HomeScreen


def test_action_group_precision_and_chronology():
    periods = ['2029-09-21', '2028-09', '2027-09..2027-10', '2026-fall']
    records = [ApplicationRecord(id=f'{action}-{i}', company='X', job='Y',
                                 action=action, when=period)
               for action in ACTIONS for i, period in enumerate(periods)]
    ordered = sort_records(records[::-1])
    assert all(r.action != 'Check' for r in ordered[:-4])
    assert all(r.action == 'Check' for r in ordered[-4:])
    assert [periods.index(r.when) for r in ordered[:-4]] == sorted(periods.index(r.when) for r in ordered[:-4])
    assert [r.when for r in ordered[-4:]] == periods


@pytest.mark.parametrize('earlier,later', [
    ('2026-09-21', '2026-09-22'), ('2026-09', '2026-10'),
    ('2026-08..2026-12', '2026-09..2026-10'), ('2026-fall', '2026-winter'),
])
def test_chronology_within_precision_ignores_non_check_action(earlier, later):
    records = [
        ApplicationRecord(id='later', company='A', job='Y', action='Apply', when=later),
        ApplicationRecord(id='earlier', company='Z', job='Y', action='Archive', when=earlier),
    ]
    assert [r.id for r in sort_records(records)] == ['earlier', 'later']


@pytest.mark.parametrize('import_id', ['', 'external-job'])
@pytest.mark.parametrize('exists', [True, False])
def test_legacy_brochure_migration_preserves_description_and_is_idempotent(tmp_path, import_id, exists):
    store = CareerStore(tmp_path)
    row = dict(id='1', company='X', job='Y', deadline='2026-09-21',
               description='X_Y_Description.pdf', description_text='  Text\n\n中文  ',
               action='Check', import_id=import_id)
    folder = store.applications_dir / ('X_Y__1' if import_id else 'X_Y')
    folder.mkdir()
    if exists:
        (folder / row['description']).write_bytes(b'legacy document')
    store.metadata_path.write_text(json.dumps({'version': 7, 'applications': [row]}))
    record = store.get('1')
    assert record.description_text == row['description_text']
    folder = store._folder(record)
    assert record.brochure == ('X_Y_Brochure.pdf' if exists else row['description'])
    if exists:
        assert (folder / record.brochure).read_bytes() == b'legacy document'
        assert not (folder / row['description']).exists()
    saved = json.loads(store.metadata_path.read_text())
    assert 'description' not in saved['jobs'][0]
    before = store.metadata_path.read_bytes()
    assert store.get('1') == record
    assert store.metadata_path.read_bytes() == before
    assert FORM_FIELDS[-1] == DESCRIPTION_TEXT_FIELD
    assert DESCRIPTION_TEXT_FIELD in TEXT_FIELDS
    assert DESCRIPTION_TEXT_FIELD not in FILE_FIELDS


@pytest.mark.parametrize('kind', FILE_FIELDS)
def test_document_options_navigation_view_and_choose(tmp_path, monkeypatch, kind):
    async def scenario():
        store = CareerStore(tmp_path / 'store')
        store.add(ApplicationRecord(id='1', company='X', job='Y'))
        picker = Mock(return_value=None)
        reveal = Mock()
        monkeypatch.setattr('career_job_manager.ui.choose_file', picker)
        monkeypatch.setattr('career_job_manager.ui.reveal_file', reveal)
        app = CareerApp(store)
        async with app.run_test(size=(70, 22)) as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row(kind)
            row.focus()
            await pilot.pause()
            assert row.size.height == 1
            assert row.render().plain.strip() == f'> {kind:<12} View    Choose'
            await pilot.press('right', 'enter')  # Missing View is clean.
            reveal.assert_not_called()
            assert app.screen is screen
            await pilot.press('right', 'left')
            assert row.document_option == 0
            picker.assert_not_called()
            await pilot.press('right', 'enter')
            picker.assert_called_once()
            for index, extension in enumerate(('.pdf', '.docx')):
                source = tmp_path / f'source{extension}'
                source.write_bytes(f'bytes {index}'.encode())
                before = source.stat().st_mtime_ns
                picker.return_value = source
                await pilot.press('enter')
                record = store.get('1')
                managed = store._folder(record) / getattr(record, kind.lower())
                assert managed.name == f'X_Y_{kind}{extension}'
                assert managed.read_bytes() == source.read_bytes()
                assert source.stat().st_mtime_ns == before
                await pilot.press('left', 'enter')
                reveal.assert_called_with(managed)
                assert app.screen is screen
                await pilot.press('right')
            await pilot.press('down')
            assert screen.focused is not row
            await pilot.press('up')
            assert screen.focused is row
            assert len(list(store._folder(record).iterdir())) == 1
            screen._row('Company').focus()
            await pilot.pause()
            await pilot.press('left')
            assert isinstance(app.screen, HomeScreen)
    asyncio.run(scenario())


def test_view_reveals_managed_location_without_changing_file(tmp_path, monkeypatch):
    from career_job_manager.filepicker import reveal_file
    managed = tmp_path / 'managed.pdf'
    managed.write_bytes(b'unchanged')
    run = Mock()
    monkeypatch.setattr('career_job_manager.filepicker.platform.system', lambda: 'Darwin')
    monkeypatch.setattr('career_job_manager.filepicker.subprocess.run', run)
    reveal_file(managed)
    assert run.call_args.args[0] == ['open', '-R', str(managed.resolve())]
    assert managed.read_bytes() == b'unchanged'
    with pytest.raises(ValueError, match='No managed file'):
        reveal_file(tmp_path / 'missing.pdf')


def test_choose_on_new_job_creates_managed_copy_immediately(tmp_path, monkeypatch):
    async def scenario():
        source = tmp_path / 'source.pdf'
        source.write_bytes(b'new brochure')
        store = CareerStore(tmp_path / 'store')
        monkeypatch.setattr('career_job_manager.ui.choose_file', lambda _: source)
        reveal = Mock()
        monkeypatch.setattr('career_job_manager.ui.reveal_file', reveal)
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('a')
            screen = app.screen
            screen.finish_inline_edit('Company', 'X')
            screen.finish_inline_edit('Job', 'Y')
            screen._row('Brochure').focus()
            await pilot.pause()
            await pilot.press('right', 'right', 'enter')
            record = store.list()[0]
            managed = store._folder(record) / record.brochure
            assert managed.read_bytes() == source.read_bytes() == b'new brochure'
            assert managed != source
            await pilot.press('left', 'enter')
            reveal.assert_called_once_with(managed)
            assert app.screen is screen
    asyncio.run(scenario())


@pytest.mark.parametrize('kind', FILE_FIELDS)
def test_document_left_boundary_returns_to_same_job_field(tmp_path, monkeypatch, kind):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='X', job='Y'))
        picker = Mock()
        reveal = Mock()
        monkeypatch.setattr('career_job_manager.ui.choose_file', picker)
        monkeypatch.setattr('career_job_manager.ui.reveal_file', reveal)
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row(kind)
            row.focus()
            await pilot.pause()
            assert row.document_option is None
            await pilot.press('right')
            assert row.document_option == 0
            await pilot.press('right', 'right')
            assert row.document_option == 1
            await pilot.press('left')
            assert row.document_option == 0
            await pilot.press('left')
            assert app.screen is screen
            assert screen.focused is row
            assert row.document_option is None
            rendered = row.render()
            for option in ('View', 'Choose'):
                assert not rendered.get_style_at_offset(app.console, rendered.plain.index(option)).underline
            # Normal Job navigation resumes, and returning does not reopen options.
            await pilot.press('down', 'up')
            assert screen.focused is row
            assert row.document_option is None
            await pilot.press('right')
            assert row.document_option == 0
            await pilot.press('left')
            assert screen.focused is row
            assert row.document_option is None
            picker.assert_not_called()
            reveal.assert_not_called()
            # A subsequent Left in normal Job mode returns to Home.
            await pilot.press('left')
            assert isinstance(app.screen, HomeScreen)
    asyncio.run(scenario())
