import pytest

from showonce.config import Settings


def test_reads_model_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "secret")
    assert Settings(_env_file=None).require_api_key() == "secret"


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        Settings(_env_file=None).require_api_key()


def test_key_is_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "secret")
    assert "secret" not in repr(Settings(_env_file=None))
