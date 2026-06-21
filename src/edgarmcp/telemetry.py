import atexit
import platform
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path
from typing import Callable

import httpx


def _detect_version() -> str:
    try:
        return _pkg_version("mcp-edgar")
    except PackageNotFoundError:
        return "unknown"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_sender(url: str, payload: dict) -> None:
    httpx.post(url, json=payload, timeout=3.0)


class Telemetry:
    def __init__(
        self,
        enabled: bool,
        url: str,
        cache_dir: str,
        version: str | None = None,
        sender: Callable[[str, dict], None] | None = None,
        clock: Callable[[], str] | None = None,
        flush_interval: float = 1800.0,
    ) -> None:
        self._enabled = bool(enabled) and bool(url)
        self._url = url
        self._cache_dir = cache_dir
        self._version = version if version is not None else _detect_version()
        self._sender = sender if sender is not None else _default_sender
        self._clock = clock if clock is not None else _utc_now_iso
        self._flush_interval = flush_interval
        self._lock = threading.Lock()
        self._calls: dict[str, int] = {}
        self._errors: dict[str, int] = {}
        self._install_id: str | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _install(self) -> str:
        if self._install_id is not None:
            return self._install_id
        try:
            p = Path(self._cache_dir) / ".telemetry_id"
            if p.exists():
                existing = p.read_text().strip()
                if existing:
                    self._install_id = existing
                    return existing
            new = str(uuid.uuid4())
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new)
            self._install_id = new
            return new
        except Exception:
            self._install_id = str(uuid.uuid4())
            return self._install_id

    def record(self, tool: str, ok: bool) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._calls[tool] = self._calls.get(tool, 0) + 1
            if not ok:
                self._errors[tool] = self._errors.get(tool, 0) + 1

    def _snapshot(self) -> dict | None:
        with self._lock:
            if not self._calls and not self._errors:
                return None
            calls, errors = self._calls, self._errors
            self._calls, self._errors = {}, {}
        return {
            "install_id": self._install(),
            "version": self._version,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "os": platform.system().lower(),
            "tool_calls": calls,
            "tool_errors": errors,
            "sent_at": self._clock(),
        }

    def flush(self) -> None:
        if not self._enabled:
            return
        payload = self._snapshot()
        if payload is None:
            return
        try:
            self._sender(self._url, payload)
        except Exception:
            pass

    def start(self) -> None:
        if not self._enabled:
            return
        atexit.register(self.flush)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while True:
            time.sleep(self._flush_interval)
            self.flush()
