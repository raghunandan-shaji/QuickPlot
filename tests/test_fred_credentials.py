import pytest

from series_lab.exceptions import ProviderUnavailableError
from series_lab.models import SeriesCandidate
from series_lab.providers.fred import FredProvider
from series_lab.services.search import search_providers


class WorkingProvider:
    def search(self, query, limit=8):
        return [SeriesCandidate("bls", "X", "Working result")]


class LeakingSession:
    def get(self, *args, **kwargs):
        raise RuntimeError("request failed with api_key=SHOULD-NOT-APPEAR")


def test_fred_without_key_is_unavailable_before_network():
    provider = FredProvider("")
    provider.session = LeakingSession()
    assert provider.is_available() is False
    assert provider.availability_message() == "Configure FRED_API_KEY to search and fetch FRED series."
    with pytest.raises(ProviderUnavailableError, match="Configure FRED_API_KEY"):
        provider.search("GDP")


def test_missing_fred_key_does_not_break_other_provider_search():
    outcome = search_providers(
        {"FRED": FredProvider(""), "BLS": WorkingProvider()},
        "GDP",
        ["FRED", "BLS"],
    )
    assert [item.provider for item in outcome.results] == ["bls"]
    assert "Configure FRED_API_KEY" in outcome.failures["FRED"]


def test_fred_transport_error_cannot_expose_key_in_user_message():
    provider = FredProvider("configured-but-private")
    provider.session = LeakingSession()
    with pytest.raises(ProviderUnavailableError) as error:
        provider.search("GDP")
    assert str(error.value) == "FRED is temporarily unavailable."
    assert "configured-but-private" not in str(error.value)
    assert "SHOULD-NOT-APPEAR" not in str(error.value)
