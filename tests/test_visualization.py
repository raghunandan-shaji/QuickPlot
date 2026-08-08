from collections import OrderedDict

import numpy as np
import pandas as pd

from conftest import make_workspace
from series_lab.charts.timeseries import overlay_chart
from series_lab.models import PrepareConfig, PreparedData
from series_lab.services.harmonize import harmonize
from series_lab.services.visualization import (
    DATE_RANGE_OPTIONS,
    build_layer_frame,
    filter_date_window,
    frame_bounds,
    layer_bounds_by_series,
    visible_series_keys,
)


def sample_layers():
    first = make_workspace("first", range(11), pd.date_range("2010-12-31", periods=11, freq="YE"), "Annual")
    second = make_workspace("second", range(8), pd.date_range("2015-12-31", periods=8, freq="YE"), "Annual")
    workspace = OrderedDict([(first.series_key, first), (second.series_key, second)])
    index = pd.date_range("2016-12-31", periods=5, freq="YE")
    harmonized = pd.DataFrame({"first": range(5), "second": range(10, 15)}, index=index, dtype=float)
    analysis = harmonized.copy()
    analysis.iloc[0] = pd.NA
    prepared = PreparedData(harmonized, analysis, "2016-12-31", "2020-12-31")
    return workspace, prepared


def test_full_sample_uses_selected_layer_bounds():
    workspace, prepared = sample_layers()
    keys = list(workspace)
    raw = build_layer_frame(workspace, prepared, keys, "Raw")
    harmonized = build_layer_frame(workspace, prepared, keys, "Harmonized")
    analysis = build_layer_frame(workspace, prepared, keys, "Prepared analysis")
    assert frame_bounds(raw) == (pd.Timestamp("2010-12-31"), pd.Timestamp("2022-12-31"))
    assert frame_bounds(harmonized) == (pd.Timestamp("2016-12-31"), pd.Timestamp("2020-12-31"))
    assert frame_bounds(analysis) == (pd.Timestamp("2017-12-31"), pd.Timestamp("2020-12-31"))
    assert filter_date_window(raw, "Full").equals(raw)


def test_every_visible_date_window_and_custom_range():
    frame = pd.DataFrame({"x": range(21)}, index=pd.date_range("2000-12-31", periods=21, freq="YE"))
    expected_starts = {"1Y": "2019-12-31", "3Y": "2017-12-31", "5Y": "2015-12-31", "10Y": "2010-12-31"}
    assert DATE_RANGE_OPTIONS == ("Full", "1Y", "3Y", "5Y", "10Y", "Custom")
    assert frame_bounds(filter_date_window(frame, "Full")) == (pd.Timestamp("2000-12-31"), pd.Timestamp("2020-12-31"))
    assert filter_date_window(frame, None).equals(frame)
    for option, expected in expected_starts.items():
        assert frame_bounds(filter_date_window(frame, option))[0] == pd.Timestamp(expected)
    custom = filter_date_window(frame, "Custom", "2007-01-01", "2012-12-31")
    assert frame_bounds(custom) == (pd.Timestamp("2007-12-31"), pd.Timestamp("2012-12-31"))


def test_plot_x_axis_ends_at_final_observation():
    frame = pd.DataFrame({"x": [1, 2, 3]}, index=pd.to_datetime(["2018-01-01", "2020-01-01", "2021-06-30"]))
    figure = overlay_chart(frame)
    assert pd.Timestamp(figure.layout.xaxis.range[0]) == pd.Timestamp("2018-01-01")
    assert pd.Timestamp(figure.layout.xaxis.range[1]) == pd.Timestamp("2021-06-30")
    assert figure.layout.xaxis.autorange is False


def test_hidden_series_stays_in_workspace_but_not_figure():
    workspace, prepared = sample_layers()
    workspace["second"].visible = False
    keys = visible_series_keys(workspace)
    assert list(workspace) == ["first", "second"]
    assert keys == ["first"]
    frame = build_layer_frame(workspace, prepared, keys, "Harmonized")
    figure = overlay_chart(frame)
    assert [trace.name for trace in figure.data] == ["first"]


def test_per_series_layer_bounds_are_auditable():
    workspace, prepared = sample_layers()
    bounds = layer_bounds_by_series(workspace, prepared, list(workspace))
    assert bounds["first"]["Raw"][0] == pd.Timestamp("2010-12-31")
    assert bounds["second"]["Raw"][1] == pd.Timestamp("2022-12-31")
    assert bounds["first"]["Prepared analysis"][0] == pd.Timestamp("2017-12-31")


def test_mixed_quarter_timestamp_conventions_create_two_drawable_prepared_traces():
    quarter_start = make_workspace(
        "quarter_start",
        [100, 110, 120, 130],
        pd.to_datetime(["2023-01-01", "2023-04-01", "2023-07-01", "2023-10-01"]),
        "Quarterly",
    )
    month_start = make_workspace(
        "month_start",
        range(1, 13),
        pd.date_range("2023-01-01", periods=12, freq="MS"),
        "Monthly",
        transform="log_level",
    )
    workspace = OrderedDict((item.series_key, item) for item in (quarter_start, month_start))
    prepared = harmonize(list(workspace.values()), PrepareConfig(frequency="quarterly"))
    frame = build_layer_frame(workspace, prepared, list(workspace), "Prepared analysis")
    figure = overlay_chart(frame)

    assert list(frame.columns) == ["quarter_start", "month_start"]
    assert len(figure.data) == 2
    for trace in figure.data:
        finite = np.isfinite(pd.to_numeric(pd.Series(trace.y), errors="coerce"))
        assert finite.sum() >= 2
        assert (finite.astype(int).rolling(2).sum() == 2).any()
