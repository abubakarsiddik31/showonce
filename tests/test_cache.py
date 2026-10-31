from pathlib import Path

from showonce.cache import JsonCache, make_key


def test_roundtrip(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    key = make_key("sam", "file_1", "red block")
    assert cache.get(key) is None
    cache.set(key, {"text": "hello"})
    assert cache.get(key) == {"text": "hello"}


def test_keys_differ_by_field() -> None:
    assert make_key("sam", "a", "b") != make_key("sam", "ab")
    assert make_key("sam", "a") != make_key("plan", "a")
