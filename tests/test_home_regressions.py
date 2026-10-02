import asyncio

import pytest
from rich.cells import cell_len

from career_job_manager.model import ApplicationRecord, sort_records
from career_job_manager.presentation import render_home_lines
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp


@pytest.mark.parametrize('company,job', [
    ('CPIC', ''), ('CPIC', 'Analyst'), ('CPIC', 'Long role ' * 20),
    ('中国太平洋保险', '投资分析师' * 15), ('Cafe\u0301', '[bold]Analyst[/bold]'),
])
def test_home_columns_use_fixed_terminal_positions(tmp_path, company, job):
    async def scenario():
        app = CareerApp(CareerStore(tmp_path))
        async with app.run_test(size=(100, 20)) as pilot:
            widget = app.screen.query_one(ApplicationList)
            widget.set_records([ApplicationRecord(
                id='1', company=company, job=job, deadline='2026-09-21', action='Wait',
            )])
            await pilot.pause()
            header = widget.render_line(0).text
            row = widget.render_line(1).text
            for label, value in [('Deadline', '21 Sep'), ('Company', company), ('Action', 'Wait')]:
                assert cell_len(row[:row.index(value)]) == cell_len(header[:header.index(label)])
            if job:
                assert cell_len(row[:row.index(job[:4])]) == cell_len(header[:header.index('Program')])
            assert cell_len(row[:row.index('Wait')]) == 68
    asyncio.run(scenario())


def test_exact_deadline_and_fuzzy_periods_display_and_sort():
    records = [
        ApplicationRecord(id='fall', company='A', job='', when='2026-fall'),
        ApplicationRecord(id='range', company='A', job='', when='2026-09..2026-10'),
        ApplicationRecord(id='month', company='A', job='', when='2026-09'),
        ApplicationRecord(id='25', company='A', job='', deadline='2026-09-25'),
        ApplicationRecord(id='21', company='A', job='', deadline='2026-09-21', when='2026-fall'),
    ]
    ordered = sort_records(records)
    assert [r.id for r in ordered] == ['21', '25', 'month', 'range', 'fall']
    assert [line[2:18].strip() for line in render_home_lines(ordered)[1:]] == [
        '21 Sep', '25 Sep', '~Sep', '~Sep–Oct', '~Fall',
    ]
    assert records[-1].deadline == '2026-09-21'


@pytest.mark.parametrize('when,before,after', [
    ('2024-02', '2024-02-28', '2024-03-01'),
    ('2026-winter', '2027-02-27', '2027-03-01'),
    ('2026-12..2027-01', '2027-01-30', '2027-02-01'),
])
def test_fuzzy_period_sorts_after_all_exact_deadlines(when, before, after):
    records = [ApplicationRecord(id='fuzzy', company='A', job='', when=when),
               ApplicationRecord(id='before', company='A', job='', deadline=before),
               ApplicationRecord(id='after', company='A', job='', deadline=after)]
    assert [r.id for r in sort_records(records)] == ['before', 'after', 'fuzzy']


def test_normal_screen_background_uses_terminal_default(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.add(ApplicationRecord(id='1', company='CPIC', job='Analyst'))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            async def check_background():
                await pilot.pause()
                strips = app.screen._compositor.render_strips()
                for strip in strips:
                    for segment in strip:
                        if segment.style and segment.style.bgcolor:
                            assert segment.style.bgcolor.is_default
            await check_background()
            await pilot.press('/')
            await check_background()
            await pilot.press('escape', 'right')
            await check_background()
            await pilot.press('left', 'd')
            await check_background()
    asyncio.run(scenario())


@pytest.mark.parametrize('search', [False, True])
def test_arrows_traverse_entire_home_viewport(tmp_path, search):
    async def scenario():
        store = CareerStore(tmp_path)
        for index in range(24):
            store.add(ApplicationRecord(id=str(index), company=f'Company {index:02}',
                                        job='Analyst', deadline='2026-10-31'))
        app = CareerApp(store)
        async with app.run_test(size=(100, 12)) as pilot:
            widget = app.screen.query_one(ApplicationList)
            if search:
                await pilot.press('/')
            for direction, indices in [('down', range(1, 24)), ('up', range(22, -1, -1))]:
                for index in indices:
                    await pilot.press(direction)
                    assert widget.selected().id == str(index)
                    visible = [widget.render_line(y).text for y in range(widget.size.height)]
                    assert 'Deadline' in visible[0]
                    assert any('>' in line and f'Company {index:02}' in line for line in visible[1:])
            await pilot.press(*(['down'] * 23))
            await pilot.resize_terminal(100, 9)
            await pilot.pause()
            assert any('Company 23' in widget.render_line(y).text for y in range(widget.size.height))
            if search:
                await pilot.press('enter')
            await pilot.press('right')
            assert app.screen.record_id == '23'
            await pilot.press('left', '/')
            await pilot.press(*'missing')
            assert widget.selected() is None
            assert 'No applications' in widget.render().plain
            await pilot.press('escape')
            assert widget.selected().id == '0'
            assert 'Company 00' in widget.render_line(1).text
    asyncio.run(scenario())


def test_exact_deadlines_precede_fuzzy_period_end_including_times():
    records = [
        ApplicationRecord(id='month', company='A', job='Role', when='2026-10'),
        ApplicationRecord(id='time', company='Nomura', job='Role', deadline='2026-10-31 23:55'),
        ApplicationRecord(id='day', company='HSBC', job='Role', deadline='2026-10-31'),
        ApplicationRecord(id='next', company='PG', job='Role', deadline='2026-11-02'),
    ]
    ordered = sort_records(records)
    assert [r.id for r in ordered] == ['day', 'time', 'next', 'month']
    assert [line[2:18].strip() for line in render_home_lines(ordered)[1:]] == [
        '31 Oct', '31 Oct 23:55', '2 Nov', '~Oct',
    ]


@pytest.mark.parametrize('action,color', [
    ('Check', 'white'), ('Archive', 'white'), ('Apply', 'green'),
    ('Email', 'green'), ('Go', 'red'), ('Take', 'red'), ('Wait', 'green'),
])
def test_home_colors_only_action_text(tmp_path, action, color):
    from rich.color import Color

    async def scenario():
        app = CareerApp(CareerStore(tmp_path))
        async with app.run_test(size=(100, 12)) as pilot:
            widget = app.screen.query_one(ApplicationList)
            # Repeated labels and wide characters must not color other columns.
            widget.set_records([ApplicationRecord(
                id='1', company='中' + action, job=action, action=action,
            )])
            await pilot.pause()
            rendered = widget.render()
            start = rendered.plain.rindex(action)
            for index in range(len(rendered.plain)):
                expected = Color.parse(color) if color and start <= index < start + len(action) else None
                style = rendered.get_style_at_offset(app.console, index)
                assert style.color == expected
                assert not style.bold
                assert style.bgcolor is None
    asyncio.run(scenario())
