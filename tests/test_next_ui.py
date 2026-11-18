"""Current user contract: Action, Next, Deadline at top of job detail."""
import asyncio
from datetime import date

from career_job_manager.model import ApplicationRecord, default_next
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp


def test_detail_keeps_automatic_next_for_priority_actions(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(ApplicationRecord(
            id="hsbc", company="HSBC", job="Investment Specialist",
            action="Apply", deadline="2026-fall", when="2026-fall",
        ))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await app.push_screen(ApplicationScreen(store, "hsbc"))
            await pilot.pause()
            screen = app.screen
            assert screen.focused is screen._row("Action")
            assert screen._navigable_rows()[:3] == [
                screen._row("Action"), screen._row("Next"), screen._row("Deadline"),
            ]
            expected = default_next(store.get("hsbc"), date.today())
            assert screen.values["Next"] == expected
            assert screen._auto_next
            screen.action_save()
            await pilot.pause()
            assert store.get("hsbc").next == ""
            assert store.get("hsbc").deadline == "2026-fall"

            await app.push_screen(ApplicationScreen(store, "hsbc"))
            await pilot.pause()
            screen = app.screen
            screen._after_choice("Action", "Take")
            assert screen.values["Deadline"] == "2026-fall"
            assert screen._auto_next
            screen.finish_inline_edit("Next", "ASAP")
            assert screen._auto_next
            screen.action_save()
            await pilot.pause()
            result = store.get("hsbc")
            assert result.action == "Take"
            assert result.next == ""
            assert result.deadline == "2026-fall"
    asyncio.run(scenario())



def test_changing_action_enforces_weekly_next_but_other_actions_keep_manual_next(tmp_path):
    from career_job_manager.model import end_of_current_week

    async def scenario():
        store = CareerStore(tmp_path / 'career')
        store.add(ApplicationRecord(id='priority', company='Firm A', job='Research',
                                    action='Apply', next='2026-11-15', deadline=''))
        store.add(ApplicationRecord(id='manual', company='Firm B', job='Research',
                                    action='Email', next='ASAP', deadline=''))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await app.push_screen(ApplicationScreen(store, 'priority'))
            await pilot.pause()
            screen = app.screen
            sunday = end_of_current_week(date.today()).isoformat()
            assert screen._auto_next
            assert screen.values['Next'] == sunday
            screen._after_choice('Action', 'Take')
            assert screen._auto_next
            assert screen.values['Next'] == sunday
            screen.action_save()
            await pilot.pause()
            assert store.get('priority').action == 'Take'
            assert store.get('priority').next == ''

            await app.push_screen(ApplicationScreen(store, 'manual'))
            await pilot.pause()
            screen = app.screen
            assert not screen._auto_next
            assert screen.values['Next'] == 'ASAP'
            screen._after_choice('Action', 'Go')
            assert not screen._auto_next
            screen.action_save()
            await pilot.pause()
            assert store.get('manual').action == 'Go'
            assert store.get('manual').next == 'ASAP'

    asyncio.run(scenario())

def test_action_change_keeps_automatic_next_automatic(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(ApplicationRecord(
            id="automatic", company="Firm", job="Research",
            action="Apply", deadline="2026-12-31",
        ))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await app.push_screen(ApplicationScreen(store, "automatic"))
            await pilot.pause()
            screen = app.screen
            from career_job_manager.model import end_of_current_week
            assert screen._auto_next
            assert screen.values["Next"] == end_of_current_week(date.today()).isoformat()
            screen._after_choice("Action", "Take")
            assert screen._auto_next
            assert screen.values["Next"] == end_of_current_week(date.today()).isoformat()
            screen.action_save()
            await pilot.pause()
            result = store.get("automatic")
            assert result.action == "Take"
            assert result.next == ""
            assert result.deadline == "2026-12-31"
    asyncio.run(scenario())
