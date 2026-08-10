import numpy as np
import pytest

from conftest import make_workspace
from series_lab.exceptions import SeriesFetchError
from series_lab.models import SeriesCandidate, resolve_candidate
from series_lab.services.fetch import fetch_resolved


class CountingFetcher:
    label = "FRED"

    def __init__(self, fetched):
        self.fetched = fetched
        self.calls = 0

    def fetch(self, candidate, start=None, end=None):
        self.calls += 1
        return self.fetched


def test_identical_series_fetch_is_cached():
    fetched = make_workspace("fred:X", [1, 2], ["2024-01-01", "2024-01-02"]).fetched
    provider = CountingFetcher(fetched)
    candidate = resolve_candidate(SeriesCandidate("fred", "X", "Example"))
    first = fetch_resolved({"FRED": provider}, candidate)
    second = fetch_resolved({"FRED": provider}, candidate)
    assert provider.calls == 1
    assert first is not second


def test_all_missing_fetch_is_rejected_before_workspace_addition():
    fetched = make_workspace("fred:EMPTY", [np.nan, np.nan], ["2024-01-01", "2024-01-02"]).fetched
    provider = CountingFetcher(fetched)
    candidate = resolve_candidate(SeriesCandidate("fred", "EMPTY", "Empty example"))
    with pytest.raises(SeriesFetchError, match="no usable observations"):
        fetch_resolved({"FRED": provider}, candidate)
