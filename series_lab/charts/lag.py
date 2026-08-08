from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .timeseries import series_color


def lag_chart(values: dict[str, pd.Series], titles: dict[str, str] | None = None) -> go.Figure:
    titles = titles or {}
    fig = go.Figure()
    for key, series in values.items():
        fig.add_trace(go.Scatter(x=series.index, y=series.values, name=titles.get(key, key), mode="lines+markers", line=dict(color=series_color(key), width=1.8), marker=dict(size=5)))
    fig.add_hline(y=0, line_color="#C5CBC1", line_width=1)
    fig.update_layout(
        height=520, margin=dict(l=55, r=24, t=35, b=60),
        paper_bgcolor="#F5F5F1", plot_bgcolor="#F5F5F1",
        font=dict(family="IBM Plex Mono, monospace", color="#4B5149"),
        xaxis_title="lag k", yaxis_title="correlation", hovermode="x unified",
        xaxis=dict(gridcolor="#E1E4DC"), yaxis=dict(gridcolor="#E1E4DC", range=[-1.05, 1.05]),
    )
    return fig
