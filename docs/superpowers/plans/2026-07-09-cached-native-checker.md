# Cached + Native Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a WhatsOSINT user pick a cheaper WhatsApp-number check strategy (cache-first-then-live fallback, or cache-only) and/or a cheaper transport (native `checkleaked.cc` vs RapidAPI marketplace), configured entirely through `.env`, with zero behavior change for existing users.

**Architecture:** Extract all HTTP logic out of `WhatsOSINT.py` into a new `whatsosint_client/` package with three focused modules — `config` (env parsing + validation), `providers` (URL/header construction for each provider×endpoint), and `client` (mode dispatch + miss/fallback logic). `WhatsOSINT.py` keeps only the banner, prompt, colored-JSON printer, and error display, delegating the actual check to `WhatsOSINTClient.check()`.

**Tech Stack:** Python 3.12, `requests` (already a dependency), `python-dotenv` (already), `colorama` (already); tests via `pytest` + `requests-mock`.

## Global Constraints

- Python 3.8+ compatible syntax (dataclasses, f-strings, `typing`); no 3.10+-only syntax (no `match`, no `X | Y` unions in annotations — use `Optional[...]`). Copied from repo's plain-`requests` style.
- Default config MUST reproduce today's request exactly: `CHECK_PROVIDER=rapidapi`, `CHECK_MODE=live`, `GET https://{RAPIDAPI_HOST}/number/{number}` with `x-rapidapi-key` + `x-rapidapi-host` headers.
- No CLI flags. Configuration is env-only.
- No retry/backoff. No bulk-check. Single-number scope only.
- No committed test may hit a real third-party API — all HTTP is mocked.
- Provider auth (verified live 2026-07-09): rapidapi → `x-rapidapi-key` + `x-rapidapi-host`; native → `x-rapidapi-key` only (value is a separate native-tier key, NOT the RapidAPI key), no host header.
- Cache-miss signal (verified live 2026-07-09): HTTP **404** from `/number_cache/{number}` (body also carries `"code":"NOT_IN_DATABASE"`). Detection uses the **status code**, not body shape. `200` = hit. Any other status (401/429/5xx) = real error. The live endpoint's `400` (malformed input) is a distinct error, never a "miss", never triggers fallback.

## Decisions that deviate from / refine the spec

