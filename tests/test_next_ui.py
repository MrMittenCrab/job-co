"""Current user contract: Action, Next, Deadline at top of job detail."""
import asyncio
from datetime import date

from career_job_manager.model import ApplicationRecord, default_next
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp


def test_detail_keeps_auto_next_dynamic_and_saves_manual_next(tmp_path):
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
            assert not screen._auto_next
            screen.action_save()
            await pilot.pause()
            result = store.get("hsbc")
            assert result.action == "Take"
            assert result.next == "ASAP"
            assert result.deadline == "2026-fall"
    asyncio.run(scenario())
