import pytest
import requests
import requests_mock

from whatsosint_client.client import CacheResult, CheckerError, WhatsOSINTClient
from whatsosint_client.config import load_config

NUMBER = "59898297150"

HIT_BODY = {"exists": True, "number": NUMBER, "phone": "+598 98 297 150"}
# Distinct sentinel so "came from live" is proven by the value, not only call counts.
LIVE_BODY = {"exists": True, "number": NUMBER, "phone": "+598 98 297 150", "src": "live"}
MISS_BODY = {
    "error": "Whatsapp number is not in the Database records",
    "status": 404,
    "code": "NOT_IN_DATABASE",
}

# (env, live_url, cache_url) for each provider
PROVIDER_CASES = [
    (
        {"RAPIDAPI_KEY": "rk"},
        "https://wp-data.p.rapidapi.com/number/" + NUMBER,
        "https://wp-data-db-only.p.rapidapi.com/number_cache/" + NUMBER,
    ),
    (
        {"CHECK_PROVIDER": "native", "NATIVE_API_KEY": "nk"},
        "https://whatsapp-proxy.checkleaked.cc/number/" + NUMBER,
        "https://whatsapp-proxy.checkleaked.cc/number_cache/" + NUMBER,
    ),
]


def _client(env):
    return WhatsOSINTClient(load_config(env))


# ---- live mode ----

@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_live_mode_calls_only_live(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, json=MISS_BODY, status_code=404)
        result = _client({**env, "CHECK_MODE": "live"}).check(NUMBER)
    assert result == HIT_BODY
    assert live.call_count == 1
    assert cache.call_count == 0


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_live_mode_http_400_raises_checker_error(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        m.get(live_url, json={"error": "Invalid phone number"}, status_code=400)
        with pytest.raises(CheckerError):
            _client({**env, "CHECK_MODE": "live"}).check(NUMBER)


# ---- cache_only mode ----

@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_only_hit_returns_body_and_skips_live(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, json=HIT_BODY, status_code=200)
        result = _client({**env, "CHECK_MODE": "cache_only"}).check(NUMBER)
    assert result == HIT_BODY
    assert cache.call_count == 1
    assert live.call_count == 0


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_only_miss_returns_404_body_without_raising(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, json=MISS_BODY, status_code=404)
        result = _client({**env, "CHECK_MODE": "cache_only"}).check(NUMBER)
    assert result == MISS_BODY
    assert cache.call_count == 1
    assert live.call_count == 0


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_only_non_json_404_wraps_body_without_raising(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, text="Not Found", status_code=404)
        result = _client({**env, "CHECK_MODE": "cache_only"}).check(NUMBER)
    assert result == {"error": "Not Found", "status": 404}
    assert cache.call_count == 1
    assert live.call_count == 0


@pytest.mark.parametrize("cache_status", [500, 429])
@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_only_error_propagates_and_never_calls_live(
    env, live_url, cache_url, cache_status
):
    # cache_only contract: cache only, no fallback ever — a 5xx or non-404 4xx
    # must raise and must NOT touch the live endpoint.
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        m.get(cache_url, json={"error": "x"}, status_code=cache_status)
        with pytest.raises(CheckerError) as exc:
            _client({**env, "CHECK_MODE": "cache_only"}).check(NUMBER)
        assert live.call_count == 0
    assert exc.value.status_code == cache_status


# ---- cache_first mode ----

@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_hit_skips_live(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, json=HIT_BODY, status_code=200)
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == HIT_BODY
    assert cache.call_count == 1
    assert live.call_count == 0


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_miss_falls_back_to_live(env, live_url, cache_url):
    live_hit = {"exists": True, "number": NUMBER, "phone": "+598 98 297 150", "src": "live"}
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=live_hit, status_code=200)
        cache = m.get(cache_url, json=MISS_BODY, status_code=404)
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == live_hit
    assert cache.call_count == 1
    assert live.call_count == 1


