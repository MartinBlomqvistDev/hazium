"""HTTP retrieval for snapshot collectors.

Deliberately small and dependency-free (``urllib``), matching the existing
adapters in ``hazium.sources``. Retries cover transient network faults and
server-side rate limiting; a 4xx other than 429 is not retried, because a bad
request will not become a good one.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request

USER_AGENT = "hazium/0.1 (github.com/MartinBlomqvistDev/hazium; research)"
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3.0

#: Retried: rate limiting and server-side faults.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """A source could not be retrieved after exhausting retries."""


def http_get(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    headers: dict[str, str] | None = None,
    sleep=time.sleep,
) -> bytes:
    """Fetch ``url`` and return the raw body.

    Args:
        url: Absolute URL.
        timeout: Per-attempt socket timeout in seconds.
        retries: Total attempts before giving up.
        headers: Extra request headers, merged over the default user agent.
        sleep: Injected for tests; defaults to ``time.sleep``.

    Returns:
        The response body.

    Raises:
        FetchError: If every attempt fails, or the server returns a
            non-retryable error status.
    """
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)

    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRYABLE_STATUS:
                raise FetchError(f"{url} returned HTTP {exc.code}") from exc
        except Exception as exc:  # noqa: BLE001 - transient network faults
            last = exc
        if attempt < retries - 1:
            sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

    raise FetchError(f"{url} failed after {retries} attempts: {last}")
