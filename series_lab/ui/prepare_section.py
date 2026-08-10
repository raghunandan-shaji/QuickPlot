from __future__ import annotations

import html
from hashlib import sha1

import streamlit as st

from series_lab.models import PrepareConfig
from series_lab.services.harmonize import harmonize, normalize_frequency
from series_lab.services.preparation import apply_aggregation_setting, apply_transform_setting
from series_lab.services.transforms import TRANSFORM_LABELS
from series_lab.ui.series_controls import render_color_editor


FREQUENCY_OPTIONS = {
    "Choose / keep common source frequency": None,
    "Daily": "daily",
    "Business daily": "business_daily",
    "Weekly (Friday)": "weekly",
    "Monthly (month end)": "monthly",
    "Quarterly (quarter end)": "quarterly",
    "Annual (year end)": "annual",
}
COVERAGE_OPTIONS = {"Common overlap": "common_overlap", "Full union": "full_union"}
MISSING_OPTIONS = {"Leave missing": "leave_missing", "Forward fill": "forward_fill", "Time interpolation": "time_interpolation", "Drop incomplete dates": "drop_incomplete"}
AGGREGATION_OPTIONS = {"Last observation": "last", "First observation": "first", "Mean": "mean", "Sum": "sum", "Median": "median"}
INLINE_TRANSFORM_LABELS = {**TRANSFORM_LABELS, "percent_change": "% change"}


def _label_for(mapping, value):
    return next((label for label, item in mapping.items() if item == value), next(iter(mapping)))


def _series_token(series_key: str) -> str:
    return sha1(series_key.encode()).hexdigest()[:12]


def _store_prepared(build) -> None:
    try:
        with st.spinner("Building harmonized and analysis layers…"):
            st.session_state.prepared_data = build()
        st.session_state.prepare_inline_error = None
    except Exception as exc:
        st.session_state.prepared_data = None
        st.session_state.prepare_inline_error = str(exc)


def _render_editable_row(series_key, item, workspace, config) -> None:
    token = _series_token(series_key)
    current_transform = INLINE_TRANSFORM_LABELS.get(item.transform, item.transform)
    current_aggregation = _label_for(AGGREGATION_OPTIONS, item.aggregation).lower() if item.aggregation else "inherit aggregation"
    last_change = st.session_state.prepare_last_transform_change
    show_apply_all = (
        last_change == (series_key, item.transform)
        and len(workspace) > 1
        and any(other.transform != item.transform for other in workspace.values())
    )

    with st.container(key=f"prep_row_{token}"):
        swatch, title, transform, dot, aggregation, bulk = st.columns(
            [0.04, 0.48, 0.14, 0.025, 0.20, 0.115], vertical_alignment="center"
        )
        with swatch:
            render_color_editor(series_key, "preparation")
        title.markdown(f'<div class="prep-series-title">{html.escape(item.fetched.title)}</div>', unsafe_allow_html=True)
        with transform:
            with st.popover(current_transform):
                for method, label in INLINE_TRANSFORM_LABELS.items():
                    if st.button(label, key=f"prep-transform:{series_key}:{method}", disabled=method == item.transform, width="stretch"):
                        _store_prepared(
                            lambda: apply_transform_setting(workspace, series_key, method, config)
                        )
                        st.session_state.prepare_last_transform_change = (series_key, method)
                        st.rerun()
        dot.markdown('<div class="prep-separator">·</div>', unsafe_allow_html=True)
        with aggregation:
            with st.popover(current_aggregation):
                choices = [(None, "inherit aggregation"), *[(value, label.lower()) for label, value in AGGREGATION_OPTIONS.items()]]
                for value, label in choices:
                    if st.button(label, key=f"prep-aggregation:{series_key}:{value or 'inherit'}", disabled=value == item.aggregation, width="stretch"):
                        _store_prepared(
                            lambda: apply_aggregation_setting(workspace, series_key, value, config)
                        )
                        st.rerun()
        with bulk:
            if show_apply_all and st.button("apply to all", key=f"prep-apply-all:{series_key}:{item.transform}"):
                _store_prepared(
                    lambda: apply_transform_setting(
                        workspace,
                        series_key,
                        item.transform,
                        config,
                        apply_to_all=True,
                    )
                )
                st.session_state.prepare_last_transform_change = None
                st.rerun()


