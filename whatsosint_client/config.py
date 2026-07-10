"""Environment-driven configuration for the WhatsOSINT checker."""

import os
from dataclasses import dataclass
from typing import Mapping, Optional

VALID_PROVIDERS = ("rapidapi", "native")
VALID_MODES = ("live", "cache_first", "cache_only")

DEFAULT_RAPIDAPI_HOST = "wp-data.p.rapidapi.com"
DEFAULT_RAPIDAPI_CACHE_HOST = "wp-data-db-only.p.rapidapi.com"
DEFAULT_NATIVE_BASE_URL = "https://whatsapp-proxy.checkleaked.cc"
# Generous default: a live WhatsApp check can legitimately take many seconds,
# so this only guards against a truly hung host (see CHECK_TIMEOUT_SECONDS).
DEFAULT_TIMEOUT_SECONDS = 60.0


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
    timeout_seconds: float


def _resolve(source: Mapping[str, str], key: str, default: str) -> str:
    """Return the trimmed env value for key, falling back to default when the
    value is absent, empty, or whitespace-only."""
    return source.get(key, "").strip() or default


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

    raw_timeout = source.get("CHECK_TIMEOUT_SECONDS", "").strip()
    if raw_timeout:
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError:
            raise ConfigError(
                "Invalid CHECK_TIMEOUT_SECONDS={!r}. Expected a number.".format(
                    raw_timeout
                )
            )
        if timeout_seconds <= 0:
            raise ConfigError(
                "CHECK_TIMEOUT_SECONDS must be greater than 0 (got {}).".format(
                    timeout_seconds
                )
            )
    else:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    return Config(
        provider=provider,
        mode=mode,
        rapidapi_key=rapidapi_key,
        rapidapi_host=_resolve(source, "RAPIDAPI_HOST", DEFAULT_RAPIDAPI_HOST),
        rapidapi_cache_host=_resolve(
            source, "RAPIDAPI_CACHE_HOST", DEFAULT_RAPIDAPI_CACHE_HOST
        ),
        native_api_key=native_api_key,
        native_base_url=_resolve(
            source, "NATIVE_BASE_URL", DEFAULT_NATIVE_BASE_URL
        ),
        timeout_seconds=timeout_seconds,
    )
