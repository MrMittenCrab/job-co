"""Wait follow-up rollover at status change and on first upgrade."""
import asyncio
import json
from datetime import date

from career_job_manager import store as store_module, ui as ui_module
from career_job_manager.model import ApplicationRecord, next_value
from career_job_manager.store import CareerStore
from career_job_manager.ui import ApplicationScreen, CareerApp


class FrozenDate(date):
    current = date(2026, 11, 17)

    @classmethod
    def today(cls):
        return cls.current


def make_record(key, *, action="Apply", next="", deadline="2026-12-31"):
    return ApplicationRecord(id=key, company=key.upper(), job="Research",
                             action=action, next=next, deadline=deadline,
                             when="2026-fall")


def test_transition_moves_expired_followup_only_on_entering_wait(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    store = CareerStore(tmp_path / "career")
    store.add(make_record("gaw", next="2026-11-15"))
    changed = store.update("gaw", {"action": "Wait"})
    assert changed.next == "2026-11-22"
    assert changed.deadline == "2026-12-31"
    assert next_value(store.get("gaw"), date(2026, 11, 17)) == "2026-11-22"
    FrozenDate.current = date(2026, 11, 24)
    assert store.update("gaw", {"contact": "Follow up"}).next == "2026-11-22"
    store.update("gaw", {"action": "Apply"})
    assert store.update("gaw", {"action": "Wait"}).next == "2026-11-29"


def test_transition_preserves_asap_today_and_future_dates(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    store = CareerStore(tmp_path / "career")
    for key, due in (("asap", "ASAP"), ("today", "2026-11-17"),
                     ("future", "2026-11-29")):
        store.add(make_record(key, next=due))
        changed = store.update(key, {"action": "Wait"})
        assert changed.next == due
        assert changed.deadline == "2026-12-31"


def test_one_time_migration_corrects_four_existing_wait_entries(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    root = tmp_path / "career"
    store = CareerStore(root)
    for key in ("gaw", "hkex", "hsbc", "jefferies"):
        store.add(make_record(key, action="Wait", next="2026-11-15"))
    store.add(make_record("citi", action="Take", next="2026-11-15"))
    store.add(make_record("jpm", action="Wait", next="ASAP"))
    store.add(make_record("orbis", action="Wait", next="2026-11-29"))
    raw = store._document()
    raw["version"] = 8
    raw["custom"] = {"preserve": True}
    store._write(raw)
    upgraded = CareerStore(root)
    for key in ("gaw", "hkex", "hsbc", "jefferies"):
        rec = upgraded.get(key)
        assert rec.next == "2026-11-22"
        assert rec.deadline == "2026-12-31"
    assert upgraded.get("citi").next == "2026-11-15"
    assert upgraded.get("jpm").next == "ASAP"
    assert upgraded.get("orbis").next == "2026-11-29"
    result = json.loads(upgraded.metadata_path.read_text())
    assert result["version"] == 9
    assert result["custom"] == {"preserve": True}
    FrozenDate.current = date(2026, 11, 24)
    assert CareerStore(root).get("gaw").next == "2026-11-22"


def test_auto_wait_with_expired_cutoff_reviews_this_week_not_asap():
    wait = make_record("wait", action="Wait", deadline="2026-11-15")
    assert next_value(wait, date(2026, 11, 17)) == "2026-11-22"
    assert next_value(wait, date(2026, 11, 24)) == "2026-11-29"
    assert wait.next == ""
    assert wait.deadline == "2026-11-15"


def test_ui_previews_rollover_when_wait_selected(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    monkeypatch.setattr(ui_module, "date", FrozenDate)

    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(make_record("jefferies", next="2026-11-15"))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await app.push_screen(ApplicationScreen(store, "jefferies"))
            await pilot.pause()
            screen = app.screen
            screen._after_choice("Action", "Wait")
            assert screen.values["Next"] == "2026-11-22"
            assert not screen._auto_next
            screen.action_save()
            await pilot.pause()
            assert store.get("jefferies").next == "2026-11-22"

    asyncio.run(scenario())