def render_prepare() -> None:
    st.markdown("## prepare")
    workspace = st.session_state.workspace
    if not workspace:
        st.caption("Add series to configure the research sample.")
        return
    config: PrepareConfig = st.session_state.prepare_config
    source_frequencies = {normalize_frequency(item.fetched.metadata.get("frequency"), item.fetched.value_series.index) for item in workspace.values()}
    if len(source_frequencies - {None}) > 1:
        st.info("Source frequencies differ. Choose a common analysis frequency explicitly; QuickPlot will not resolve the mismatch silently.")

    with st.form("prepare_form"):
        st.markdown("### common alignment")
        c1, c2 = st.columns(2)
        with c1:
            frequency_label = st.selectbox("Analysis frequency", list(FREQUENCY_OPTIONS), index=list(FREQUENCY_OPTIONS).index(_label_for(FREQUENCY_OPTIONS, config.frequency)))
            coverage_label = st.selectbox("Date coverage", list(COVERAGE_OPTIONS), index=list(COVERAGE_OPTIONS).index(_label_for(COVERAGE_OPTIONS, config.date_coverage)))
        with c2:
            missing_label = st.selectbox("Missing values", list(MISSING_OPTIONS), index=list(MISSING_OPTIONS).index(_label_for(MISSING_OPTIONS, config.missing_strategy)))
            aggregation_label = st.selectbox("Default aggregation", list(AGGREGATION_OPTIONS), index=list(AGGREGATION_OPTIONS).index(_label_for(AGGREGATION_OPTIONS, config.default_aggregation)))
        acknowledged = st.checkbox("I understand that upsampling creates dates with no original observation", value=config.upsampling_acknowledged)
        build = st.form_submit_button("apply alignment and rebuild analysis dataset")
    if build:
        config.frequency = FREQUENCY_OPTIONS[frequency_label]
        config.date_coverage = COVERAGE_OPTIONS[coverage_label]
        config.missing_strategy = MISSING_OPTIONS[missing_label]
        config.default_aggregation = AGGREGATION_OPTIONS[aggregation_label]
        config.upsampling_acknowledged = acknowledged
        _store_prepared(lambda: harmonize(list(workspace.values()), config))

    st.markdown("### current preparation")
    for series_key, item in workspace.items():
        _render_editable_row(series_key, item, workspace, config)
    if st.session_state.prepare_inline_error:
        st.caption(f"Preparation unavailable — {st.session_state.prepare_inline_error}")

    prepared = st.session_state.prepared_data
    if prepared:
        valid_analysis = prepared.analysis.dropna(how="all")
        analysis_start = valid_analysis.index.min().date().isoformat() if not valid_analysis.empty else prepared.effective_start
        analysis_end = valid_analysis.index.max().date().isoformat() if not valid_analysis.empty else prepared.effective_end
        frequency = config.frequency or normalize_frequency(None, prepared.analysis.index) or "frequency unresolved"
        transformed = sum(item.transform != "level" for item in workspace.values())
        levels = len(workspace) - transformed
        coverage = "common overlap" if config.date_coverage == "common_overlap" else "full union"
        st.markdown(
            f"""
            <div class="analysis-summary">
              <div class="analysis-status">✓ analysis dataset updated</div>
              <div class="analysis-range">{analysis_start or '—'} → {analysis_end or '—'}</div>
              <div class="analysis-meta">{len(workspace)} series · {frequency.replace('_', ' ')} · {coverage}</div>
              <div class="analysis-meta">{transformed} transformed · {levels} level</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for warning in prepared.warnings:
            st.warning(warning)
        if config.missing_strategy in {"forward_fill", "time_interpolation"}:
            st.caption("Synthetic or repeated values can be inappropriate for forecasting or backtesting. QuickPlot V1 is an exploratory workspace.")
