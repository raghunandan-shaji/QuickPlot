from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from series_lab.services.colors import SERIES_PALETTE as PALETTE
from series_lab.services.colors import series_color



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
    color_overrides: dict[str, str] | None = None,
) -> go.Figure:
    titles = titles or {}
    fig = go.Figure()
    for column in frame.columns:
        color = series_color(column, color_overrides)
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                name=titles.get(column, column),
                mode="lines+markers" if markers else "lines",
                line=dict(color=color, width=2.05),
                marker=dict(color=color, size=4),
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
    color_overrides: dict[str, str] | None = None,
) -> go.Figure:
    titles = titles or {}
    fig = make_subplots(
        rows=max(1, len(frame.columns)), cols=1, shared_xaxes=True,
        subplot_titles=[titles.get(c, c) for c in frame.columns], vertical_spacing=0.05,
    )
    for row, column in enumerate(frame.columns, start=1):
        color = series_color(column, color_overrides)
        fig.add_trace(
            go.Scatter(
                x=frame.index, y=frame[column], name=titles.get(column, column),
                mode="lines+markers" if markers else "lines",
                line=dict(color=color, width=1.9), marker=dict(color=color, size=3), showlegend=False,
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
