from __future__ import annotations

from datetime import datetime

import streamlit as st

from series_lab.services.export import analysis_csv, research_bundle


def render_export() -> None:
    st.markdown("## export")
    prepared = st.session_state.prepared_data
    if prepared is None:
        st.caption("Build the analysis dataset to enable research-ready exports.")
        return
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("download analysis CSV", analysis_csv(prepared), file_name=f"quickplot-analysis-{stamp}.csv", mime="text/csv", width="stretch")
    with c2:
        try:
            bundle = research_bundle(
                st.session_state.workspace.values(), st.session_state.prepare_config, prepared,
                st.session_state.target_series_key, st.session_state.get("main_chart_html"),
            )
            st.download_button("download research bundle", bundle, file_name=f"quickplot-research-{stamp}.zip", mime="application/zip", width="stretch")
        except Exception as exc:
            st.error(f"Could not assemble research bundle: {exc}")
    st.caption("The ZIP includes experiment settings, provenance, raw snapshots, harmonized/analysis data, summary diagnostics, and the current chart when available. Secret keys are excluded.")
