from __future__ import annotations

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root { --paper:#F5F5F1; --surface:#EEF1EA; --ink:#282A25; --muted:#74786F; --border:#D9DDD4; --sage:#A9BCA1; --lilac:#B6AAC3; --pale-lilac:#E8E2ED; --mauve:#C6AEB7; --clay:#D1B3A7; --straw:#CFC294; }
html, body, [class*="st-"] { font-family:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace; }
[data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded','Material Icons' !important; font-weight:normal !important; }
.stApp { background:var(--paper); color:var(--ink); }
.block-container { max-width:1160px; padding-top:4.5rem; padding-bottom:5rem; }
header[data-testid="stHeader"] { background:transparent; height:0; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"], #MainMenu, footer { display:none !important; }
h1, h2, h3 { font-family:'IBM Plex Mono',ui-monospace,monospace !important; color:var(--ink); letter-spacing:-0.035em; }
h1 { font-size:3.35rem !important; line-height:1.05 !important; margin:0 !important; }
h2 { font-size:1.85rem !important; margin-top:5.5rem !important; padding-bottom:.7rem; border-bottom:1px solid var(--border); }
h3 { font-size:1.05rem !important; letter-spacing:.02em; text-transform:uppercase; color:var(--muted); }
p, label, .stMarkdown, [data-testid="stWidgetLabel"] { font-size:1rem; }
.series-subtitle { color:var(--muted); font-size:1rem; margin-top:.45rem; margin-bottom:1rem; }
.section-note, .meta-line { color:var(--muted); font-size:.84rem; line-height:1.5; }
.results-label { margin:.9rem 0 .35rem; color:var(--muted); font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; }
.search-title { font-weight:600; font-size:1rem; margin-bottom:.2rem; }
.search-row { padding:.45rem 0 .1rem 0; }
.coverage-line { margin-top:.22rem; font-size:.76rem; line-height:1.4; }
.coverage-full { color:#657A60; }
.coverage-partial { color:#8A7485; }
.coverage-none, .coverage-unknown { color:var(--muted); }
.workspace-line { padding:.55rem 0; }
.series-identity { display:flex; align-items:center; gap:.65rem; min-height:2rem; color:var(--ink); }
.series-identity.is-muted { color:var(--muted); }
.series-swatch { display:inline-block; width:.72rem; height:.72rem; border-radius:2px; flex:0 0 .72rem; box-shadow:0 0 0 1px rgba(40,42,37,.12); }
.series-name { font-weight:500; line-height:1.3; }
.series-detail { color:var(--muted); font-size:.78rem; margin-left:auto; text-transform:lowercase; }
.analysis-summary { margin-top:1rem; padding:.9rem 1rem; border-left:3px solid var(--lilac); background:rgba(232,226,237,.42); }
.analysis-status { color:#596A54; font-size:.84rem; margin-bottom:.4rem; }
.analysis-range { font-size:1rem; color:var(--ink); margin-bottom:.3rem; }
.analysis-meta { color:var(--muted); font-size:.8rem; line-height:1.55; }
.prep-series-title { font-size:.9rem; line-height:1.35; color:var(--ink); }
.prep-separator { color:var(--muted); text-align:center; }
[class*="st-key-prep_row_"] { padding:.22rem 0; border-bottom:1px solid rgba(217,221,212,.65); }
[class*="st-key-prep_row_"] [data-testid="stPopover"] > button {
  background:transparent !important; border:0 !important; color:var(--muted) !important;
  min-height:1.7rem !important; padding:.12rem .2rem !important; box-shadow:none !important;
  font-size:.82rem !important; justify-content:flex-start !important;
}
[class*="st-key-prep_row_"] [data-testid="stPopover"] > button:hover { color:var(--ink) !important; background:var(--pale-lilac) !important; }
[class*="st-key-prep_row_"] .stButton > button { min-height:1.8rem; padding:.18rem .45rem; font-size:.76rem; }
hr { border:none; border-top:1px solid var(--border); margin:.6rem 0; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
  border:1px solid var(--border); background:var(--surface); color:var(--ink); border-radius:2px; box-shadow:none; min-height:2.55rem;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover { border-color:var(--lilac); color:var(--ink); background:var(--pale-lilac); }
button[aria-pressed="true"] { background:var(--pale-lilac) !important; border-color:var(--lilac) !important; color:var(--ink) !important; }
button:focus-visible, input:focus-visible { outline:2px solid var(--lilac) !important; outline-offset:1px; }
input, [data-baseweb="select"] > div, [data-baseweb="input"] > div { background:#FAFBF7 !important; border-color:var(--border) !important; }
[data-testid="stAlert"] { background:var(--surface); border:1px solid var(--border); color:var(--ink); border-radius:2px; }
[data-testid="stDataFrame"] { border:1px solid var(--border); }
div[data-testid="stExpander"] { border:1px solid var(--border); border-radius:2px; background:transparent; }
.st-key-search_results_region, .st-key-series_shown_region { border-color:var(--border) !important; background:rgba(238,241,234,.34); }
@media (max-width: 760px) {
  .block-container { padding:2.5rem 1.1rem 3rem; }
  h1 { font-size:2.55rem !important; }
  h2 { margin-top:3.8rem !important; font-size:1.55rem !important; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header() -> None:
    st.markdown("# QuickPlot")
    st.markdown('<div class="series-subtitle">multivariate time-series research workspace</div>', unsafe_allow_html=True)
