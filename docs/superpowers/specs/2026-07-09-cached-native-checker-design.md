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

- **Cache-miss shape (current, post backend update on 2026-07-09)**: real HTTP
  **404**, body carries a machine-readable `"code":"NOT_IN_DATABASE"` (plus a
  redundant `"status":404` and a human-readable `"error"` string), e.g.
  `{"error":"Whatsapp number is not in the Database records","under_maintenance":false,"fbLeak":{...},"status":404,"code":"NOT_IN_DATABASE"}`.
  (The API previously returned this same body shape under HTTP 200 — the
  maintainer changed it to a real 404 mid-session; verified live against both
  providers after the change. Design below uses status-code detection, not
  body-shape sniffing, so it doesn't matter which shape ships.)
- **Live endpoint, malformed input**: HTTP **400** with
  `{"error":"Invalid phone number, please provide a valid formatted phone number, ...","success":null}`
  — this is a *distinct* case from a cache/DB miss (bad input vs. legitimately
  absent number) and must not be treated as "miss"/trigger any fallback.
- Hit shape: `"exists": true` plus full `WhatsAppEntry` fields (`phone`,
  `profilePic`, `carrierData`, `fbLeak`, etc.), HTTP 200 — confirmed
  unaffected by the not-found change (re-checked after the update).
- rapidapi provider requires both `x-rapidapi-key` and `x-rapidapi-host`
  headers (host = whichever of `RAPIDAPI_HOST` / `RAPIDAPI_CACHE_HOST`
  matches the endpoint being called).
- native provider (`checkleaked.cc`) reads the **same header name**
  (`x-rapidapi-key`) but validates it against its own key store — a RapidAPI
  marketplace key gets a distinct `"Invalid API key"` (key read, wrong value),
  while a missing/wrong header name gets `"API key missing"`. No
  `x-rapidapi-host` header is needed or checked on this domain. A working
  native-tier key was minted for this session (`pro` role) to confirm.
- **Miss vs. error distinction**: cache-miss (404) is a normal, expected
  outcome of `/number_cache` — not a transport error. It is the *only*
  non-2xx status that endpoint returns for legitimate business reasons;
  anything else (401/429/5xx) is a real error. The live endpoint's error
  conventions (400 for bad input, etc.) are untouched from today's script.

## Architecture

New package `whatsosint_client/` alongside `WhatsOSINT.py`:

- **`config.py`** — `Config` dataclass + `load_config()`: reads env vars,
  validates enums/required fields, raises `ConfigError` (a `ValueError`
  subclass) on bad input.
- **`providers.py`** — `build_request(provider, endpoint_kind, number, config)
  -> (url, headers)`, where `endpoint_kind` is `"live"` or `"cache"`. Holds
  the 2×2 provider/endpoint → (base URL, path, header set) mapping.
- **`client.py`** — `WhatsOSINTClient`:
  - `fetch_live(number) -> dict` — single HTTP call, behavior **unchanged**
    from today's script: `raise_for_status()` then `.json()`, so any non-2xx
    (400 bad input, 401, etc.) raises `CheckerError` exactly as it does now
    (preserves live-mode back-compat byte-for-byte).
  - `fetch_cache(number) -> CacheResult` (`CacheResult(status_code: int, data:
    dict)`) — treats **200 and 404 as normal business responses** (parses and
    returns the body either way); any other status (401/429/5xx) raises
    `CheckerError`. 404 is a legitimate "not in DB" outcome for this endpoint,
    not a transport error.
  - `check(number) -> dict` — dispatches on `config.mode`:
    - `live`: `fetch_live(number)`.
    - `cache_only`: `fetch_cache(number).data`, returned as-is regardless of
      status (even 404 — the caller just sees the not-found body).
    - `cache_first`: call `fetch_cache(number)`; if it raised `CheckerError`
      *or* its `status_code == 404`, fall back to `fetch_live(number)`;
      otherwise return `.data`.

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
- `fetch_live` is untouched from today: any non-2xx (400 malformed input, 401,
  etc.) raises via `raise_for_status()`, same as the current script.
- `fetch_cache` treats only `200`/`404` as business responses; `404` means
  "not in DB", not an error. Any other status (401 bad key, 429 rate limit,
  5xx) raises `CheckerError`.
- `cache_first`: falls back to `fetch_live` when the cache call either raises
  `CheckerError` (network/auth/rate-limit failure — best-effort) or returns
  `status_code == 404` (genuine cache miss). A subsequent failure on the live
  call propagates normally (no further fallback — live is the last tier).
- A `400` from `fetch_cache` (should not happen per the endpoint's contract,
  but if the upstream ever adds input validation there too) raises like any
  other non-200/404 status — it is **not** treated as a miss and does **not**
  trigger fallback, since retrying the same malformed input against live
  would just fail identically.
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
  - `live` mode calls only the live endpoint; a mocked 400 raises
    `CheckerError` (back-compat check).
  - `cache_only` mode calls only the cache endpoint and returns the 200-hit
    and 404-miss bodies untouched (asserting the 404 does *not* raise).
  - `cache_first` mode: cache hit (200) → only the cache endpoint is called
    (assert via `requests_mock` call history — live must NOT be called);
    cache miss (404) → both endpoints called, live response returned; cache
    transport/5xx/401 error → falls back to live; a mocked cache `400` raises
    `CheckerError` and does **not** call live.

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
