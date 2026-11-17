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
    assert CareerStore(root).get("gaw").next == "2026-11-29"


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


def test_version9_overdue_wait_self_heals_on_next_startup(tmp_path, monkeypatch):
    """A prior schema upgrade must not permanently strand dated Wait entries."""
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    root = tmp_path / "career"
    store = CareerStore(root)
    for key in ("gaw", "hkex", "hsbc", "jefferies"):
        store.add(make_record(key, action="Wait", next="2026-11-15"))
    store.add(make_record("pimco", action="Apply", next="2026-11-14"))
    store.add(make_record("bernstein", action="Wait", next="ASAP"))
    store.add(make_record("fullgoal", action="Wait", next="2026-11-22"))
    assert store._document()["version"] == 9

    # Even before a restart, the displayed queue uses the effective date.
    rows = store.list()
    wait_rows = [r for r in rows if r.id in ("gaw", "hkex", "hsbc", "jefferies")]
    assert all(next_value(r, date(2026, 11, 17)) == "2026-11-22" for r in wait_rows)
    # Rendering uses the model's effective Next when local date is current.

    # Opening the store corrects persisted data regardless of schema version.
    reopened = CareerStore(root)
    assert all(reopened.get(key).next == "2026-11-22"
               for key in ("gaw", "hkex", "hsbc", "jefferies"))
    assert reopened.get("pimco").next == "2026-11-22"
    assert reopened.get("bernstein").next == "ASAP"
    assert reopened.get("fullgoal").next == "2026-11-22"
    assert all(reopened.get(key).deadline == "2026-12-31"
               for key in ("gaw", "hkex", "hsbc", "jefferies"))
    before = reopened.metadata_path.read_bytes()
    assert CareerStore(root).metadata_path.read_bytes() == before


def test_model_never_leaves_an_explicit_wait_next_in_past():
    from career_job_manager.model import sort_records
    today = date(2026, 11, 17)
    stale = make_record("gaw", action="Wait", next="2026-11-15")
    tomorrow = make_record("future", action="Wait", next="2026-11-18")
    asap = make_record("asap", action="Wait", next="ASAP")
    assert next_value(stale, today) == "2026-11-22"
    assert stale.next == "2026-11-15"  # Reads cannot mutate persisted metadata.
    assert [r.id for r in sort_records([stale, tomorrow, asap], today=today)] == [
        "asap", "future", "gaw",
    ]
    assert next_value(tomorrow, today) == "2026-11-18"
    assert next_value(asap, today) == "ASAP"


def test_detail_screen_displays_effective_next_for_existing_wait(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    monkeypatch.setattr(ui_module, "date", FrozenDate)

    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(make_record("hkex", action="Wait", next="2026-11-15"))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await app.push_screen(ApplicationScreen(store, "hkex"))
            await pilot.pause()
            screen = app.screen
            assert screen.values["Next"] == "2026-11-22"
            assert not screen._auto_next
            screen.action_save()
            await pilot.pause()
            assert store.get("hkex").next == "2026-11-22"

    asyncio.run(scenario())



def test_apply_existing_stale_date_changes_on_startup_even_with_version9(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    root = tmp_path / "career"
    store = CareerStore(root)
    for key, deadline, next_due in (
        ("flow", "2026-12-31", "2026-11-15"),
        ("point72", "2027-01-15", "2027-01-15"),
        ("capula", "2026-11-20 15:00", "2026-11-15"),
        ("pimco", "2026-11-14", "2026-11-14"),
        ("unknown", "", "2026-11-15"),
        ("priority", "2026-12-31", "ASAP"),
    ):
        store.add(make_record(key, action="Apply", deadline=deadline, next=next_due))
    assert store._document()["version"] == 9

    # Before startup repair, the in-memory queue resolves eligible Apply dates.
    today = date(2026, 11, 17)
    assert next_value(store.get("flow"), today) == "2026-11-22"
    assert next_value(store.get("point72"), today) == "2026-11-22"
    assert next_value(store.get("capula"), today) == "2026-11-20 15:00"

    reloaded = CareerStore(root)
    assert reloaded.get("flow").next == "2026-11-22"
    assert reloaded.get("point72").next == "2026-11-22"
    assert reloaded.get("capula").next == "2026-11-20 15:00"
    assert reloaded.get("pimco").next == "2026-11-14"
    assert reloaded.get("unknown").next == "2026-11-15"
    assert reloaded.get("priority").next == "ASAP"
    assert reloaded.get("flow").deadline == "2026-12-31"

    previous = reloaded.metadata_path.read_bytes()
    assert CareerStore(root).metadata_path.read_bytes() == previous
    FrozenDate.current = date(2026, 11, 24)
    assert CareerStore(root).get("flow").next == "2026-11-29"


def test_apply_status_transition_schedules_current_week(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    store = CareerStore(tmp_path / "career")
    store.add(make_record("capula", action="Check", next="2026-12-31"))
    changed = store.update("capula", {"action": "Apply"})
    assert changed.next == "2026-11-22"
    assert changed.deadline == "2026-12-31"


def test_apply_detail_previews_week_end_for_unexpired_deadline(tmp_path, monkeypatch):
    FrozenDate.current = date(2026, 11, 17)
    monkeypatch.setattr(store_module, "date", FrozenDate)
    monkeypatch.setattr(ui_module, "date", FrozenDate)

    async def scenario():
        store = CareerStore(tmp_path / "career")
        store.add(make_record("flow", action="Apply", next="2026-11-15"))
        store.add(make_record("point72", action="Check", next="2026-12-31"))
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await app.push_screen(ApplicationScreen(store, "flow"))
            await pilot.pause()
            screen = app.screen
            assert screen.values["Next"] == "2026-11-22"
            screen.action_save()
            await pilot.pause()
            assert store.get("flow").next == "2026-11-22"

            await app.push_screen(ApplicationScreen(store, "point72"))
            await pilot.pause()
            screen = app.screen
            screen._after_choice("Action", "Apply")
            assert screen.values["Next"] == "2026-11-22"
            screen.action_save()
            await pilot.pause()
            assert store.get("point72").next == "2026-11-22"

    asyncio.run(scenario())
