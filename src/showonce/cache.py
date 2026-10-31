"""Content-addressed JSON cache so repeated runs never pay for the same API call twice."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def hash_bytes(*parts: bytes) -> str:
    """Return a stable SHA-256 hex digest over the given byte strings."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def hash_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_key(namespace: str, *fields: str | bytes | Iterable[str]) -> str:
    """Build a cache key from a namespace and any number of string fields."""
    parts: list[bytes] = [namespace.encode()]
    for field in fields:
        if isinstance(field, bytes):
            parts.append(field)
        elif isinstance(field, str):
            parts.append(field.encode())
        else:
            parts.append("\x1f".join(field).encode())
    return hash_bytes(*parts)


class JsonCache:
    """A tiny on-disk key-value store of JSON-serializable values."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value))
        tmp.replace(path)
