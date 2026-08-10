import numpy as np
import pandas as pd

from conftest import make_workspace
from series_lab.models import PrepareConfig
from series_lab.services.diagnostics import (
    correlation_matrix,
    prepared_summary_statistics,
    rolling_pair_correlation,
    stationarity_tests,
    summary_statistics,
)
from series_lab.services.harmonize import harmonize
from series_lab.ui.diagnostics_section import DIAGNOSTIC_OPTIONS, diagnostic_visibility


def test_summary_and_pairwise_correlation():
    frame = pd.DataFrame({"a": [1, 2, 3, np.nan], "b": [2, 4, np.nan, 8]}, index=pd.date_range("2024-01-01", periods=4))
    summary = summary_statistics(frame)
    assert summary.loc["a", "observations"] == 3
    assert summary.loc["a", "missing"] == 1
    assert correlation_matrix(frame).loc["a", "b"] == 1


def test_prepared_summary_is_unchanged_when_only_transform_changes():
    first = make_workspace(
        "first",
        [10, 20, 30, 40, 50],
        pd.date_range("2024-01-01", periods=5),
    )
    second = make_workspace(
        "second",
        [2, 4, 6, 8, 10],
        pd.date_range("2024-01-02", periods=5),
    )
    config = PrepareConfig(frequency="daily", date_coverage="common_overlap")

    level_prepared = harmonize([first, second], config)
    level_summary = prepared_summary_statistics(level_prepared)

    first.transform = "z_score"
    z_score_prepared = harmonize([first, second], config)
    z_score_summary = prepared_summary_statistics(z_score_prepared)

    pd.testing.assert_frame_equal(level_summary, z_score_summary)
    assert not level_prepared.analysis["first"].equals(z_score_prepared.analysis["first"])
    assert level_summary.loc["first", "first_date"] == "2024-01-02"
    assert level_summary.loc["first", "last_date"] == "2024-01-05"


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
