# Cached + Native Checker Support — Design Spec

## Context

`WhatsOSINT.py` currently makes one live request per lookup to the RapidAPI
marketplace host (`RAPIDAPI_HOST`, `GET /number/{number}`). Every lookup pays
full live-check price even when the number was already checked before.

The upstream API now also exposes:
- A **cache-only** endpoint (`GET /number_cache/{number}`) that reads from the
  existing database without doing a live check — cheaper.
- A **native** domain (`https://whatsapp-proxy.checkleaked.cc`) that serves
  the same paths directly, bypassing the RapidAPI marketplace.

Goal: let a user pick a cheaper checking strategy (cache-first-then-live-fallback,
or cache-only) and/or a cheaper transport (native vs RapidAPI), without
changing default behavior for existing users.

## Non-goals

- No CLI flags — config is env-only (`.env`), matching the script's existing
  single-purpose/interactive style.
- No retry/backoff logic.
- No bulk-check support — script stays single-number, matching current scope.
- No change to default behavior when no new env var is set.

## Config (`.env`)

| Var | Default | Notes |
|---|---|---|
| `RAPIDAPI_KEY` | — | existing, RapidAPI marketplace key |
| `RAPIDAPI_HOST` | `wp-data.p.rapidapi.com` | existing, live endpoint host |
| `RAPIDAPI_CACHE_HOST` | `wp-data-db-only.p.rapidapi.com` | new, cache endpoint host |
| `NATIVE_API_KEY` | — | new, **separate credential** from `RAPIDAPI_KEY` (see Empirical findings) — required only when `CHECK_PROVIDER=native` |
| `NATIVE_BASE_URL` | `https://whatsapp-proxy.checkleaked.cc` | new, override for testing |
| `CHECK_PROVIDER` | `rapidapi` | new, `rapidapi` \| `native` |
| `CHECK_MODE` | `live` | new, `live` \| `cache_first` \| `cache_only` |

Validation happens at startup, before any network call:
- Unknown `CHECK_PROVIDER` / `CHECK_MODE` value → `ConfigError`, clear message, exit non-zero.
- `CHECK_PROVIDER=native` with `NATIVE_API_KEY` unset → `ConfigError`.

## Empirical findings (verified live this session)

- Miss shape is identical across both endpoints and both providers: HTTP
  **200** with a top-level `"error"` string and no `"exists"` key, e.g.
  `{"error":"Whatsapp number is not in the Database records","under_maintenance":false,"fbLeak":{...}}`.
- Hit shape: `"exists": true` plus full `WhatsAppEntry` fields (`phone`,
  `profilePic`, `carrierData`, `fbLeak`, etc.) — identical shape from cache
  and live once a number is cached.
- rapidapi provider requires both `x-rapidapi-key` and `x-rapidapi-host`
  headers (host = whichever of `RAPIDAPI_HOST` / `RAPIDAPI_CACHE_HOST`
  matches the endpoint being called).
- native provider (`checkleaked.cc`) reads the **same header name**
  (`x-rapidapi-key`) but validates it against its own key store — a RapidAPI
  marketplace key gets a distinct `"Invalid API key"` (key read, wrong value),
  while a missing/wrong header name gets `"API key missing"`. No
  `x-rapidapi-host` header is needed or checked on this domain. A working
  native-tier key was minted for this session (`pro` role) to confirm.
- **Miss vs. error distinction**: a "miss" is a normal 200 response, not an
  HTTP error — `raise_for_status()`-style handling is untouched; the miss
  check is purely a body-shape check performed after a successful HTTP call.

## Architecture

New package `whatsosint_client/` alongside `WhatsOSINT.py`:

- **`config.py`** — `Config` dataclass + `load_config()`: reads env vars,
  validates enums/required fields, raises `ConfigError` (a `ValueError`
  subclass) on bad input.
