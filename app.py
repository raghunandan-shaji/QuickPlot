from __future__ import annotations

import logging

import streamlit as st

from series_lab.providers import build_provider_registry
from series_lab.state import initialize_state
from series_lab.ui.diagnostics_section import render_diagnostics
from series_lab.ui.export_section import render_export
from series_lab.ui.prepare_section import render_prepare
from series_lab.ui.search_section import render_search
from series_lab.ui.theme import apply_theme, page_header
from series_lab.ui.visualize_section import render_visualize
from series_lab.ui.workspace_section import render_workspace


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
st.set_page_config(page_title="QuickPlot", page_icon="⌁", layout="wide", initial_sidebar_state="collapsed")
apply_theme()
initialize_state(st.session_state)


@st.cache_resource
def providers():
    return build_provider_registry()


page_header()
render_search(providers())
render_workspace()
render_prepare()
render_visualize()
render_diagnostics()
render_export()
