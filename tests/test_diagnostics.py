import numpy as np
import pandas as pd

from series_lab.services.diagnostics import correlation_matrix, rolling_pair_correlation, stationarity_tests, summary_statistics
from series_lab.ui.diagnostics_section import DIAGNOSTIC_OPTIONS, diagnostic_visibility


def test_summary_and_pairwise_correlation():
    frame = pd.DataFrame({"a": [1, 2, 3, np.nan], "b": [2, 4, np.nan, 8]}, index=pd.date_range("2024-01-01", periods=4))
    summary = summary_statistics(frame)
    assert summary.loc["a", "observations"] == 3
    assert summary.loc["a", "missing"] == 1
    assert correlation_matrix(frame).loc["a", "b"] == 1


def test_stationarity_handles_constant_and_short_series():
    frame = pd.DataFrame({"constant": [1] * 20, "short": [1, 2, 3] + [np.nan] * 17})
    result = stationarity_tests(frame)
    assert result.loc["constant", "note"]
    assert result.loc["short", "note"]


def test_rolling_spearman_is_window_local():
    index = pd.date_range("2024-01-01", periods=6)
    target = pd.Series([1, 2, 3, 3, 2, 1], index=index)
    predictor = pd.Series([2, 4, 6, 6, 4, 2], index=index)
    result = rolling_pair_correlation(target, predictor, 3, "spearman")
    assert result.dropna().eq(1).all()


def test_all_diagnostic_choices_are_visible_but_one_panel_is_selected():
    assert DIAGNOSTIC_OPTIONS == ("Summary", "Correlation", "Stationarity", "ACF", "Lag scan", "Rolling correlation")
    for selected in DIAGNOSTIC_OPTIONS:
        visibility = diagnostic_visibility(selected)
        assert list(visibility) == list(DIAGNOSTIC_OPTIONS)
        assert sum(visibility.values()) == 1
        assert visibility[selected] is True
