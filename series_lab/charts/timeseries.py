from __future__ import annotations

from hashlib import sha256

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PALETTE = [
    "#8FA58A", "#A394B2", "#C39385", "#B6A15F", "#799E94", "#A98996",
    "#8E9E6C", "#879BA4", "#B29A7E", "#789487", "#A596B8", "#B6A171",
]


def series_color(series_key: str) -> str:
    return PALETTE[int(sha256(series_key.encode()).hexdigest()[:8], 16) % len(PALETTE)]


def _x_range(frame: pd.DataFrame):
    valid = frame.dropna(how="all")
    if valid.empty:
        return None
    start, end = pd.Timestamp(valid.index.min()), pd.Timestamp(valid.index.max())
    if start == end:
        padding = pd.Timedelta(days=1)
        return [start - padding, end + padding]
    return [start, end]


def _base_layout(height: int, legend: bool, grid: bool, rangeslider: bool, y_log: bool):
    return dict(
        height=height,
        margin=dict(l=55, r=24, t=32, b=48),
        paper_bgcolor="#F5F5F1",
        plot_bgcolor="#F5F5F1",
        font=dict(family="IBM Plex Mono, ui-monospace, monospace", color="#4B5149", size=13),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#282A25", font_color="#F5F5F1"),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor="#E1E4DC" if grid else "rgba(0,0,0,0)", linecolor="#C5CBC1", rangeslider=dict(visible=rangeslider)),
        yaxis=dict(gridcolor="#E1E4DC" if grid else "rgba(0,0,0,0)", linecolor="#C5CBC1", type="log" if y_log else "linear"),
    )


def overlay_chart(
    frame: pd.DataFrame,
    titles: dict[str, str] | None = None,
    legend: bool = True,
    grid: bool = True,
    rangeslider: bool = False,
    markers: bool = False,
    y_log: bool = False,
) -> go.Figure:
    titles = titles or {}
    fig = go.Figure()
    for column in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                name=titles.get(column, column),
                mode="lines+markers" if markers else "lines",
                line=dict(color=series_color(column), width=2.05),
                marker=dict(size=4),
                connectgaps=False,
            )
        )
    fig.update_layout(**_base_layout(650, legend, grid, rangeslider, y_log))
    bounds = _x_range(frame)
    if bounds:
        fig.update_xaxes(range=bounds, autorange=False)
    return fig


def small_multiples(
    frame: pd.DataFrame,
    titles: dict[str, str] | None = None,
    grid: bool = True,
    markers: bool = False,
    y_log: bool = False,
) -> go.Figure:
    titles = titles or {}
    fig = make_subplots(
        rows=max(1, len(frame.columns)), cols=1, shared_xaxes=True,
        subplot_titles=[titles.get(c, c) for c in frame.columns], vertical_spacing=0.05,
    )
    for row, column in enumerate(frame.columns, start=1):
        fig.add_trace(
            go.Scatter(
                x=frame.index, y=frame[column], name=titles.get(column, column),
                mode="lines+markers" if markers else "lines",
                line=dict(color=series_color(column), width=1.9), marker=dict(size=3), showlegend=False,
            ), row=row, col=1,
        )
    fig.update_layout(
        height=max(350, 270 * len(frame.columns)), margin=dict(l=55, r=24, t=40, b=45),
        paper_bgcolor="#F5F5F1", plot_bgcolor="#F5F5F1",
        font=dict(family="IBM Plex Mono, ui-monospace, monospace", color="#4B5149", size=12),
        hovermode="x unified",
    )
    bounds = _x_range(frame)
    fig.update_xaxes(gridcolor="#E1E4DC" if grid else "rgba(0,0,0,0)", linecolor="#C5CBC1", range=bounds, autorange=bounds is None)
    fig.update_yaxes(gridcolor="#E1E4DC" if grid else "rgba(0,0,0,0)", linecolor="#C5CBC1", type="log" if y_log else "linear")
    return fig
