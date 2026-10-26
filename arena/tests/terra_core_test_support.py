"""Explicit, test-only core fixtures; never imported by a production engine."""
from pathlib import Path


def engine_source(package):
    core = Path(package) / 'web/playground/terraria-core.js'
    return core if core.exists() else Path(package) / 'web/playground/terraria.js'


def test_source(path):
    path = Path(path)
    source = path.read_text()
    if path.name != 'terraria-core.js':
        return source
    marker = '  bridge.reset(conditionSeed,options.generationOptions);\n  return bridge;'
    if marker not in source:
        marker = '  bridge.reset(conditionSeed);\n  return bridge;'
    assert source.count(marker) == 1
    fixtures = Path(__file__).with_name('terra_core_fixture.js').read_text()
    return source.replace(marker, 'if(window.__JEV_TEST_MODE__){\n' + fixtures + '\n}\n' + marker)


async def install_fixture(page, package):
    source = engine_source(package)
    if source.name != 'terraria-core.js':
        return

    async def intercept(route):
        await route.fulfill(status=200, content_type='application/javascript', body=test_source(source))

    await page.route('**/terraria-core.js*', intercept)
