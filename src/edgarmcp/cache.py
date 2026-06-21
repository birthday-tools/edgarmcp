import hashlib
import os
from typing import Protocol


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...


class MemoryCache:
    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._d.get(key)

    def set(self, key: str, value: str) -> None:
        self._d[key] = value


class FileCache:
    def __init__(self, directory: str) -> None:
        self._dir = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self._dir, f"{digest}.cache")

    def get(self, key: str) -> str | None:
        try:
            with open(self._path(key), "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def set(self, key: str, value: str) -> None:
        with open(self._path(key), "w", encoding="utf-8") as f:
            f.write(value)
