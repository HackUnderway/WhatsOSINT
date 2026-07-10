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
