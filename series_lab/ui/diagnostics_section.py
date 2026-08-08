from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from series_lab.charts.acf import acf_chart
from series_lab.charts.correlations import correlation_heatmap
from series_lab.charts.lag import lag_chart
from series_lab.charts.timeseries import series_color
from series_lab.services.diagnostics import (
    LAG_CONVENTION,
    autocorrelation_values,
    correlation_matrix,
    lag_correlations,
    rolling_pair_correlation,
    stationarity_tests,
    summary_statistics,
)


DIAGNOSTIC_OPTIONS = ("Summary", "Correlation", "Stationarity", "ACF", "Lag scan", "Rolling correlation")


def diagnostic_visibility(selected: str) -> dict[str, bool]:
    return {option: option == selected for option in DIAGNOSTIC_OPTIONS}


def render_diagnostics() -> None:
    st.markdown("## quick diagnostics")
    prepared = st.session_state.prepared_data
    workspace = st.session_state.workspace
    if prepared is None:
        st.caption("Build the analysis dataset before running diagnostics.")
        return
    frame = prepared.analysis
    titles = {key: item.fetched.title for key, item in workspace.items()}
    view = st.segmented_control(
        "Diagnostic",
        list(DIAGNOSTIC_OPTIONS),
        default="Summary",
        label_visibility="collapsed",
        key="diagnostic_view",
    ) or "Summary"
    if view == "Summary":
        st.caption(f"Effective common date range: {prepared.effective_start or '—'} — {prepared.effective_end or '—'}")
        table = summary_statistics(frame).rename(index=titles)
        st.dataframe(table, width="stretch")
    elif view == "Correlation":
        method = st.radio("Method", ["Pearson", "Spearman"], horizontal=True).lower()
        matrix = correlation_matrix(frame, method)
        st.plotly_chart(correlation_heatmap(matrix, titles), width="stretch", config={"displaylogo": False})
        st.caption("Correlation describes association in this prepared sample. It does not establish causality or out-of-sample predictive value.")
    elif view == "Stationarity":
        st.caption("ADF null: unit root. KPSS null: level stationarity. The 5% interpretations below are descriptive, not dashboard pass/fail signals.")
        st.dataframe(stationarity_tests(frame).rename(index=titles), width="stretch")
    elif view == "ACF":
        key = st.selectbox("Series", list(frame.columns), format_func=lambda value: titles.get(value, value))
        max_allowed = max(1, min(100, frame[key].notna().sum() - 1))
        max_lag = st.slider("Maximum lag", 1, max_allowed, min(24, max_allowed))
        try:
            st.plotly_chart(acf_chart(autocorrelation_values(frame[key], max_lag)), width="stretch", config={"displaylogo": False})
        except Exception as exc:
            st.warning(str(exc))
    elif view in {"Lag scan", "Rolling correlation"}:
        target = st.session_state.target_series_key
        if not target or target not in frame:
            st.info("Choose a research target in the workspace section to use target-oriented diagnostics.")
            return
        candidates = [key for key in frame.columns if key != target]
        if not candidates:
            st.info("Add at least one predictor candidate alongside the target.")
            return
        st.caption("TARGET: " + titles.get(target, target))
        st.caption("QuickPlot V1 does not adjust for publication lags or historical data revisions. These diagnostics are exploratory and should not be interpreted as a real-time backtest.")
        method = st.radio("Method", ["Pearson", "Spearman"], horizontal=True, key=f"{view}_method").lower()
        if view == "Lag scan":
            selected = st.multiselect("Predictor candidates", candidates, default=candidates[:1], format_func=lambda value: titles.get(value, value))
            max_lag = st.slider("Maximum lag", 1, min(100, max(1, len(frame) // 4)), min(24, max(1, len(frame) // 4)))
            st.info(LAG_CONVENTION)
            values = {key: lag_correlations(frame[target], frame[key], max_lag, method) for key in selected}
            if values:
                st.plotly_chart(lag_chart(values, titles), width="stretch", config={"displaylogo": False})
                strongest = []
                for key, series in values.items():
                    valid = series.dropna()
                    if not valid.empty:
                        lag = valid.abs().idxmax()
                        strongest.append(f"{titles.get(key, key)}: lag {lag:+d} ({valid.loc[lag]:.3f})")
                if strongest:
                    st.caption("Strongest in-sample Y→X lag association — " + "; ".join(strongest) + ". Screening evidence only; not proof of causality or out-of-sample predictability.")
        else:
            candidate = st.selectbox("Predictor candidate", candidates, format_func=lambda value: titles.get(value, value))
            max_window = max(2, min(250, len(frame)))
            window = st.slider("Rolling window (analysis periods)", 2, max_window, min(24, max_window))
            values = rolling_pair_correlation(frame[target], frame[candidate], window, method)
            fig = go.Figure(go.Scatter(x=values.index, y=values, mode="lines", line=dict(color=series_color(candidate), width=1.8), name=titles.get(candidate, candidate)))
            fig.update_layout(height=500, paper_bgcolor="#F5F5F1", plot_bgcolor="#F5F5F1", font=dict(family="IBM Plex Mono, monospace", color="#4B5149"), yaxis=dict(range=[-1.05, 1.05], gridcolor="#E1E4DC"), xaxis=dict(gridcolor="#E1E4DC"), margin=dict(l=55, r=24, t=30, b=55))
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.caption("Rolling association can vary within the prepared sample; this does not establish regimes, causality, or predictive value.")
