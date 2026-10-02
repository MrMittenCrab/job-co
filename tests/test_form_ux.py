import asyncio

import pytest

from career_job_manager.model import ApplicationRecord
from career_job_manager.presentation import FORM_FIELDS, selector_options
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp, HomeScreen


def test_wrapped_values_share_column_after_resize_without_changing_storage(tmp_path):
    raw = 'A long description that wraps naturally across several lines. ' * 8 + '\nExplicit newline\n\n最後一行 [literal]'
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst', portal='https://example.com/' + 'path/' * 40, description_text=raw))
        app = CareerApp(store)
        async with app.run_test(size=(70, 30)) as pilot:
            await pilot.press('right', 'down', 'down')
            screen = app.screen
            for width in (70, 45, 95):
                await pilot.resize_terminal(width, 30)
                await pilot.pause()
                for field in ('Company', 'Job', 'Portal', 'DescriptionText'):
                    row = screen._row(field)
                    lines = [row.render_line(y).text for y in range(row.size.height)]
                    assert lines[0][15:].strip()
                    for line in lines[1:]:
                        assert line[:15] == ' ' * 15
                    if field in ('Portal', 'DescriptionText'):
                        assert len(lines) == 1
                        assert '…' in lines[0]
                desc = screen._row('DescriptionText')
                desc.focus()
                await pilot.pause()
                await pilot.press('right')
                assert desc.size.height > 1
                for y in range(1, desc.size.height):
                    assert desc.render_line(y).text[:15] == ' ' * 15
                screen._row('Deadline').focus()
                await pilot.pause()
            await pilot.press('left')
            assert store.get('1').description_text == raw
    asyncio.run(scenario())


@pytest.mark.parametrize('field', ['Company', 'Job', 'Deadline', 'Target', 'Portal', 'Contact', 'DescriptionText'])
def test_text_context_keyboard(tmp_path, field):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            home = app.screen
            await pilot.press('enter')
            assert app.screen is home
            await pilot.press('right')
            screen = app.screen
            assert screen.focused is screen._row('Company')
            assert not screen.focused.editing
            await pilot.press('down')
            assert screen.focused is screen._row('Job')
            await pilot.press('up')
            assert screen.focused is screen._row('Company')
            row = screen._row(field)
            row.focus()
            await pilot.pause()
            assert not row.editing
            await pilot.press('right')
            assert row.editing
            await pilot.press('ctrl+a', 'a', 'b', 'left')
            assert row.editor.cursor == 1
            await pilot.press('right')
            assert row.editor.cursor == 2
            assert app.screen is screen
            await pilot.press('enter')
            assert not row.editing
            assert screen.values[field] == 'ab'
            assert app.screen is screen
            # Restore a valid deadline before saving the whole form.
            if field == 'Deadline':
                await pilot.press('right', 'ctrl+a', 'backspace', 'enter')
            await pilot.press('left')
            assert app.screen is home
    asyncio.run(scenario())


@pytest.mark.parametrize('open_key', ['right'])
@pytest.mark.parametrize('close_key', ['enter', 'right', 'left'])
def test_choice_context_keyboard(tmp_path, open_key, close_key):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right', 'down', 'down', 'down', open_key)
            screen = app.screen
            row = screen._row('Action')
            assert row.selector_open
            assert row.selector_options == ('Apply', 'Email', 'Wait', 'Go', 'Take', 'Check', 'Archive')
            await pilot.press('down', 'down', 'up')
            assert row.selected_option() == 'Email'
            assert '> Email' in row.render().plain
            assert row.value == 'Apply'
            await pilot.press(close_key)
            assert not row.selector_open
            assert app.screen is screen
            assert screen.focused is row
            assert row.value == ('Apply' if close_key == 'left' else 'Email')
            await pilot.press('left')
            assert isinstance(app.screen, HomeScreen)
            assert store.get('1').action == row.value
    asyncio.run(scenario())


