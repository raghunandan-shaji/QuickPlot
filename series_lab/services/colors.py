from __future__ import annotations

import re
from hashlib import sha256
from typing import Mapping, MutableMapping


SERIES_PALETTE = (
    "#3F5F50",
    "#5B4E77",
    "#8A4F46",
    "#7A641F",
    "#2F6B68",
    "#7A4860",
    "#5D6F2D",
    "#3F6075",
    "#76543B",
    "#486A3F",
    "#69527E",
    "#8A5A2B",
)
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def default_series_color(series_key: str) -> str:
    index = int(sha256(series_key.encode()).hexdigest()[:8], 16) % len(SERIES_PALETTE)
    return SERIES_PALETTE[index]


def normalize_series_color(color: str) -> str:
    if not _HEX_COLOR.fullmatch(color):
        raise ValueError("Series colors must use six-digit hexadecimal notation.")
    return color.upper()


def series_color(series_key: str, overrides: Mapping[str, str] | None = None) -> str:
    override = (overrides or {}).get(series_key)
    if override is not None:
        try:
            return normalize_series_color(override)
        except ValueError:
            pass
    return default_series_color(series_key)


def set_series_color_override(state: MutableMapping, series_key: str, color: str) -> None:
    state.setdefault("series_color_overrides", {})[series_key] = normalize_series_color(color)


def reset_series_color_override(state: MutableMapping, series_key: str) -> None:
    state.setdefault("series_color_overrides", {}).pop(series_key, None)
