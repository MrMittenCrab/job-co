"""Initial date selection must not leak into detail-return restoration."""
import asyncio
from datetime import date

import pytest

from career_job_manager import ui
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
    return Clock


@pytest.mark.parametrize('rows, expected', [
    ([{'deadline': '2026-10-17'}, {'deadline': '2026-10-19'},
      {'deadline': '2026-10-20'}], '1'),
    ([{'deadline': '2026-10-18 23:59'}, {'deadline': '2026-10-19 00:01'}], '1'),
    ([{'deadline': '2026-10-17'}, {'deadline': '2026-10-19', 'action': 'Check'},
      {'deadline': '2026-10-20'}], '1'),
    ([{'deadline': '2026-10-17'}, {'deadline': '2026-10-19 23:59'},
      {'deadline': '2026-10-19'}], '2'),
    ([{'deadline': '2026-10-17'}, {'when': '2026-11'},
      {'deadline': '2026-12-01'}], '2'),
    ([{'deadline': '2026-10-17'}, {'when': '2026-12'},
      {'when': '2026-11..2026-12'}, {'when': '2027-spring'}], '2'),
    ([{'when': '2026-10'}, {'when': '2026-fall'}, {'when': '2026-winter'}], '2'),
    ([{'deadline': '2026-10-17', 'when': '2027-spring'},
      {'deadline': '2026-10-18'}], '0'),
    ([], None),
])
def test_initial_date_selection(tmp_path, clock, rows, expected):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'jobs': [dict(id=str(i), company=f'Company {i}', job='Role', **row)
                                    for i, row in enumerate(rows)]})
        order = [r.id for r in store.list()]
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.pause()
            selected = app.screen.selected_record()
            assert (selected.id if selected else None) == expected
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
            assert widget.selected().id == '18'
            assert widget.first_visible == 18
            widget.move(3)
            await pilot.pause()
            previous = widget.selected_index, widget.first_visible
            await pilot.press('right')
            clock.current = date(2026, 10, 25)
            await pilot.press('left')
            await pilot.pause()
            assert app.screen is home
            assert widget.selected().id == '21'
            assert (widget.selected_index, widget.first_visible) == previous
            # A genuinely new screen gets today's new date, even in the same app.
            await app.push_screen(HomeScreen(store))
            await pilot.pause()
            fresh = app.screen.query_one(ApplicationList)
            assert fresh.selected().id == '25'
            assert fresh.first_visible == min(25, 31 - max(1, fresh.content_size.height - 1))
    asyncio.run(scenario())
