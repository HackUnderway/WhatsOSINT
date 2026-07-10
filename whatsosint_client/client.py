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
    """Raised on a transport failure, unexpected HTTP status, or bad body.

    ``status_code`` is the HTTP status that triggered the error, or ``None``
    for a transport-level failure (timeout, connection refused, ...) where no
    response was received. ``cache_first`` uses it to decide whether a
    fallback to the live endpoint is worthwhile.
    """

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


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
            return self.session.get(
                url, headers=headers, timeout=self.config.timeout_seconds
            )
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
                ),
                status_code=response.status_code,
            ) from exc

    @staticmethod
    def _json_or_text(response: requests.Response) -> dict:
        """Parse a body as JSON, falling back to wrapping the raw text.

        Used for the 404 cache-miss path, which must never raise on an
        unparseable body — the miss itself is the meaningful signal.
        """
        try:
            return response.json()
        except ValueError:
            return {"error": response.text, "status": response.status_code}

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
                ),
                status_code=response.status_code,
            ) from exc
        return self._json(response, "live")

    def fetch_cache(self, number: str) -> CacheResult:
        response = self._get("cache", number)
        status = response.status_code
        if status == _CACHE_MISS:
            # 404 is the cache-miss signal and must ALWAYS yield a CacheResult
            # (so cache_first falls back and cache_only returns the miss),
            # regardless of whether the body parses as JSON. A CDN/gateway can
            # front a 404 with an HTML/empty body, so tolerate a non-JSON body.
            return CacheResult(status_code=status, data=self._json_or_text(response))
        if status == _CACHE_HIT:
            return CacheResult(status_code=status, data=self._json(response, "cache"))
        raise CheckerError(
            "{provider} cache returned HTTP {code}: {text}".format(
                provider=self.config.provider, code=status, text=response.text
            ),
            status_code=status,
        )

    @staticmethod
    def _should_fall_back(error: "CheckerError") -> bool:
        """Whether a failed cache call is worth retrying against live.

        Fall back only for non-deterministic failures: a transport error
        (no status) or a server error (5xx). Client errors (4xx other than
        the 404 miss, which never reaches here) are request-level problems
        the live endpoint would reject identically, so they propagate — this
        also avoids silently spending money on a live call after a 429/400.
        """
        return error.status_code is None or error.status_code >= 500

    def check(self, number: str) -> dict:
        mode = self.config.mode
        if mode == "live":
            return self.fetch_live(number)
        if mode == "cache_only":
            return self.fetch_cache(number).data
        if mode == "cache_first":
            try:
                result = self.fetch_cache(number)
            except CheckerError as exc:
                if self._should_fall_back(exc):
                    return self.fetch_live(number)
                raise
            if result.status_code == _CACHE_MISS:
                return self.fetch_live(number)
            return result.data
        # Unreachable when config is validated via load_config().
        raise CheckerError("Unknown CHECK_MODE: {!r}".format(mode))
