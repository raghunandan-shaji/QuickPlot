import pandas as pd
import pytest

from conftest import make_workspace
from series_lab.exceptions import FrequencyResolutionError
from series_lab.models import PrepareConfig
from series_lab.services.harmonize import harmonize


def test_daily_to_monthly_last_and_mean():
    dates = pd.date_range("2024-01-01", "2024-02-29", freq="D")
    item = make_workspace("daily", range(len(dates)), dates, "Daily")
    config = PrepareConfig(frequency="monthly", default_aggregation="last", date_coverage="full_union")
    result = harmonize([item], config)
    assert result.harmonized.iloc[0, 0] == 30
    config.default_aggregation = "mean"
    result = harmonize([item], config)
    assert result.harmonized.iloc[0, 0] == pytest.approx(15)


def test_weekly_to_monthly():
    dates = pd.date_range("2024-01-05", periods=10, freq="W-FRI")
    item = make_workspace("weekly", range(10), dates, "Weekly")
    result = harmonize([item], PrepareConfig(frequency="monthly", date_coverage="full_union"))
    assert len(result.harmonized) == 3


def test_mismatch_requires_explicit_frequency():
    daily = make_workspace("daily", [1, 2, 3], pd.date_range("2024-01-01", periods=3), "Daily")
    monthly = make_workspace("monthly", [1, 2, 3], pd.date_range("2024-01-31", periods=3, freq="ME"), "Monthly")
    with pytest.raises(FrequencyResolutionError, match="Choose a common"):
        harmonize([daily, monthly], PrepareConfig())


def test_upsampling_requires_acknowledgment():
    monthly = make_workspace("monthly", [1, 2], pd.date_range("2024-01-31", periods=2, freq="ME"), "Monthly")
    with pytest.raises(FrequencyResolutionError, match="Upsampling creates dates"):
        harmonize([monthly], PrepareConfig(frequency="daily"))
    result = harmonize([monthly], PrepareConfig(frequency="daily", upsampling_acknowledged=True, date_coverage="full_union", missing_strategy="forward_fill"))
    assert len(result.harmonized) > 2


def test_common_overlap_union_and_missing_strategies():
    a = make_workspace("a", [1, 2, 3], pd.date_range("2024-01-01", periods=3), "Daily")
    b = make_workspace("b", [4, 5, 6], pd.date_range("2024-01-02", periods=3), "Daily")
    overlap = harmonize([a, b], PrepareConfig(frequency="daily", date_coverage="common_overlap"))
    assert list(overlap.harmonized.index) == list(pd.date_range("2024-01-02", "2024-01-03"))
    union = harmonize([a, b], PrepareConfig(frequency="daily", date_coverage="full_union"))
    assert len(union.harmonized) == 4
    dropped = harmonize([a, b], PrepareConfig(frequency="daily", date_coverage="full_union", missing_strategy="drop_incomplete"))
    assert len(dropped.harmonized) == 2


def test_raw_series_is_not_mutated():
    item = make_workspace("a", [1, 2, 3], pd.date_range("2024-01-01", periods=3), "Daily")
    before = item.fetched.value_series.copy(deep=True)
    harmonize([item], PrepareConfig(frequency="monthly", date_coverage="full_union"))
    pd.testing.assert_series_equal(item.fetched.value_series, before)