@pytest.mark.parametrize('width', [45, 70])
def test_description_full_wrapped_navigation_and_cursor_visibility(tmp_path, width):
    from textual.containers import VerticalScroll
    raw = ('Wrapped description with 中文 and several words. ' * 8 + '\n\n') * 8 + 'Final line'
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst', description_text=raw))
        app = CareerApp(store)
        async with app.run_test(size=(width, 12)) as pilot:
            await pilot.press('right')
            screen = app.screen
            row = screen._row('DescriptionText')
            row.focus()
            await pilot.pause()
            await pilot.press('right', 'home')
            viewport = screen.query_one(VerticalScroll)
            def cursor_visible():
                line = next(i for i, text in enumerate(row._value_lines()) if text.spans)
                region = viewport.scrollable_content_region
                assert region.y <= row.region.y + line < region.bottom
            cursor_visible()
            for direction in ('down', 'up'):
                last = row.editor.cursor
                for _ in range(row.size.height + 5):
                    line = next(i for i, text in enumerate(row._value_lines()) if text.spans)
                    if direction == 'up' and line == 0:
                        break
                    await pilot.press(direction)
                    cursor_visible()
                    current = row.editor.cursor
                    assert current >= last if direction == 'down' else current <= last
                    last = current
                if direction == 'down':
                    assert row.editor.cursor >= len(raw) - len('Final line')
                    assert viewport.scroll_y > 0
                    await pilot.resize_terminal(width + 5, 14)
                    cursor_visible()
                else:
                    assert row.editor.cursor < width
            await pilot.press('enter')
            assert not row.editing
            assert app.screen is screen
            await pilot.press('left')
            assert store.get('1').description_text == raw
    asyncio.run(scenario())


@pytest.mark.parametrize('action,color', [('Apply','green'), ('Email','green'), ('Wait','green'), ('Go','red'), ('Take','red'), ('Check','white'), ('Archive','white')])
def test_action_field_and_dropdown_text_colors_only(tmp_path, action, color):
    from rich.color import Color
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst', action=action))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('right')
            row = app.screen._row('Action')
            row.focus()
            await pilot.pause()
            for dropdown in (False, True):
                if dropdown:
                    await pilot.press('right')
                rendered = row.render()
                for offset in range(len(rendered)):
                    style = rendered.get_style_at_offset(app.console, offset)
                    assert not style.bold
                    assert style.bgcolor is None
                start = rendered.plain.index(action, 15)
                assert rendered.get_style_at_offset(app.console, start).color == Color.parse(color)
                if dropdown:
                    colors = dict(zip(selector_options('Action'), ['green','green','green','red','red','white','white']))
                    for option, expected in colors.items():
                        start = rendered.plain.rindex(option)
                        assert rendered.get_style_at_offset(app.console, start).color == Color.parse(expected)
    asyncio.run(scenario())


@pytest.mark.parametrize('kind', ['Resume', 'Letter', 'Form', 'Brochure'])
def test_document_picker_copies_replaces_and_references_managed_file(tmp_path, monkeypatch, kind):
    from career_job_manager.naming import application_stem
    async def scenario():
        store = CareerStore(tmp_path / 'store')
        store.add(ApplicationRecord(id='1', company='HSBC', job='Analyst'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            for index, extension in enumerate(['.pdf', '.pdf', '.docx']):
                source = tmp_path / f'source-{index}{extension}'
                payload = bytes([index]) + b'document bytes'
                source.write_bytes(payload)
                before = source.stat()
                monkeypatch.setattr('career_job_manager.ui.choose_file', lambda _: source)
                await pilot.press('right')
                app.screen._row(kind).focus()
                await pilot.pause()
                await pilot.press('right', 'right', 'enter')
                app.screen._row('Company').focus()
                await pilot.pause()
                await pilot.press('left')
                assert isinstance(app.screen, HomeScreen)
                assert source.read_bytes() == payload
                assert source.stat().st_mtime_ns == before.st_mtime_ns
                record = CareerStore(store.root).get('1')
                name = getattr(record, kind.lower())
                folder = store._folder(record)
                assert name == f'HSBC_Analyst_{kind}{extension}'
                assert (folder / name).read_bytes() == payload
                assert list(folder.iterdir()) == [folder / name]
    asyncio.run(scenario())
