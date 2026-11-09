"""Initial date selection must not leak into detail-return restoration."""
import asyncio
from datetime import date

import pytest

from career_job_manager import model, ui
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationList, CareerApp, HomeScreen


@pytest.fixture
def clock(monkeypatch):
    class Clock(date):
        current = date(2026, 10, 18)

        @classmethod
        def today(cls):
            return cls.current

    monkeypatch.setattr(ui, 'date', Clock, raising=False)
    monkeypatch.setattr(model, 'date', Clock, raising=False)
    return Clock


@pytest.mark.parametrize("rows", [
    [{"deadline": "2026-10-17"}, {"deadline": "2026-10-19"},
     {"deadline": "2026-10-20"}],
    [{"deadline": "2026-10-18 23:59"}, {"deadline": "2026-10-19 00:01"}],
    [{"next": "ASAP", "deadline": "2026-12-01"}, {"deadline": "2026-10-19"}],
    [{"deadline": "2026-10-17"}, {"when": "2026-11"},
     {"deadline": "2026-12-01"}],
    [{"when": "2026-10"}, {"when": "2026-fall"}, {"when": "2026-winter"}],
    [],
])
def test_initial_date_selection(tmp_path, clock, rows):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({"jobs": [dict(id=str(i), company=f"Company {i}",
                                       job="Role", **row)
                                    for i, row in enumerate(rows)]})
        order = [r.id for r in store.list()]
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.pause()
            selected = app.screen.selected_record()
            assert (selected.id if selected else None) == (order[0] if order else None)
            assert [r.id for r in app.screen.visible_records] == order
    asyncio.run(scenario())


def test_creation_clock_initial_viewport_and_detail_return(tmp_path, clock):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [
            {'id': str(i), 'company': f'Company {i:02}', 'job': 'Role',
             'deadline': f'2026-10-{i + 1:02}'} for i in range(31)]})
        app = CareerApp(store)
        async with app.run_test(size=(100, 14)) as pilot:
            home = app.screen
            widget = home.query_one(ApplicationList)
            await pilot.pause()
            assert widget.selected().id == store.list()[0].id
            assert widget.first_visible == 0
            widget.move(3)
            await pilot.pause()
            previous = widget.selected_index, widget.first_visible
            selected_before = widget.selected().id
            await pilot.press('right')
            clock.current = date(2026, 10, 25)
            await pilot.press('left')
            await pilot.pause()
            assert app.screen is home
            assert widget.selected().id == selected_before
            assert (widget.selected_index, widget.first_visible) == previous
            # A genuinely new screen gets today's new date, even in the same app.
            await app.push_screen(HomeScreen(store))
            await pilot.pause()
            fresh = app.screen.query_one(ApplicationList)
            assert fresh.selected().id == store.list()[0].id
            assert fresh.first_visible == 0
    asyncio.run(scenario())


def test_expired_wait_appears_after_today_and_is_initially_selected(tmp_path, clock):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [
            {'id': 'old', 'company': 'A', 'job': 'Role',
             'deadline': '2026-10-01', 'action': 'Apply'},
            {'id': 'waiting', 'company': 'B', 'job': 'Role',
             'deadline': '2026-09-15', 'action': 'Wait'},
            {'id': 'future', 'company': 'C', 'job': 'Role',
             'deadline': '2026-10-20', 'action': 'Apply'},
        ]})
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [r.id for r in app.screen.visible_records] == [
                'waiting', 'future', 'old',
            ]
            assert app.screen.selected_record().id == 'waiting'
            assert store.get('waiting').deadline == '2026-09-15'
            clock.current = date(2026, 10, 25)
            await app.push_screen(HomeScreen(store))
            await pilot.pause()
            assert [r.id for r in app.screen.visible_records] == [
                'waiting', 'old', 'future',
            ]
            assert app.screen.selected_record().id == 'waiting'
    asyncio.run(scenario())
