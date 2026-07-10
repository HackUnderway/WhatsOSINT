import whatsosint_client as pkg
from whatsosint_client import (  # noqa: F401  (import is the assertion)
    CacheResult,
    CheckerError,
    Config,
    ConfigError,
    WhatsOSINTClient,
    load_config,
)

EXPECTED_EXPORTS = {
    "Config",
    "ConfigError",
    "load_config",
    "WhatsOSINTClient",
    "CheckerError",
    "CacheResult",
}


def test_all_matches_expected_exports():
    assert set(pkg.__all__) == EXPECTED_EXPORTS


def test_every_all_entry_is_a_real_attribute():
    for name in pkg.__all__:
        assert hasattr(pkg, name), "missing export: {}".format(name)
