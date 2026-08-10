import pandas as pd

from series_lab.charts.acf import acf_chart
from series_lab.charts.correlations import correlation_heatmap
from series_lab.charts.lag import lag_chart
from series_lab.charts.timeseries import overlay_chart, series_color, small_multiples
from series_lab.services.colors import (
    SERIES_PALETTE,
    reset_series_color_override,
    set_series_color_override,
)
from series_lab.ui.series_controls import identity_html, swatch_html


def test_series_colors_are_deterministic_and_high_contrast():
    assert series_color("fred:GDP") == series_color("fred:GDP")
    assert series_color("fred:GDP").startswith("#")
    assert series_color("fred:GDP") in SERIES_PALETTE
    assert SERIES_PALETTE == (
        "#3F5F50", "#5B4E77", "#8A4F46", "#7A641F", "#2F6B68", "#7A4860",
        "#5D6F2D", "#3F6075", "#76543B", "#486A3F", "#69527E", "#8A5A2B",
    )


def test_manual_color_override_persists_and_resets_by_series_key():
    state = {"series_color_overrides": {}}
    key = "fred:GDP"
    default = series_color(key)

    set_series_color_override(state, key, "#34495e")
    reordered_keys = ["yahoo:GC=F", key]

    assert series_color(reordered_keys[1], state["series_color_overrides"]) == "#34495E"
    reset_series_color_override(state, key)
    assert series_color(key, state["series_color_overrides"]) == default


def test_manual_color_is_consistent_across_charts_and_ui_helpers():
    key = "fred:GDP"
    override = "#34495E"
    overrides = {key: override}
    frame = pd.DataFrame({key: [1, 2]}, index=pd.date_range("2024-01-01", periods=2))
    lag_values = {key: pd.Series([0.1, 0.5], index=[0, 1])}

    overlay_trace = overlay_chart(frame, color_overrides=overrides).data[0]
    multiples_trace = small_multiples(frame, color_overrides=overrides).data[0]
    lag_trace = lag_chart(lag_values, color_overrides=overrides).data[0]
    assert overlay_trace.line.color == overlay_trace.marker.color == override
    assert multiples_trace.line.color == multiples_trace.marker.color == override
    assert lag_trace.line.color == lag_trace.marker.color == override
    assert acf_chart(pd.Series([1.0, 0.2], index=[0, 1], name=key), overrides).data[0].marker.color == override
    assert f"background:{override}" in swatch_html(key, color_overrides=overrides)
    assert f"background:{override}" in identity_html(key, "GDP", color_overrides=overrides)


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
