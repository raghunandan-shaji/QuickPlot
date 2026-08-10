from __future__ import annotations

import streamlit as st

from series_lab.state import remove_from_workspace
from series_lab.ui.series_controls import identity_html, render_color_editor, visibility_widget_key


def render_workspace() -> None:
    st.markdown("## workspace")
    workspace = st.session_state.workspace
    if not workspace:
        st.caption("No series yet. Search above and add a series to begin.")
        return
    options = {"None": None, **{item.fetched.title: key for key, item in workspace.items()}}
    current = next((label for label, key in options.items() if key == st.session_state.target_series_key), "None")
    selected = st.selectbox("Research target (optional)", list(options), index=list(options).index(current))
    st.session_state.target_series_key = options[selected]
    for index, (key, item) in enumerate(list(workspace.items())):
        c1, c2, c3, c4, c5, c6 = st.columns([0.11, 0.04, 0.41, 0.18, 0.17, 0.09], vertical_alignment="center")
        with c1:
            if st.button("hide" if item.visible else "show", key=f"visibility_{index}", help="Hide from or show on charts"):
                item.visible = not item.visible
                st.session_state[visibility_widget_key(key)] = item.visible
                st.rerun()
        with c2:
            render_color_editor(key, "workspace", muted=not item.visible)
        with c3:
            st.markdown(identity_html(key, item.fetched.title, muted=not item.visible, include_swatch=False), unsafe_allow_html=True)
        with c4:
            st.caption(item.fetched.provider)
        with c5:
            st.caption(item.fetched.metadata.get("frequency") or "frequency unknown")
        with c6:
            if st.button("×", key=f"remove_{index}", help=f"Remove {item.fetched.title}"):
                remove_from_workspace(st.session_state, key)
                st.rerun()
        st.markdown("<hr>", unsafe_allow_html=True)