@pytest.mark.parametrize("server_status", [500, 502, 503])
@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_cache_5xx_falls_back_to_live(
    env, live_url, cache_url, server_status
):
    # Boundary coverage: 500 (low edge) must fall back too, not just 503.
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=LIVE_BODY, status_code=200)
        cache = m.get(cache_url, status_code=server_status, text="upstream down")
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == LIVE_BODY
    assert cache.call_count == 1
    assert live.call_count == 1


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_cache_transport_error_falls_back_to_live(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=LIVE_BODY, status_code=200)
        cache = m.get(cache_url, exc=requests.exceptions.ConnectTimeout)
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == LIVE_BODY
    assert cache.call_count == 1
    assert live.call_count == 1


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_non_json_404_still_falls_back_to_live(env, live_url, cache_url):
    # A 404 with a non-JSON body (e.g. a CDN/gateway error page) is still a
    # miss and must fall back — it must NOT hard-fail on the parse.
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=LIVE_BODY, status_code=200)
        cache = m.get(cache_url, text="<html>Not Found</html>", status_code=404)
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == LIVE_BODY
    assert cache.call_count == 1
    assert live.call_count == 1


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_falls_back_and_live_also_fails_surfaces_live_error(
    env, live_url, cache_url
):
    # When cache fails (5xx) AND the live fallback also fails, the LIVE error
    # must surface (not the original cache error).
    with requests_mock.Mocker() as m:
        cache = m.get(cache_url, status_code=503, text="cache down")
        live = m.get(live_url, json={"error": "boom"}, status_code=500)
        with pytest.raises(CheckerError) as exc:
            _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert exc.value.status_code == 500  # the live failure, not the cache 503
    assert cache.call_count == 1
    assert live.call_count == 1


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_cache_400_raises_and_skips_live(env, live_url, cache_url):
    # A 400 from cache is a real error, NOT a miss: must not fall back.
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, json={"error": "bad"}, status_code=400)
        with pytest.raises(CheckerError):
            _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
        assert live.call_count == 0


@pytest.mark.parametrize("client_status", [400, 401, 403, 429])
@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_cache_4xx_raises_and_skips_live(
    env, live_url, cache_url, client_status
):
    # Any 4xx (except the 404 miss) is a request-level error the live call
    # would hit identically, so cache_first must propagate it without a
    # (potentially costly) fallback.
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        m.get(cache_url, json={"error": "nope"}, status_code=client_status)
        with pytest.raises(CheckerError) as exc:
            _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
        assert live.call_count == 0
    assert exc.value.status_code == client_status


# ---- header propagation ----

def test_rapidapi_sends_both_headers():
    with requests_mock.Mocker() as m:
        m.get(
            "https://wp-data.p.rapidapi.com/number/" + NUMBER,
            json=HIT_BODY,
            status_code=200,
        )
        _client({"RAPIDAPI_KEY": "rk", "CHECK_MODE": "live"}).check(NUMBER)
        req = m.request_history[0]
    assert req.headers["x-rapidapi-key"] == "rk"
    assert req.headers["x-rapidapi-host"] == "wp-data.p.rapidapi.com"


def test_native_sends_only_key_header():
    with requests_mock.Mocker() as m:
        m.get(
            "https://whatsapp-proxy.checkleaked.cc/number/" + NUMBER,
            json=HIT_BODY,
            status_code=200,
        )
        _client(
            {"CHECK_PROVIDER": "native", "NATIVE_API_KEY": "nk", "CHECK_MODE": "live"}
        ).check(NUMBER)
        req = m.request_history[0]
    assert req.headers["x-rapidapi-key"] == "nk"
    assert "x-rapidapi-host" not in req.headers


# ---- fetch_cache returns a CacheResult ----

def test_fetch_cache_returns_cache_result():
    with requests_mock.Mocker() as m:
        m.get(
            "https://wp-data-db-only.p.rapidapi.com/number_cache/" + NUMBER,
            json=MISS_BODY,
            status_code=404,
        )
        result = _client({"RAPIDAPI_KEY": "rk"}).fetch_cache(NUMBER)
    assert isinstance(result, CacheResult)
    assert result.status_code == 404
    assert result.data == MISS_BODY


# ---- non-JSON body handling on the 200 (success) path ----

@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_live_non_json_200_raises_checker_error(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        m.get(live_url, text="<html>bad gateway</html>", status_code=200)
        with pytest.raises(CheckerError) as exc:
            _client({**env, "CHECK_MODE": "live"}).check(NUMBER)
    assert exc.value.status_code == 200
    assert "non-JSON" in str(exc.value)


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_non_json_200_raises_checker_error(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        m.get(cache_url, text="oops not json", status_code=200)
        with pytest.raises(CheckerError) as exc:
            _client({**env, "CHECK_MODE": "cache_only"}).check(NUMBER)
    assert exc.value.status_code == 200
    assert "non-JSON" in str(exc.value)
