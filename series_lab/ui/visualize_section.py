from __future__ import annotations

import streamlit as st

from series_lab.charts.timeseries import overlay_chart, small_multiples
from series_lab.services.transforms import TRANSFORM_LABELS
from series_lab.services.visualization import (
    DATA_LAYERS,
    DATE_RANGE_OPTIONS,
    build_layer_frame,
    filter_date_window,
    frame_bounds,
    layer_bounds_by_series,
)
from series_lab.ui.series_controls import identity_html, render_color_editor, visibility_widget_key


def _date_label(value) -> str:
    return value.date().isoformat() if value is not None else "—"


def _layer_note(layer: str, frame, coverage_policy: str) -> str:
    start, end = frame_bounds(frame)
    if layer == "Prepared analysis":
        policy = "common-overlap alignment" if coverage_policy == "common_overlap" else "full-union alignment"
        return f"Prepared analysis range: {_date_label(start)} to {_date_label(end)} · {policy}."
    if layer == "Harmonized":
        policy = "common overlap" if coverage_policy == "common_overlap" else "full union"
        return f"Harmonized range: {_date_label(start)} to {_date_label(end)} · {policy}."
    return f"Raw range: {_date_label(start)} to {_date_label(end)} · union of selected raw histories."


def render_visualize() -> None:
    st.markdown("## visualize")
    workspace = st.session_state.workspace
    prepared = st.session_state.prepared_data
    if not workspace or prepared is None:
        st.caption("Build the analysis dataset in prepare before visualizing.")
        return

    st.markdown("### series shown")
    with st.container(height=min(300, max(116, 58 * len(workspace))), border=True, key="series_shown_region"):
        for key, item in workspace.items():
            widget_key = visibility_widget_key(key)
            if widget_key not in st.session_state:
                st.session_state[widget_key] = item.visible
            swatch, left, right = st.columns([0.05, 0.83, 0.12], vertical_alignment="center")
            with swatch:
                render_color_editor(key, "series_shown", muted=not st.session_state[widget_key])
            with left:
                transform_detail = TRANSFORM_LABELS.get(item.transform, item.transform)
                st.markdown(identity_html(key, item.fetched.title, muted=not st.session_state[widget_key], detail=transform_detail, include_swatch=False), unsafe_allow_html=True)
            with right:
                shown = st.checkbox(
                    f"Show {item.fetched.title}",
                    key=widget_key,
                    label_visibility="collapsed",
                    help=f"Show or hide {item.fetched.title} without removing it from the workspace.",
                )
            item.visible = shown

    selected = [key for key, item in workspace.items() if item.visible]
    if not selected:
        st.caption("No series are currently shown. Enable at least one series above.")
        return

    left_controls, right_controls = st.columns(2)
    with left_controls:
        st.markdown("### layout")
        layout = st.segmented_control("Layout", ["Overlay", "Small multiples"], default="Overlay", label_visibility="collapsed", key="visual_layout") or "Overlay"
        st.markdown("### data layer")
        layer = st.segmented_control("Data layer", list(DATA_LAYERS), default="Prepared analysis", label_visibility="collapsed", key="visual_layer") or "Prepared analysis"
    with right_controls:
        st.markdown("### y scale")
        y_scale = st.segmented_control("Y scale", ["Linear", "Log"], default="Linear", label_visibility="collapsed", key="visual_y_scale") or "Linear"
        st.markdown("### display")
        d1, d2 = st.columns(2)
        with d1:
            legend = st.checkbox("Legend", value=True, key="visual_legend")
            grid = st.checkbox("Subtle grid", value=True, key="visual_grid")
        with d2:
            rangeslider = st.checkbox("Range slider", value=False, disabled=layout == "Small multiples", key="visual_range_slider")
            markers = st.checkbox("Markers", value=False, key="visual_markers")

    base_frame = build_layer_frame(workspace, prepared, selected, layer)
    if base_frame.empty:
        st.warning("The selected data layer has no usable observations for the shown series.")
        return
    st.markdown("### date range")
    date_range = st.segmented_control(
        "Date range",
        list(DATE_RANGE_OPTIONS),
        default="Full",
        label_visibility="collapsed",
        key="visual_date_range",
    ) or "Full"
    custom_start = custom_end = None
    if date_range == "Custom":
        bound_start, bound_end = frame_bounds(base_frame)
        c1, c2 = st.columns(2)
        with c1:
            custom_start = st.date_input("Start date", value=bound_start.date(), min_value=bound_start.date(), max_value=bound_end.date(), key="visual_custom_start")
        with c2:
            custom_end = st.date_input("End date", value=bound_end.date(), min_value=bound_start.date(), max_value=bound_end.date(), key="visual_custom_end")
    try:
        frame = filter_date_window(base_frame, date_range, custom_start, custom_end)
    except ValueError as exc:
        st.warning(str(exc))
        return

    config = st.session_state.prepare_config
    st.caption(_layer_note(layer, base_frame, config.date_coverage))
    if date_range != "Full":
        shown_start, shown_end = frame_bounds(frame)
        st.caption(f"Displayed range: {_date_label(shown_start)} to {_date_label(shown_end)}.")

    titles = {key: item.fetched.title for key, item in workspace.items()}
    chart_titles = dict(titles)
    if layer == "Prepared analysis":
        chart_titles = {
            key: f"{titles[key]} · {TRANSFORM_LABELS.get(workspace[key].transform, workspace[key].transform)}"
            for key in selected
        }
        transform_summary = " · ".join(chart_titles[key] for key in selected)
        st.caption("Transforms shown: " + transform_summary)

    if y_scale == "Log" and (frame <= 0).any().any():
        st.warning("Logarithmic display omits or cannot represent non-positive values.")
    units = {str(workspace[key].fetched.metadata.get("units")) for key in selected if workspace[key].fetched.metadata.get("units")}
    if layer != "Prepared analysis" and len(units) > 1:
        st.caption("These series use different units/scales. Consider z-score or rebase-to-100 for visual comparison.")
    if layout == "Small multiples" and len(selected) > 10:
        st.warning("Small multiples are limited to 10 displayed series for readability. Select a smaller display subset; the workspace is unchanged.")
        return
    if frame.empty:
        st.warning("No observations fall inside the selected date range.")
        return

    if layout == "Overlay":
        fig = overlay_chart(
            frame,
            chart_titles,
            legend,
            grid,
            rangeslider,
            markers,
            y_scale == "Log",
            st.session_state.series_color_overrides,
        )
    else:
        fig = small_multiples(
            frame,
            chart_titles,
            grid,
            markers,
            y_scale == "Log",
            st.session_state.series_color_overrides,
        )
    st.plotly_chart(fig, width="stretch", config={"responsive": True, "displaylogo": False, "scrollZoom": True})
    st.session_state.main_chart_html = fig.to_html(include_plotlyjs="cdn", full_html=True)

    with st.expander("sample bounds by series"):
        bounds = layer_bounds_by_series(workspace, prepared, selected)
        for key in selected:
            raw = bounds[key]["Raw"]
            harmonized = bounds[key]["Harmonized"]
            analysis = bounds[key]["Prepared analysis"]
            st.caption(
                f"{titles[key]} · raw {_date_label(raw[0])} → {_date_label(raw[1])} · "
                f"harmonized {_date_label(harmonized[0])} → {_date_label(harmonized[1])} · "
                f"analysis {_date_label(analysis[0])} → {_date_label(analysis[1])}"
            )
