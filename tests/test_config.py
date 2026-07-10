import dataclasses

import pytest

from whatsosint_client.config import (
    Config,
    ConfigError,
    load_config,
    DEFAULT_RAPIDAPI_HOST,
    DEFAULT_RAPIDAPI_CACHE_HOST,
    DEFAULT_NATIVE_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
)


def test_defaults_reproduce_legacy_behavior():
    cfg = load_config({"RAPIDAPI_KEY": "k"})
    assert cfg.provider == "rapidapi"
    assert cfg.mode == "live"
    assert cfg.rapidapi_key == "k"
    assert cfg.rapidapi_host == DEFAULT_RAPIDAPI_HOST
    assert cfg.rapidapi_cache_host == DEFAULT_RAPIDAPI_CACHE_HOST
    assert cfg.native_base_url == DEFAULT_NATIVE_BASE_URL


def test_explicit_hosts_override_defaults():
    cfg = load_config(
        {
            "RAPIDAPI_KEY": "k",
            "RAPIDAPI_HOST": "custom-live.example.com",
            "RAPIDAPI_CACHE_HOST": "custom-cache.example.com",
        }
    )
    assert cfg.rapidapi_host == "custom-live.example.com"
    assert cfg.rapidapi_cache_host == "custom-cache.example.com"


@pytest.mark.parametrize("mode", ["live", "cache_first", "cache_only"])
def test_valid_modes_accepted(mode):
    cfg = load_config({"RAPIDAPI_KEY": "k", "CHECK_MODE": mode})
    assert cfg.mode == mode


def test_provider_and_mode_are_case_insensitive_and_trimmed():
    cfg = load_config(
        {"RAPIDAPI_KEY": "k", "CHECK_PROVIDER": "  RapidAPI ", "CHECK_MODE": " LIVE "}
    )
    assert cfg.provider == "rapidapi"
    assert cfg.mode == "live"


def test_invalid_provider_raises():
    with pytest.raises(ConfigError) as exc:
        load_config({"RAPIDAPI_KEY": "k", "CHECK_PROVIDER": "bogus"})
    assert "CHECK_PROVIDER" in str(exc.value)


def test_invalid_mode_raises():
    with pytest.raises(ConfigError) as exc:
        load_config({"RAPIDAPI_KEY": "k", "CHECK_MODE": "bogus"})
    assert "CHECK_MODE" in str(exc.value)


def test_rapidapi_provider_requires_rapidapi_key():
    with pytest.raises(ConfigError) as exc:
        load_config({"CHECK_PROVIDER": "rapidapi"})
    assert "RAPIDAPI_KEY" in str(exc.value)


def test_native_provider_requires_native_key():
    with pytest.raises(ConfigError) as exc:
        load_config({"CHECK_PROVIDER": "native"})
    assert "NATIVE_API_KEY" in str(exc.value)


def test_native_provider_with_key_ok():
    cfg = load_config({"CHECK_PROVIDER": "native", "NATIVE_API_KEY": "nk"})
    assert cfg.provider == "native"
    assert cfg.native_api_key == "nk"


def test_native_base_url_override():
    cfg = load_config(
        {
            "CHECK_PROVIDER": "native",
            "NATIVE_API_KEY": "nk",
            "NATIVE_BASE_URL": "http://localhost:8080",
        }
    )
    assert cfg.native_base_url == "http://localhost:8080"


def test_config_is_frozen():
    cfg = load_config({"RAPIDAPI_KEY": "k"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.provider = "native"  # type: ignore[misc]


def test_timeout_defaults():
    cfg = load_config({"RAPIDAPI_KEY": "k"})
    assert cfg.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_timeout_override():
    cfg = load_config({"RAPIDAPI_KEY": "k", "CHECK_TIMEOUT_SECONDS": "5"})
    assert cfg.timeout_seconds == 5.0


def test_timeout_non_numeric_raises():
    with pytest.raises(ConfigError) as exc:
        load_config({"RAPIDAPI_KEY": "k", "CHECK_TIMEOUT_SECONDS": "soon"})
    assert "CHECK_TIMEOUT_SECONDS" in str(exc.value)


@pytest.mark.parametrize("bad", ["0", "-3"])
def test_timeout_non_positive_raises(bad):
    with pytest.raises(ConfigError) as exc:
        load_config({"RAPIDAPI_KEY": "k", "CHECK_TIMEOUT_SECONDS": bad})
    assert "CHECK_TIMEOUT_SECONDS" in str(exc.value)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_host_env_falls_back_to_default(blank):
    cfg = load_config(
        {
            "RAPIDAPI_KEY": "k",
            "RAPIDAPI_HOST": blank,
            "RAPIDAPI_CACHE_HOST": blank,
        }
    )
    assert cfg.rapidapi_host == DEFAULT_RAPIDAPI_HOST
    assert cfg.rapidapi_cache_host == DEFAULT_RAPIDAPI_CACHE_HOST


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_native_base_url_falls_back_to_default(blank):
    cfg = load_config(
        {
            "CHECK_PROVIDER": "native",
            "NATIVE_API_KEY": "nk",
            "NATIVE_BASE_URL": blank,
        }
    )
    assert cfg.native_base_url == DEFAULT_NATIVE_BASE_URL
