import pytest

from whatsosint_client.config import load_config
from whatsosint_client.providers import build_request

RAPIDAPI_ENV = {"RAPIDAPI_KEY": "rk"}
NATIVE_ENV = {"CHECK_PROVIDER": "native", "NATIVE_API_KEY": "nk"}


def test_rapidapi_live_url_and_headers():
    cfg = load_config(RAPIDAPI_ENV)
    url, headers = build_request(cfg, "live", "59898297150")
    assert url == "https://wp-data.p.rapidapi.com/number/59898297150"
    assert headers == {
        "x-rapidapi-key": "rk",
        "x-rapidapi-host": "wp-data.p.rapidapi.com",
    }


def test_rapidapi_cache_url_and_headers():
    cfg = load_config(RAPIDAPI_ENV)
    url, headers = build_request(cfg, "cache", "59898297150")
    assert url == "https://wp-data-db-only.p.rapidapi.com/number_cache/59898297150"
    assert headers == {
        "x-rapidapi-key": "rk",
        "x-rapidapi-host": "wp-data-db-only.p.rapidapi.com",
    }


def test_native_live_url_and_headers():
    cfg = load_config(NATIVE_ENV)
    url, headers = build_request(cfg, "live", "59898297150")
    assert url == "https://whatsapp-proxy.checkleaked.cc/number/59898297150"
    assert headers == {"x-rapidapi-key": "nk"}
    assert "x-rapidapi-host" not in headers


def test_native_cache_url_and_headers():
    cfg = load_config(NATIVE_ENV)
    url, headers = build_request(cfg, "cache", "59898297150")
    assert url == "https://whatsapp-proxy.checkleaked.cc/number_cache/59898297150"
    assert headers == {"x-rapidapi-key": "nk"}


def test_native_base_url_trailing_slash_is_normalized():
    cfg = load_config({**NATIVE_ENV, "NATIVE_BASE_URL": "http://localhost:8080/"})
    url, _ = build_request(cfg, "cache", "123")
    assert url == "http://localhost:8080/number_cache/123"


def test_unknown_endpoint_kind_raises():
    cfg = load_config(RAPIDAPI_ENV)
    with pytest.raises(ValueError):
        build_request(cfg, "bogus", "123")
