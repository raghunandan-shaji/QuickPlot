from __future__ import annotations

import html
from hashlib import sha256
from typing import Mapping

import streamlit as st

from series_lab.services.colors import (
    reset_series_color_override,
    series_color,
    set_series_color_override,
)


def visibility_widget_key(series_key: str) -> str:
    digest = sha256(series_key.encode()).hexdigest()[:12]
    return f"chart_visible_{digest}"


def swatch_html(
    series_key: str,
    muted: bool = False,
    color_overrides: Mapping[str, str] | None = None,
) -> str:
    opacity = ".42" if muted else "1"
    return (
        f'<span class="series-swatch" style="background:{series_color(series_key, color_overrides)};'
        f'opacity:{opacity}" aria-hidden="true"></span>'
    )


def identity_html(
    series_key: str,
    title: str,
    muted: bool = False,
    detail: str = "",
    color_overrides: Mapping[str, str] | None = None,
    include_swatch: bool = True,
) -> str:
    css_class = "series-identity is-muted" if muted else "series-identity"
    detail_html = f'<span class="series-detail">{html.escape(detail)}</span>' if detail else ""
    swatch = swatch_html(series_key, muted, color_overrides) if include_swatch else ""
    return (
        f'<div class="{css_class}">{swatch}'
        f'<span class="series-name">{html.escape(title)}</span>{detail_html}</div>'
    )


def _commit_color(series_key: str, picker_key: str) -> None:
    set_series_color_override(st.session_state, series_key, st.session_state[picker_key])


def _reset_color(series_key: str, picker_key: str) -> None:
    reset_series_color_override(st.session_state, series_key)
    st.session_state[picker_key] = series_color(series_key)


def render_color_editor(series_key: str, location: str, muted: bool = False) -> None:
    token = sha256(series_key.encode()).hexdigest()[:12]
    popover_key = f"series_color_{location}_{token}"
    picker_key = f"series_color_picker_{location}_{token}"
    overrides = st.session_state.series_color_overrides
    current = series_color(series_key, overrides)
    opacity = ".42" if muted else "1"
    st.markdown(
        f"""
        <style>
        .st-key-{popover_key} [data-testid="stPopover"] > button {{
          width:.86rem !important; min-width:.86rem !important; height:.86rem !important;
          min-height:.86rem !important; padding:0 !important; border-radius:2px !important;
          border:1px solid rgba(40,42,37,.2) !important; background:{current} !important;
          opacity:{opacity}; font-size:0 !important; box-shadow:none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    if picker_key in st.session_state and st.session_state[picker_key] != current:
        st.session_state[picker_key] = current
    with st.popover(
        "color",
        key=popover_key,
        help="Change series color",
        on_change="rerun",
    ):
        st.color_picker(
            "Series color",
            value=current,
            key=picker_key,
            on_change=_commit_color,
            args=(series_key, picker_key),
            width="stretch",
        )
        if series_key in overrides:
            st.button(
                "reset to default",
                key=f"series_color_reset_{location}_{token}",
                width="stretch",
                on_click=_reset_color,
                args=(series_key, picker_key),
            )
        else:
            st.caption("deterministic default")
