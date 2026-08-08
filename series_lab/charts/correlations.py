from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def _short_label(name: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(name)).strip()
    lower = text.lower()
    suffix = None
    if "producer price index" in lower:
        suffix = "PPI"
    elif "consumer price index" in lower:
        suffix = "CPI"

    if "brent" in lower and "crude" in lower:
        label = "Brent Crude"
    else:
        text = re.sub(r"(?i)^global price of\s+", "", text)
        segments = [part.strip() for part in re.split(r"\s*[:–—]\s*", text) if part.strip()]
        candidate = segments[-1] if len(segments) > 1 else text
        words = [
            word for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9.'&/-]*", candidate)
            if word.lower() not in {"and", "the", "of", "for", "by", "in"}
        ]
        if suffix:
            label = " ".join(words[:2] + [suffix])
        else:
            label = " ".join(words[:4]) or candidate

    if len(label) > max_chars:
        label = label[: max_chars - 1].rstrip(" -/:") + "…"
    return label or "Series"


def _display_labels(keys: list, titles: dict, max_chars: int) -> dict:
    labels: dict = {}
    counts: dict[str, int] = {}
    for key in keys:
        base = _short_label(titles.get(key, key), max_chars)
        counts[base] = counts.get(base, 0) + 1
        suffix = f"·{counts[base]}" if counts[base] > 1 else ""
        labels[key] = base[: max_chars - len(suffix)].rstrip() + suffix
    return labels


def correlation_heatmap(matrix: pd.DataFrame, titles: dict[str, str] | None = None) -> go.Figure:
    titles = titles or {}
    size = max(len(matrix.index), len(matrix.columns))
    max_chars = 22 if size <= 6 else 17 if size <= 10 else 13
    label_font_size = 12 if size <= 6 else 11 if size <= 10 else 9
    keys = list(dict.fromkeys([*matrix.columns, *matrix.index]))
    display = _display_labels(keys, titles, max_chars)
    x_labels = [display[key] for key in matrix.columns]
    y_labels = [display[key] for key in matrix.index]
    full_x = [titles.get(key, key) for key in matrix.columns]
    full_y = [titles.get(key, key) for key in matrix.index]
    customdata = np.empty((len(matrix.index), len(matrix.columns), 2), dtype=object)
    for row, row_name in enumerate(full_y):
        for column, column_name in enumerate(full_x):
            customdata[row, column] = [row_name, column_name]

    fig = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(), x=x_labels, y=y_labels, zmin=-1, zmax=1, zmid=0,
            colorscale=[[0, "#8F7D9F"], [0.5, "#F5F5F1"], [1, "#7F997A"]],
            texttemplate="%{z:.2f}", customdata=customdata,
            colorbar=dict(title="correlation", thickness=12, x=1.03, xanchor="left", len=0.84),
            hovertemplate="%{customdata[0]} × %{customdata[1]}<br>correlation: %{z:.3f}<extra></extra>",
            hoverongaps=False, xgap=1, ygap=1,
        )
    )
    fig.update_layout(
        autosize=True,
        height=max(360, min(720, 70 + 46 * size)),
        margin=dict(l=118, r=112, t=18, b=72 if size <= 6 else 92),
        paper_bgcolor="#F5F5F1", plot_bgcolor="#F5F5F1",
        font=dict(family="IBM Plex Mono, monospace", color="#4B5149"),
        xaxis=dict(
            tickangle=0 if size <= 6 else -30,
            tickfont=dict(size=label_font_size),
            automargin=False,
            constrain="domain",
        ),
        yaxis=dict(
            tickfont=dict(size=label_font_size),
            automargin=False,
            constrain="domain",
            scaleanchor="x",
            scaleratio=1,
        ),
    )
    return fig