- **`build_request` signature** simplified to `build_request(config, endpoint_kind, number)` (provider is read from `config.provider`) rather than the spec's 4-arg form. Internal detail.
- **`.env` stays tracked** (upstream ships a tracked `.env` with a placeholder key and the README instructs editing it). Rather than untrack it + add `.env.example` (spec's original hygiene note), we respect upstream convention: update the tracked `.env` in place (new host + documented optional vars) and add a `.gitignore` covering Python artifacts only (NOT `.env`). This is lower-friction for a PR into someone else's repo and keeps `git clone` + README flow intact. Flagged for user veto at handoff.

---

## File Structure

- **Create** `whatsosint_client/__init__.py` — package exports (`Config`, `load_config`, `ConfigError`, `WhatsOSINTClient`, `CheckerError`, `CacheResult`).
- **Create** `whatsosint_client/config.py` — `Config` dataclass, `load_config(env=None)`, `ConfigError`, enum + default constants.
- **Create** `whatsosint_client/providers.py` — `build_request(config, endpoint_kind, number) -> (url, headers)`.
- **Create** `whatsosint_client/client.py` — `WhatsOSINTClient`, `CacheResult`, `CheckerError`.
- **Modify** `WhatsOSINT.py` — replace inline `requests.get` with client delegation; keep printer + banner + prompt.
- **Create** `tests/__init__.py` — empty, marks test package.
- **Create** `tests/test_config.py`, `tests/test_providers.py`, `tests/test_client.py`.
- **Create** `requirements-dev.txt` — `pytest`, `requests-mock`.
- **Create** `.gitignore` — Python artifacts.
- **Modify** `.env` — re-apply host fix + document new optional vars.
- **Modify** `README.md` — document modes/providers/vars.

Run all tests from the `api/WhatsOSINT/` directory with `python -m pytest tests/ -v` (invoking via `python -m` puts the cwd on `sys.path` so `import whatsosint_client` resolves without any packaging config).

---

### Task 1: Config module (env parsing + validation)

**Files:**
- Create: `whatsosint_client/__init__.py`
- Create: `whatsosint_client/config.py`
- Test: `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ConfigError(ValueError)`
  - `@dataclass(frozen=True) class Config` with str fields: `provider`, `mode`, `rapidapi_key`, `rapidapi_host`, `rapidapi_cache_host`, `native_api_key`, `native_base_url`.
  - `load_config(env: Optional[Mapping[str, str]] = None) -> Config` — reads from `env` (defaults to `os.environ`), lower-cases + strips `provider`/`mode`, validates, raises `ConfigError` on bad input.
  - Constants: `VALID_PROVIDERS = ("rapidapi", "native")`, `VALID_MODES = ("live", "cache_first", "cache_only")`, `DEFAULT_RAPIDAPI_HOST = "wp-data.p.rapidapi.com"`, `DEFAULT_RAPIDAPI_CACHE_HOST = "wp-data-db-only.p.rapidapi.com"`, `DEFAULT_NATIVE_BASE_URL = "https://whatsapp-proxy.checkleaked.cc"`.

- [ ] **Step 1: Create the test package marker**

Create `tests/__init__.py` as an empty file (0 bytes).

- [ ] **Step 2: Write the failing config tests**

Create `tests/test_config.py`:

```python
import pytest

from whatsosint_client.config import (
    Config,
    ConfigError,
    load_config,
    DEFAULT_RAPIDAPI_HOST,
    DEFAULT_RAPIDAPI_CACHE_HOST,
    DEFAULT_NATIVE_BASE_URL,
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
    with pytest.raises(Exception):
        cfg.provider = "native"  # type: ignore[misc]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'whatsosint_client'`.

- [ ] **Step 4: Create the package + config implementation**

Create `whatsosint_client/__init__.py`:

```python
"""HTTP client package for WhatsOSINT number checks."""

from whatsosint_client.config import Config, ConfigError, load_config

__all__ = ["Config", "ConfigError", "load_config"]
```

Create `whatsosint_client/config.py`:

```python
"""Environment-driven configuration for the WhatsOSINT checker."""

import os
from dataclasses import dataclass
from typing import Mapping, Optional

VALID_PROVIDERS = ("rapidapi", "native")
VALID_MODES = ("live", "cache_first", "cache_only")

DEFAULT_RAPIDAPI_HOST = "wp-data.p.rapidapi.com"
DEFAULT_RAPIDAPI_CACHE_HOST = "wp-data-db-only.p.rapidapi.com"
DEFAULT_NATIVE_BASE_URL = "https://whatsapp-proxy.checkleaked.cc"


class ConfigError(ValueError):
    """Raised when environment configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    provider: str
    mode: str
    rapidapi_key: str
    rapidapi_host: str
    rapidapi_cache_host: str
    native_api_key: str
    native_base_url: str


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    """Build a validated Config from environment variables.

    Fails fast (before any network call) with a clear ConfigError on any
    invalid enum value or missing-but-required credential.
    """
    source = env if env is not None else os.environ

    provider = source.get("CHECK_PROVIDER", "rapidapi").strip().lower()
    mode = source.get("CHECK_MODE", "live").strip().lower()

    if provider not in VALID_PROVIDERS:
        raise ConfigError(
            "Invalid CHECK_PROVIDER={!r}. Expected one of: {}".format(
                provider, ", ".join(VALID_PROVIDERS)
            )
        )
    if mode not in VALID_MODES:
        raise ConfigError(
            "Invalid CHECK_MODE={!r}. Expected one of: {}".format(
                mode, ", ".join(VALID_MODES)
            )
        )

    rapidapi_key = source.get("RAPIDAPI_KEY", "").strip()
    native_api_key = source.get("NATIVE_API_KEY", "").strip()

    if provider == "rapidapi" and not rapidapi_key:
        raise ConfigError(
            "RAPIDAPI_KEY is required when CHECK_PROVIDER=rapidapi."
        )
    if provider == "native" and not native_api_key:
        raise ConfigError(
            "NATIVE_API_KEY is required when CHECK_PROVIDER=native."
        )

    return Config(
        provider=provider,
        mode=mode,
        rapidapi_key=rapidapi_key,
        rapidapi_host=source.get("RAPIDAPI_HOST", DEFAULT_RAPIDAPI_HOST).strip(),
        rapidapi_cache_host=source.get(
            "RAPIDAPI_CACHE_HOST", DEFAULT_RAPIDAPI_CACHE_HOST
        ).strip(),
        native_api_key=native_api_key,
        native_base_url=source.get(
            "NATIVE_BASE_URL", DEFAULT_NATIVE_BASE_URL
        ).strip(),
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (all config tests green).

- [ ] **Step 6: Commit**

```bash
git add whatsosint_client/__init__.py whatsosint_client/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add env-driven config with provider/mode validation"
```

---

### Task 2: Providers module (URL + header construction)

**Files:**
- Create: `whatsosint_client/providers.py`
- Test: `tests/test_providers.py`

**Interfaces:**
- Consumes: `Config` from Task 1.
- Produces: `build_request(config, endpoint_kind, number) -> Tuple[str, Dict[str, str]]` where `endpoint_kind` is `"live"` or `"cache"`. Raises `ValueError` on unknown `endpoint_kind` (defensive; provider is always valid post-config-validation).

- [ ] **Step 1: Write the failing providers tests**

Create `tests/test_providers.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'whatsosint_client.providers'`.

- [ ] **Step 3: Write the providers implementation**

Create `whatsosint_client/providers.py`:

```python
"""Build the URL + headers for a given provider and endpoint."""

from typing import Dict, Tuple

from whatsosint_client.config import Config

_PATHS = {
    "live": "/number/{number}",
    "cache": "/number_cache/{number}",
}

_RAPIDAPI_HOSTS = {
    "live": "rapidapi_host",
    "cache": "rapidapi_cache_host",
}


def build_request(
    config: Config, endpoint_kind: str, number: str
) -> Tuple[str, Dict[str, str]]:
    """Return (url, headers) for the configured provider and endpoint_kind.

    endpoint_kind is "live" or "cache". The provider is taken from config.
    """
    if endpoint_kind not in _PATHS:
        raise ValueError(
            "Unknown endpoint_kind={!r}. Expected 'live' or 'cache'.".format(
                endpoint_kind
            )
        )

    path = _PATHS[endpoint_kind].format(number=number)

    if config.provider == "rapidapi":
        host = getattr(config, _RAPIDAPI_HOSTS[endpoint_kind])
        url = "https://{host}{path}".format(host=host, path=path)
        headers = {
            "x-rapidapi-key": config.rapidapi_key,
            "x-rapidapi-host": host,
        }
        return url, headers

    # provider == "native" (only remaining valid value post-config-validation)
    base = config.native_base_url.rstrip("/")
    url = "{base}{path}".format(base=base, path=path)
    headers = {"x-rapidapi-key": config.native_api_key}
    return url, headers
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_providers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add whatsosint_client/providers.py tests/test_providers.py
git commit -m "feat: add per-provider URL and header builder"
```

---

### Task 3: Client module (mode dispatch + miss/fallback)

**Files:**
- Create: `whatsosint_client/client.py`
- Modify: `whatsosint_client/__init__.py` (add exports)
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `build_request` (Task 2).
- Produces:
  - `class CheckerError(Exception)`
  - `@dataclass class CacheResult` with `status_code: int`, `data: dict`.
  - `class WhatsOSINTClient`:
    - `__init__(self, config: Config, session: Optional[requests.Session] = None)`
    - `fetch_live(self, number: str) -> dict` — `raise_for_status()` then `.json()`; raises `CheckerError` on any non-2xx or non-JSON body.
    - `fetch_cache(self, number: str) -> CacheResult` — 200/404 return a `CacheResult`; any other status or non-JSON body raises `CheckerError`.
    - `check(self, number: str) -> dict` — dispatches on `config.mode`.

- [ ] **Step 1: Write the failing client tests**

Create `tests/test_client.py`:

```python
import pytest
import requests
import requests_mock

from whatsosint_client.client import CacheResult, CheckerError, WhatsOSINTClient
from whatsosint_client.config import load_config

NUMBER = "59898297150"

HIT_BODY = {"exists": True, "number": NUMBER, "phone": "+598 98 297 150"}
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


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_cache_5xx_falls_back_to_live(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, status_code=503, text="upstream down")
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == HIT_BODY
    assert cache.call_count == 1
    assert live.call_count == 1


@pytest.mark.parametrize("env, live_url, cache_url", PROVIDER_CASES)
def test_cache_first_cache_transport_error_falls_back_to_live(env, live_url, cache_url):
    with requests_mock.Mocker() as m:
        live = m.get(live_url, json=HIT_BODY, status_code=200)
        cache = m.get(cache_url, exc=requests.exceptions.ConnectTimeout)
        result = _client({**env, "CHECK_MODE": "cache_first"}).check(NUMBER)
    assert result == HIT_BODY
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'whatsosint_client.client'` (and/or `No module named 'requests_mock'` if dev deps not yet installed — install per Step 3 first).

- [ ] **Step 3: Install the test dependency**

Run: `python -m pip install requests-mock`
Expected: installs `requests-mock` (and its `requests` dep already satisfied). This is captured in `requirements-dev.txt` in Task 5.

- [ ] **Step 4: Write the client implementation**

Create `whatsosint_client/client.py`:

```python
"""HTTP client that dispatches a number check across provider + mode."""

from dataclasses import dataclass
from typing import Optional

import requests

from whatsosint_client.config import Config
from whatsosint_client.providers import build_request

# Status codes the cache endpoint returns for legitimate business outcomes.
_CACHE_HIT = 200
_CACHE_MISS = 404


class CheckerError(Exception):
    """Raised on a transport failure, unexpected HTTP status, or bad body."""


@dataclass
class CacheResult:
    status_code: int
    data: dict


class WhatsOSINTClient:
    def __init__(self, config: Config, session: Optional[requests.Session] = None):
        self.config = config
        self.session = session if session is not None else requests.Session()

    def _get(self, endpoint_kind: str, number: str) -> requests.Response:
        url, headers = build_request(self.config, endpoint_kind, number)
        try:
            return self.session.get(url, headers=headers)
        except requests.exceptions.RequestException as exc:
            raise CheckerError(
                "{provider} {kind} request failed: {exc}".format(
                    provider=self.config.provider, kind=endpoint_kind, exc=exc
                )
            ) from exc

    def _json(self, response: requests.Response, endpoint_kind: str) -> dict:
        try:
            return response.json()
        except ValueError as exc:
            raise CheckerError(
                "{provider} {kind} returned a non-JSON body: {text}".format(
                    provider=self.config.provider,
                    kind=endpoint_kind,
                    text=response.text,
                )
            ) from exc

    def fetch_live(self, number: str) -> dict:
        response = self._get("live", number)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise CheckerError(
                "{provider} live returned HTTP {code}: {text}".format(
                    provider=self.config.provider,
                    code=response.status_code,
                    text=response.text,
                )
            ) from exc
        return self._json(response, "live")

    def fetch_cache(self, number: str) -> CacheResult:
        response = self._get("cache", number)
        if response.status_code not in (_CACHE_HIT, _CACHE_MISS):
            raise CheckerError(
                "{provider} cache returned HTTP {code}: {text}".format(
                    provider=self.config.provider,
                    code=response.status_code,
                    text=response.text,
                )
            )
        return CacheResult(
            status_code=response.status_code, data=self._json(response, "cache")
        )

    def check(self, number: str) -> dict:
        mode = self.config.mode
        if mode == "live":
            return self.fetch_live(number)
        if mode == "cache_only":
            return self.fetch_cache(number).data
        if mode == "cache_first":
            try:
                result = self.fetch_cache(number)
            except CheckerError:
                return self.fetch_live(number)
            if result.status_code == _CACHE_MISS:
                return self.fetch_live(number)
            return result.data
        # Unreachable when config is validated via load_config().
        raise CheckerError("Unknown CHECK_MODE: {!r}".format(mode))
```

- [ ] **Step 5: Update package exports**

Replace `whatsosint_client/__init__.py` contents with:

```python
"""HTTP client package for WhatsOSINT number checks."""

from whatsosint_client.client import CacheResult, CheckerError, WhatsOSINTClient
from whatsosint_client.config import Config, ConfigError, load_config

__all__ = [
    "Config",
    "ConfigError",
    "load_config",
    "WhatsOSINTClient",
    "CheckerError",
    "CacheResult",
]
```

- [ ] **Step 6: Run the full suite to verify it passes**

Run: `python -m pytest tests/ -v`
Expected: PASS (config + providers + client — all green).

- [ ] **Step 7: Commit**

```bash
git add whatsosint_client/client.py whatsosint_client/__init__.py tests/test_client.py
git commit -m "feat: add checker client with cache-first/cache-only modes"
```

---

### Task 4: Wire the CLI to the client

**Files:**
- Modify: `WhatsOSINT.py`
- Test: manual smoke run (CLI is thin I/O glue; logic is covered by Task 3).

**Interfaces:**
- Consumes: `load_config`, `ConfigError`, `WhatsOSINTClient`, `CheckerError` from `whatsosint_client`.
- Produces: an interactive CLI unchanged in look (same banner, same prompt, same colored JSON), now honoring the env config.

- [ ] **Step 1: Rewrite the HTTP-calling parts of `WhatsOSINT.py`**

Replace the entire contents of `WhatsOSINT.py` with:

```python
#BY: HACK UNDERWAY

from dotenv import load_dotenv
from colorama import Fore, Style, init

from whatsosint_client import (
    CheckerError,
    ConfigError,
    WhatsOSINTClient,
    load_config,
)

# Inicializar Colorama
init(autoreset=True)

# Cargar las variables de entorno desde el archivo .env
load_dotenv()


# Función para imprimir el JSON con formato y colores
def imprimir_json_coloreado(data, nivel=0):
    indent = "    " * nivel
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{indent}{Fore.CYAN}{key}{Style.RESET_ALL}: ", end="")
            imprimir_json_coloreado(value, nivel + 1)
    elif isinstance(data, list):
        for item in data:
            imprimir_json_coloreado(item, nivel)
    else:
        print(f"{Fore.YELLOW}{data}{Style.RESET_ALL}")


# Función para consultar datos de WhatsApp usando el cliente configurado
def consultar_numero_whatsapp(client, numero_telefono):
    try:
        datos = client.check(numero_telefono)
        imprimir_json_coloreado(datos)
    except CheckerError as err:
        print(f"{Fore.RED}Error en la consulta: {err}{Style.RESET_ALL}")
    except Exception as err:
        print(f"{Fore.RED}Ocurrió un error: {err}{Style.RESET_ALL}")


def main():
    # Banner verde
    print(Fore.GREEN + """
     __i
    |---|    
    |[_]|    
    |:::|    
    |:::|    
    `\\   \\   
      \\_=_\\ 
    Consulta de datos de número de WhatsApp
    """ + Style.RESET_ALL)

    # Cargar y validar la configuración antes de pedir el número
    try:
        config = load_config()
    except ConfigError as err:
        print(f"{Fore.RED}Error de configuración: {err}{Style.RESET_ALL}")
        return

    numero = input("Introduce el número de teléfono (con código de país): ").strip()

    # Validar si se ingresó un número
    if not numero:
        print("Debe ingresar un número de teléfono válido.")
        return

    client = WhatsOSINTClient(config)
    # Consultar datos del número
    consultar_numero_whatsapp(client, numero)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test config-error path (no network, no key)**

Run (from `api/WhatsOSINT/`, forcing an invalid provider so it fails before prompting):
```bash
CHECK_PROVIDER=bogus python -c "import WhatsOSINT; WhatsOSINT.main()"
```
Expected: prints the banner then `Error de configuración: Invalid CHECK_PROVIDER='bogus'. Expected one of: rapidapi, native` and exits without prompting. (On PowerShell use `$env:CHECK_PROVIDER='bogus'; python -c "import WhatsOSINT; WhatsOSINT.main()"; Remove-Item Env:CHECK_PROVIDER`.)

- [ ] **Step 3: Smoke-test a real cache_only lookup (uses your key; optional, needs network)**

With a valid `RAPIDAPI_KEY` in `.env`, run and enter a known-cached number:
```bash
CHECK_MODE=cache_only python WhatsOSINT.py
```
Expected: colored JSON with `exists: True` for a cached number; for an unknown number, the 404 body (`error ... / code: NOT_IN_DATABASE`) prints as colored JSON without a Python traceback.

- [ ] **Step 4: Confirm the test suite is still green**

Run: `python -m pytest tests/ -v`
Expected: PASS (unchanged — CLI edits don't touch the client).

- [ ] **Step 5: Commit**

```bash
git add WhatsOSINT.py
git commit -m "refactor: delegate CLI number check to configurable client"
```

---

### Task 5: Repo hygiene + docs

**Files:**
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Modify: `.env`
- Modify: `README.md`

**Interfaces:** none (no code).

- [ ] **Step 1: Create `requirements-dev.txt`**

```
pytest
requests-mock
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
*.egg-info/
```

(Note: `.env` is intentionally NOT ignored — upstream tracks it as a placeholder template and the README instructs editing it in place.)

- [ ] **Step 3: Update `.env` (re-apply host fix + document new optional vars)**

Replace `.env` contents with:

```
RAPIDAPI_KEY=Your_Api_Key
RAPIDAPI_HOST=wp-data.p.rapidapi.com

# --- Optional: cheaper checking (all default to the values shown) ---
# CHECK_PROVIDER selects the transport:
#   rapidapi = RapidAPI marketplace (uses RAPIDAPI_KEY)
#   native   = direct checkleaked.cc host (uses NATIVE_API_KEY; separate credential)
# CHECK_PROVIDER=rapidapi
#
# CHECK_MODE selects the strategy (cheapest last):
#   live        = always a fresh live check (default; same as before)
#   cache_first = read the cache DB first, fall back to a live check on a miss
#   cache_only  = only read the cache DB, never do a live check (cheapest)
# CHECK_MODE=live
#
# RAPIDAPI_CACHE_HOST=wp-data-db-only.p.rapidapi.com
# NATIVE_API_KEY=
# NATIVE_BASE_URL=https://whatsapp-proxy.checkleaked.cc
```

- [ ] **Step 4: Update `README.md`**

Add a new section after the existing "🔑 API Key" section (before "SUPPORTED DISTRIBUTIONS"):

````markdown
# ⚙️ Checking modes (save cost)

By default WhatsOSINT does a full **live** check on every lookup. You can
switch to cheaper strategies via environment variables in your `.env`:

| `CHECK_MODE` | What it does | Cost |
| --- | --- | --- |
| `live` (default) | Always performs a fresh live WhatsApp check | Highest |
| `cache_first` | Reads the cached database first; only falls back to a live check when the number isn't cached yet | Medium |
| `cache_only` | Only reads the cached database, never does a live check | Lowest |

You can also choose the transport with `CHECK_PROVIDER`:

| `CHECK_PROVIDER` | Host | Auth |
| --- | --- | --- |
| `rapidapi` (default) | RapidAPI marketplace | `RAPIDAPI_KEY` |
| `native` | Direct `checkleaked.cc` endpoint | `NATIVE_API_KEY` (a separate, non-RapidAPI credential) |

Example `.env` for the cheapest possible checks:

```
RAPIDAPI_KEY=your_rapidapi_key
CHECK_MODE=cache_only
```

All settings are optional — omitting them reproduces the original live-check
behavior exactly.
````

Also update the existing `RAPIDAPI_HOST` references / API host mentions in the README body if any point at the old `whatsapp-data1.p.rapidapi.com` host, so the docs match the new default `wp-data.p.rapidapi.com`.

- [ ] **Step 5: Update `requirements.txt` comment pointer (optional clarity)**

Leave runtime `requirements.txt` unchanged (`requests`, `python-dotenv`, `colorama` already cover the client). Confirm no new runtime dependency was introduced.

- [ ] **Step 6: Final full-suite run**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt .gitignore .env README.md
git commit -m "docs: document check modes/providers and add dev tooling"
```

---

## Self-Review

**1. Spec coverage:**
- Two independent axes (provider × mode) → Config (Task 1) + providers (Task 2) + client dispatch (Task 3). ✓
- Env-only config surface → Task 1 `load_config`. ✓
- Back-compat default (rapidapi+live) → `test_defaults_reproduce_legacy_behavior` + `test_live_mode_calls_only_live`. ✓
- Cache-miss = 404 detection, distinct from live 400 → `fetch_cache` status check + `test_cache_first_cache_400_raises_and_skips_live`. ✓
- Native separate key + no host header → Task 1 validation + `test_native_sends_only_key_header`. ✓
- Fallback best-effort on cache error → `test_cache_first_cache_5xx/transport_error_falls_back_to_live`. ✓
- Mocked-only tests → all HTTP via `requests_mock`. ✓
- Repo hygiene + README + dev deps → Task 5. ✓
- Re-apply host fix on this branch → Task 5 Step 3 `.env`. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step has full code. ✓

**3. Type consistency:** `Config` fields, `build_request(config, endpoint_kind, number)`, `CacheResult(status_code, data)`, `fetch_live/fetch_cache/check`, `CheckerError`/`ConfigError` names are identical across Tasks 1–4 and the tests. ✓

**Deviations from spec flagged:** `build_request` 3-arg signature; `.env` kept tracked (vs untrack + `.env.example`). Both documented in "Decisions" above; the second is user-vetoable at handoff.
