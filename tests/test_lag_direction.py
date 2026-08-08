import pandas as pd
import pytest

from series_lab.services.diagnostics import LAG_CONVENTION, lag_correlations


def test_predictor_leading_target_by_three_peaks_at_positive_three():
    y = pd.Series(range(100), index=pd.date_range("2020-01-01", periods=100), dtype=float, name="Y")
    # Add curvature so adjacent lags are not all perfectly correlated.
    y = (y ** 2 + (y.index.dayofyear % 7) * 13).rename("Y")
    x = y.shift(3).rename("X")
    scan = lag_correlations(x, y, 8)
    assert scan.abs().idxmax() == 3
    assert scan.loc[3] == pytest.approx(1)


def test_required_lag_label_is_exact():
    assert LAG_CONVENTION == "Positive lag k = Y observed k periods before X."
