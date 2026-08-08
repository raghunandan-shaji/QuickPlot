import pandas as pd

from series_lab.charts.acf import acf_chart
from series_lab.charts.correlations import correlation_heatmap
from series_lab.charts.lag import lag_chart
from series_lab.charts.timeseries import overlay_chart, series_color, small_multiples


def test_series_colors_are_deterministic_and_quiet():
    assert series_color("fred:GDP") == series_color("fred:GDP")
    assert series_color("fred:GDP").startswith("#")
    assert series_color("fred:GDP") in {
        "#8FA58A", "#A394B2", "#C39385", "#B6A15F", "#799E94", "#A98996",
        "#8E9E6C", "#879BA4", "#B29A7E", "#789487", "#A596B8", "#B6A171",
    }


def test_primary_charts_have_required_interactivity():
    frame = pd.DataFrame({"a": [1, 2], "b": [2, 3]}, index=pd.date_range("2024-01-01", periods=2))
    overlay = overlay_chart(frame)
    assert overlay.layout.hovermode == "x unified"
    assert overlay.layout.height == 650
    assert len(overlay.data) == 2
    multiples = small_multiples(frame)
    assert len(multiples.data) == 2
    assert multiples.layout.height >= 500


def test_diagnostic_charts_render_expected_traces():
    matrix = pd.DataFrame([[1, 0.5], [0.5, 1]], columns=["a", "b"], index=["a", "b"])
    assert len(correlation_heatmap(matrix).data) == 1
    lag_values = {"b": pd.Series([0.1, 0.5], index=[0, 1])}
    assert len(lag_chart(lag_values).data) == 1
    assert len(acf_chart(pd.Series([1.0, 0.2], index=[0, 1], name="a")).data) == 1


def test_correlation_heatmap_shortens_labels_and_keeps_full_names_in_hover():
    keys = ["copper", "brent", "copper_alt"]
    matrix = pd.DataFrame(
        [[1.0, 0.52, 0.8], [0.52, 1.0, 0.4], [0.8, 0.4, 1.0]],
        index=keys,
        columns=keys,
    )
    copper_name = "Producer Price Index by Commodity: Metals and Metal Products: Copper Wire and Cable"
    titles = {
        "copper": copper_name,
        "brent": "Global price of Brent Crude",
        "copper_alt": copper_name,
    }

    figure = correlation_heatmap(matrix, titles)
    trace = figure.data[0]

    assert list(trace.x) == ["Copper Wire PPI", "Brent Crude", "Copper Wire PPI·2"]
    assert list(trace.y) == list(trace.x)
    assert trace.customdata[0][1][0] == copper_name
    assert trace.customdata[0][1][1] == titles["brent"]
    assert "%{customdata[0]}" in trace.hovertemplate
    assert "%{customdata[1]}" in trace.hovertemplate
    assert trace.texttemplate == "%{z:.2f}"
    assert figure.layout.xaxis.tickangle == 0
