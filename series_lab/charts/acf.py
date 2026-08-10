from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .timeseries import series_color


def acf_chart(values: pd.Series, color_overrides: dict[str, str] | None = None) -> go.Figure:
    color = series_color(str(values.name), color_overrides)
    fig = go.Figure()
    for lag, value in values.items():
        fig.add_shape(type="line", x0=lag, x1=lag, y0=0, y1=value, line=dict(color=color, width=1.5))
    fig.add_trace(go.Scatter(x=values.index, y=values.values, mode="markers", marker=dict(color=color, size=7), hovertemplate="lag %{x}<br>%{y:.3f}<extra></extra>"))
    fig.add_hline(y=0, line_color="#C5CBC1", line_width=1)
    fig.update_layout(
        height=480, margin=dict(l=55, r=24, t=35, b=55), showlegend=False,
        paper_bgcolor="#F5F5F1", plot_bgcolor="#F5F5F1",
        font=dict(family="IBM Plex Mono, monospace", color="#4B5149"),
        xaxis_title="lag", yaxis_title="autocorrelation",
        xaxis=dict(gridcolor="#E1E4DC"), yaxis=dict(gridcolor="#E1E4DC", range=[-1.05, 1.05]),
    )
    return fig
