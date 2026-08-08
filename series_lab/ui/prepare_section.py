from __future__ import annotations

import streamlit as st

from series_lab.models import PrepareConfig
from series_lab.services.harmonize import harmonize, normalize_frequency
from series_lab.services.transforms import TRANSFORM_LABELS


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


def _label_for(mapping, value):
    return next((label for label, item in mapping.items() if item == value), next(iter(mapping)))


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
        st.markdown("### series settings")
        titles = {item.fetched.title: key for key, item in workspace.items()}
        selected_title = st.selectbox("Series to configure", list(titles))
        selected_item = workspace[titles[selected_title]]
        s1, s2 = st.columns(2)
        with s1:
            transform_labels = list(TRANSFORM_LABELS.values())
            current_transform = TRANSFORM_LABELS.get(selected_item.transform, "Level")
            transform_label = st.selectbox("Transform", transform_labels, index=transform_labels.index(current_transform))
        with s2:
            override_options = ["Inherit default"] + list(AGGREGATION_OPTIONS)
            current_override = _label_for(AGGREGATION_OPTIONS, selected_item.aggregation) if selected_item.aggregation else "Inherit default"
            override_label = st.selectbox("Aggregation override", override_options, index=override_options.index(current_override))
        build = st.form_submit_button("apply settings and build analysis dataset")
    if build:
        config.frequency = FREQUENCY_OPTIONS[frequency_label]
        config.date_coverage = COVERAGE_OPTIONS[coverage_label]
        config.missing_strategy = MISSING_OPTIONS[missing_label]
        config.default_aggregation = AGGREGATION_OPTIONS[aggregation_label]
        config.upsampling_acknowledged = acknowledged
        selected_item.transform = next(key for key, label in TRANSFORM_LABELS.items() if label == transform_label)
        selected_item.aggregation = None if override_label == "Inherit default" else AGGREGATION_OPTIONS[override_label]
        try:
            with st.spinner("Building harmonized and analysis layers…"):
                st.session_state.prepared_data = harmonize(list(workspace.values()), config)
        except Exception as exc:
            st.session_state.prepared_data = None
            st.error(str(exc))
    st.markdown("### current preparation")
    for item in workspace.values():
        left, right = st.columns([0.6, 0.4])
        left.write(item.fetched.title)
        right.caption(f"{TRANSFORM_LABELS.get(item.transform, item.transform)} · {item.aggregation or 'inherit aggregation'}")
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
