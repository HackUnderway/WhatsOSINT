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