- **`providers.py`** — `build_request(provider, endpoint_kind, number, config)
  -> (url, headers)`, where `endpoint_kind` is `"live"` or `"cache"`. Holds
  the 2×2 provider/endpoint → (base URL, path, header set) mapping.
- **`client.py`** — `WhatsOSINTClient`:
  - `fetch_live(number)`, `fetch_cache(number)` — single HTTP calls via a
    `requests.Session`, each raising `CheckerError` (wraps
    `requests.exceptions.RequestException` with provider/endpoint context)
    on transport/HTTP failure.
  - `is_miss(data: dict) -> bool`: `"error" in data and "exists" not in data`.
  - `check(number)` — dispatches on `config.mode`:
    - `live`: `fetch_live(number)`.
    - `cache_only`: `fetch_cache(number)`, returned as-is (even if a miss).
    - `cache_first`: `fetch_cache(number)`; on transport/HTTP failure *or*
      `is_miss()`, fall back to `fetch_live(number)`; otherwise return the
      cache result.

`WhatsOSINT.py` changes: `consultar_numero_whatsapp(number)` builds a
`Config`/`WhatsOSINTClient` and delegates to `client.check(number)` instead of
calling `requests.get` directly. `imprimir_json_coloreado` and the
interactive prompt are unchanged.

## Data flow

phone number input → `WhatsOSINTClient.check(number)` → provider+mode select
endpoint(s) → single normalized dict returned → printed via the existing
`imprimir_json_coloreado`. `cache_first` never merges cache+live data — it
returns whichever single response was the last one fetched.

## Error handling

- Any transport/HTTP failure raises `CheckerError` with provider/endpoint
  context; `WhatsOSINT.py` keeps its existing top-level try/except in
  `consultar_numero_whatsapp` for user-facing colored error output.
- `cache_first`: a transport/HTTP failure on the *cache* call is treated like
  a miss (falls back to live, best-effort); a failure on the subsequent live
  call propagates normally.
- Config errors fail fast (before any network call) with a clear message,
  mirroring the script's existing guard for empty phone number input.

## Testing

New `requirements-dev.txt`: `pytest`, `requests-mock`.

- `tests/test_config.py` — defaults; each valid enum value; invalid
  `CHECK_PROVIDER`/`CHECK_MODE` raises `ConfigError`; `native` provider
  without `NATIVE_API_KEY` raises `ConfigError`.
- `tests/test_providers.py` — `build_request()` produces the correct
  url/headers for all 4 provider×endpoint combinations.
- `tests/test_client.py` (via `requests_mock`, parametrized over both
  providers):
  - `live` mode calls only the live endpoint.
  - `cache_only` mode calls only the cache endpoint and returns hit/miss
    bodies untouched.
  - `cache_first` mode: cache hit → only the cache endpoint is called (assert
    via `requests_mock` call history — live must NOT be called); cache miss →
    both endpoints called, live response returned; cache transport error →
    falls back to live.

No committed test hits the real third-party API — all HTTP is mocked, so the
suite needs no live credentials and costs nothing to run in CI. The real-API
verification already performed this session (see Empirical findings) is
documented here, not automated.

## Repo hygiene bundled in

- Add `.gitignore` (`.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`).
- Add `.env.example` (placeholders for every var in the Config table above),
  committed in place of the real `.env`.
- Stop tracking the real `.env` going forward (currently committed with a
  placeholder key).

## README updates

Document the new env vars, the 3 modes, the 2 providers, and the cost
rationale. Note that the native provider needs a separately-issued key (not
the RapidAPI marketplace key) — exact distribution process for that key is
outside this script's scope and left to the PR description/maintainer.

## Backward compatibility

Default config (`CHECK_PROVIDER=rapidapi`, `CHECK_MODE=live`) produces the
same request as today's script — existing users see no behavior change
unless they opt into a new env var.

## Open item

A native-tier test key (`pro` role, 100k/month quota) was minted in
production during this session's verification and is not referenced in any
committed file. Pending user decision to keep or delete it.
