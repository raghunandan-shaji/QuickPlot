import pandas as pd
import pytest

from series_lab.exceptions import SeriesResolutionError
from series_lab.models import ResolvedSeriesCandidate
from series_lab.providers.bls import BlsProvider
from series_lab.providers.eia import EiaProvider
from series_lab.providers.fred import FredProvider
from series_lab.providers.world_bank import WorldBankProvider
from series_lab.providers.yahoo import YahooProvider


def test_fred_search_parser():
    result = FredProvider.parse_search({"seriess": [{"id": "X", "title": "Example", "frequency_short": "M", "units": "Index"}]})
    assert result[0].candidate_id == "X"
    assert result[0].frequency == "M"


def test_yahoo_normalization_and_value_field():
    result = YahooProvider.normalize_quotes([{"symbol": "HG=F", "shortname": "Copper", "quoteType": "FUTURE"}])
    assert result[0].instrument_type == "FUTURE"
    raw = pd.DataFrame({"Open": [1], "Close": [2], "Adj Close": [3]}, index=pd.to_datetime(["2024-01-01"]))
    _, values, field = YahooProvider.normalize_history(raw, "yahoo:HG=F")
    assert field == "Adj Close"
    assert values.iloc[0] == 3


def test_bls_monthly_parser_excludes_m13():
    payload = {"Results": {"series": [{"data": [
        {"year": "2024", "period": "M01", "value": "10"},
        {"year": "2024", "period": "M13", "value": "99"},
    ]}]}}
    raw, values = BlsProvider.parse_series(payload, "bls:X")
    assert len(raw) == len(values) == 1
    assert values.index[0] == pd.Timestamp("2024-01-31")


def test_bls_catalog_coverage_dates_use_month_boundaries():
    row = {"begin_year": "2001", "begin_period": "M03", "end_year": "2024", "end_period": "M11"}
    assert BlsProvider._catalog_date(row, "begin") == "2001-03-01"
    assert BlsProvider._catalog_date(row, "end") == "2024-11-30"


def test_world_bank_annual_parser():
    payload = [{"pages": 1}, [{"date": "2022", "value": "12.5", "country": {"value": "Example"}}]]
    _, values, _ = WorldBankProvider.parse_observations(payload, "world_bank:EX:X")
    assert values.index[0] == pd.Timestamp("2022-12-31")
    assert values.iloc[0] == 12.5


def test_eia_numeric_string_and_unresolved_duplicates():
    payload = {"response": {"data": [{"period": "2024-01", "value": "3.4"}]}}
    raw, values = EiaProvider.parse_data(payload, "eia:x", "value")
    assert values.iloc[0] == 3.4
    duplicate = {"response": {"data": [{"period": "2024", "value": "1"}, {"period": "2024", "value": "2"}]}}
    with pytest.raises(SeriesResolutionError, match="another facet"):
        EiaProvider.parse_data(duplicate, "eia:x", "value")


def test_eia_fetch_rejects_unresolved_facets_before_network():
    candidate = ResolvedSeriesCandidate(
        provider="eia", series_key="eia:x", provider_series_id="route|value", title="Example",
        metadata={"facets": [{"id": "state"}], "value_field": "value"},
    )
    with pytest.raises(SeriesResolutionError, match="Resolve EIA facets"):
        EiaProvider("key").fetch(candidate)
