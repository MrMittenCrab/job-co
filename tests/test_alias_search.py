import asyncio
from career_job_manager.store import CareerStore
from career_job_manager.ui import CareerApp


def test_job_search_resolves_company_aliases(tmp_path):
    async def scenario():
        store = CareerStore(tmp_path)
        store.import_jobs({'companies': [{'id': 'existing', 'name': 'China Pacific Insurance', 'aliases': ['CPIC', 'cpic-hk']}],
                           'jobs': [{'id': 'clerk', 'company_id': 'cpic-hk', 'company': 'China Pacific Insurance', 'job': 'Clerk'}]})
        app = CareerApp(store)
        async with app.run_test() as pilot:
            await pilot.press('/', *'CPIC')
            await pilot.pause()
            assert [r.id for r in app.screen.visible_records] == ['clerk']
    asyncio.run(scenario())
