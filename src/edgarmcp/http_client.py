import hashlib
import json
import re
import time
from typing import Callable
from urllib.parse import urlsplit

import httpx

from .cache import Cache


class EdgarHTTPError(Exception):
    pass


class DisallowedHost(Exception):
    pass


def _redact_secrets(s: str) -> str:
    return re.sub(r"(api_key=)[^&\s]+", r"\1REDACTED", s)


class EdgarClient:
    def __init__(
        self,
        user_agent: str,
        cache: Cache,
        transport: httpx.BaseTransport | None = None,
        min_interval: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        allowed_hosts: frozenset[str] | None = None,
    ) -> None:
        self._cache = cache
        self._min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self._allowed_hosts = allowed_hosts
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            transport=transport,
            timeout=30.0,
        )

    def _throttle(self) -> None:
        if self._min_interval <= 0 or self._last_request_at is None:
            self._last_request_at = self._clock()
            return
        elapsed = self._clock() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = self._clock()

    def get_text(self, url: str, use_cache: bool = True) -> str:
        if self._allowed_hosts is not None:
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in self._allowed_hosts:
                raise DisallowedHost(_redact_secrets(url))
        if use_cache:
            cached = self._cache.get(url)
            if cached is not None:
                return cached
        self._throttle()
        resp = self._client.get(url)
        if resp.status_code != 200:
            raise EdgarHTTPError(f"GET {_redact_secrets(url)} -> {resp.status_code}")
        text = resp.text
        if use_cache:
            self._cache.set(url, text)
        return text

    def post_json(self, url: str, body, headers: dict | None = None, use_cache: bool = True) -> dict:
        if self._allowed_hosts is not None:
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in self._allowed_hosts:
                raise DisallowedHost(_redact_secrets(url))
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
        cache_key = f"{url}#{hashlib.sha256(payload.encode()).hexdigest()}"
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        self._throttle()
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        resp = self._client.post(url, content=payload, headers=req_headers)
        if resp.status_code != 200:
            raise EdgarHTTPError(f"POST {_redact_secrets(url)} -> {resp.status_code}")
        text = resp.text
        if use_cache:
            self._cache.set(cache_key, text)
        return json.loads(text)

    def get_json(self, url: str, use_cache: bool = True) -> dict:
        return json.loads(self.get_text(url, use_cache=use_cache))
