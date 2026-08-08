from __future__ import annotations

import html
from hashlib import sha256

from series_lab.charts.timeseries import series_color


def visibility_widget_key(series_key: str) -> str:
    digest = sha256(series_key.encode()).hexdigest()[:12]
    return f"chart_visible_{digest}"


def swatch_html(series_key: str, muted: bool = False) -> str:
    opacity = ".42" if muted else "1"
    return (
        f'<span class="series-swatch" style="background:{series_color(series_key)};'
        f'opacity:{opacity}" aria-hidden="true"></span>'
    )


def identity_html(series_key: str, title: str, muted: bool = False, detail: str = "") -> str:
    css_class = "series-identity is-muted" if muted else "series-identity"
    detail_html = f'<span class="series-detail">{html.escape(detail)}</span>' if detail else ""
    return (
        f'<div class="{css_class}">{swatch_html(series_key, muted)}'
        f'<span class="series-name">{html.escape(title)}</span>{detail_html}</div>'
    )
