import asyncio
import json

import pytest

from career_job_manager import cli
from career_job_manager.model import ApplicationRecord
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp, FieldRow, HomeScreen


@pytest.mark.parametrize('legacy, expected', [
    ({'status': 'Applied', 'action': 'Email'}, 'Email'),
    ({'status': 'Interview', 'action': 'Apply'}, 'Apply'),
    ({'status': 'Assessment'}, 'Take'),
    ({'status': 'Interview', 'action': 'Attend'}, 'Go'),
])
def test_legacy_action_migration(tmp_path, legacy, expected):
    store = CareerStore(tmp_path)
    data = {'id': 'old', 'company': 'X', 'job': 'Y', 'target': 'hr@example.com', **legacy}
    store.metadata_path.write_text(json.dumps({'version': 5, 'applications': [data]}))
    assert store.get('old').action == expected
    store.update('old', {'contact': 'Jane'})
    saved = json.loads(store.metadata_path.read_text())['jobs'][0]
    assert saved['action'] == expected
    assert 'status' not in saved
    assert saved['target'] == 'hr@example.com'


@pytest.mark.parametrize('flags', [('-C', '-R', '-D'), ('--company', '--role', '--deadline')])
def test_cli_creates_without_ui(tmp_path, monkeypatch, capsys, flags):
    monkeypatch.setenv('HOME', str(tmp_path))
    def no_ui(*args, **kwargs):
        pytest.fail('creation opened UI')
    monkeypatch.setattr(cli.CareerApp, 'run', no_ui)
    cli.main([flags[0], 'X', flags[1], 'Y', flags[2], '2026-10-01'])
    record = CareerStore().list()[0]
    assert (record.company, record.job, record.deadline, record.action) == ('X', 'Y', '2026-10-01', 'Apply')
    assert 'Created' in capsys.readouterr().out


@pytest.mark.parametrize('args', [['-C', 'X'], ['-C', '', '-R', 'Y', '-D', '2026-10-01'], ['-C', 'X', '-R', 'Y', '-D', 'bad'], ['-C', 'X', '-R', 'Y', '-D', '']])
def test_cli_invalid(tmp_path, monkeypatch, capsys, args):
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    assert 'error:' in capsys.readouterr().err
    assert CareerStore().list() == []


def test_plain_cli_opens_ui(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(cli.platform, 'system', lambda: 'Darwin')
    launched = []
    monkeypatch.setattr(cli.CareerApp, 'run', lambda self, **kwargs: launched.append(self))
    cli.main([])
    assert len(launched) == 1


def test_direct_form_email_and_wrapping(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord.from_dict({'id': '1', 'company': 'X', 'job': 'Y', 'status': 'Application', 'action': 'Apply', 'portal': 'https://example.com/' + 'long-path/' * 30, 'description_text': ('long description ' * 30) + '\nLAST LINE [literal]'}))
        app = CareerApp(store)
        async with app.run_test(size=(80, 40)) as pilot:
            await pilot.press('right')
            await pilot.pause()
            screen = app.screen
            assert 'Status' not in [row.field for row in screen.query(FieldRow)]
            for field in ('Company', 'Job', 'Deadline', 'Target', 'Portal', 'Contact', 'DescriptionText'):
                row = screen._row(field)
                row.focus()
                await pilot.pause()
                original = row.value
                await pilot.press('right', 'z' if field != 'Deadline' else '2')
                assert row.editor.value == ('z' if field != 'Deadline' else '2') + original
                await pilot.press('backspace', 'enter', 'down')
                if field != 'DescriptionText':
                    assert screen.focused is not row
            assert screen._row('Portal').size.height == 1
            desc = screen._row('DescriptionText')
            assert list(screen.query(FieldRow))[-1] is desc
            assert desc.size.height == 1
            await pilot.press('right')
            assert desc.size.height > 6
            assert 'LAST LINE [literal]' in desc.render().plain
            screen._row('Action').focus()
            await pilot.press('right', 'down', 'enter')
            assert screen.values['Action'] == 'Email'
            target = screen._row('Target')
            target.focus()
            await pilot.pause()
            await pilot.press('right', *list('hr@example.com'), 'enter', 'left')
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            saved = store.get('1')
            assert (saved.action, saved.target) == ('Email', 'hr@example.com')
            assert 'Email' in app.screen.query_one('#applications').render()
            await pilot.press('right')
            await pilot.pause()
            assert app.screen.values['Action'] == 'Email'
    asyncio.run(scenario())


def test_small_terminal_description_scroll_and_validation_recovery(tmp_path):
    async def scenario():
        app = CareerApp(CareerStore(tmp_path))
        async with app.run_test(size=(50, 16)) as pilot:
            await pilot.press('a', 'left')  # Blank form fails validation.
            await pilot.press('X', 'enter', 'down', 'right', 'Y', 'enter', 'down')
            await pilot.pause()
            screen = app.screen
            assert screen.focused.field == 'Deadline'
            desc = screen._row('DescriptionText')
            desc.focus()
            await pilot.pause()
            await pilot.press('right')
            from textual.events import Paste
            desc.post_message(Paste(('readable line\n' * 70) + 'FINAL LINE'))
            await pilot.pause()
            assert desc.size.height >= 71
            scroll = screen.query_one('#form-list')
            assert scroll.scroll_y == scroll.max_scroll_y
            await pilot.press('home')
            await pilot.pause()
            before = scroll.scroll_y
            await pilot.press(*(['down'] * 70))
            await pilot.pause()
            assert scroll.scroll_y > before
            assert scroll.scroll_y == scroll.max_scroll_y
            await pilot.press('enter', 'left')
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            saved = app.store.list()[0]
            assert saved.company == 'X'
            assert saved.job == 'Y'
            assert saved.description_text.endswith('FINAL LINE')
    asyncio.run(scenario())


def test_legacy_free_text_action_retained(tmp_path):
    store = CareerStore(tmp_path)
    store.metadata_path.write_text(json.dumps({'version': 1, 'applications': [{
        'id': 'old', 'company': 'X', 'job': 'Y', 'status': 'Assessment',
        'action': 'Complete online test', 'apply': 'https://portal.example',
    }]}))
    record = store.get('old')
    assert (record.action, record.target, record.portal) == ('Take', 'Complete online test', 'https://portal.example')
    store.update('old', {'action': 'Email', 'target': 'hr@example.com'})
    assert store.get('old').action == 'Email'
