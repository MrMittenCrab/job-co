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



def test_changing_action_preserves_manual_next_and_chronological_position(tmp_path):
    from career_job_manager.model import next_value

    transitions = [
        ("Apply", "Take", "2026-11-15"),
        ("Wait", "Go", "ASAP"),
        ("Take", "Respond", "2026-11-15"),
        ("Go", "Email", "2026-11-15 18:30"),
        ("Email", "Apply", "2026-11-15"),
        ("Check", "Apply", "2026-11-15"),
        ("Apply", "Check", "2026-11-15"),
        ("Wait", "Archive", "2026-11-15"),
    ]

    async def scenario():
        store = CareerStore(tmp_path / "career")
        for i, (before, _, next_due) in enumerate(transitions):
            store.add(ApplicationRecord(
                id=f"transition-{i}", company=f"Firm {i}", job="Research",
                action=before, next=next_due, deadline="2026-12-31",
            ))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            for i, (before, after, next_due) in enumerate(transitions):
                record_id = f"transition-{i}"
                await app.push_screen(ApplicationScreen(store, record_id))
                await pilot.pause()
                screen = app.screen
                assert screen.values["Next"] == next_due
                assert not screen._auto_next
                screen._after_choice("Action", after)
                assert screen.values["Next"] == next_due
                assert not screen._auto_next
                screen.action_save()
                await pilot.pause()
                result = store.get(record_id)
                assert result.action == after
                assert result.next == next_due
                assert result.deadline == "2026-12-31"
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
            assert screen._auto_next
            assert screen.values["Next"] == "2026-12-31"
            screen._after_choice("Action", "Take")
            assert screen._auto_next
            assert screen.values["Next"] == "2026-12-31"
            screen.action_save()
            await pilot.pause()
            result = store.get("automatic")
            assert result.action == "Take"
            assert result.next == ""
            assert result.deadline == "2026-12-31"
    asyncio.run(scenario())
