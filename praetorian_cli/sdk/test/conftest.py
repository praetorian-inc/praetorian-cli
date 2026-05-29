import pytest


@pytest.fixture(autouse=True)
def _reset_registry_singleton():
    import praetorian_cli.registry as reg_mod
    reg_mod._registry = None
    yield
    reg_mod._registry = None
