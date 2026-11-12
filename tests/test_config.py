import pytest

from aerosafe.config import get_settings


@pytest.mark.parametrize("value", ["-1", "11", "invalid"])
def test_rejects_invalid_retry_limits(monkeypatch, value):
    monkeypatch.setenv("AEROSAFE_MAX_RETRIES", value)
    with pytest.raises(ValueError, match="AEROSAFE_MAX_RETRIES"):
        get_settings()


def test_allows_zero_retry_limit(monkeypatch):
    monkeypatch.setenv("AEROSAFE_MAX_RETRIES", "0")
    assert get_settings().max_retries == 0
