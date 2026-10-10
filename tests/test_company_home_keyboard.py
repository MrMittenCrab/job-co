import asyncio

from textual.containers import VerticalScroll

from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp


def test_home_hides_scrollbar_but_arrows_reach_last_company(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [
            {'id': str(i), 'name': f'Company {i:02}'} for i in range(24)
        ]})
        before = store.metadata_path.read_bytes()
        app = CareerApp(store, initial_root='company')
        async with app.run_test(size=(80, 12)) as pilot:
            screen = app.screen
            scroll = screen.query_one(VerticalScroll)
            await pilot.pause()
            assert scroll.max_scroll_y > 0
            assert scroll.scrollbar_size_vertical == 0
            assert scroll.vertical_scrollbar.region.width == 0
            await pilot.press(*(['down'] * 23))
            assert screen.selected()['name'] == 'Company 23'
            assert scroll.scroll_y > 0
            assert scroll.scrollbar_size_vertical == 0
            assert scroll.vertical_scrollbar.region.width == 0
            strips = screen._compositor.render_strips()
            assert any('Company 23' in strip.text for strip in strips)
            await pilot.press(*(['up'] * 23))
            assert screen.selected()['name'] == 'Company 00'
            assert scroll.scroll_y == 0
            await pilot.press('q')
            assert not app.is_running
        assert store.metadata_path.read_bytes() == before
    asyncio.run(scenario())
