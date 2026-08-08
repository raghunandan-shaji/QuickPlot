from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from series_lab.models import PreparedData, WorkspaceSeries


DATE_RANGE_OPTIONS = ("Full", "1Y", "3Y", "5Y", "10Y", "Custom")
DATA_LAYERS = ("Prepared analysis", "Harmonized", "Raw")


def frame_bounds(frame: pd.DataFrame | pd.Series) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if isinstance(frame, pd.Series):
        valid = frame.dropna()
    else:
        valid = frame.dropna(how="all")
    if valid.empty:
        return None, None
    return pd.Timestamp(valid.index.min()), pd.Timestamp(valid.index.max())


def trim_empty_edges(frame: pd.DataFrame) -> pd.DataFrame:
    start, end = frame_bounds(frame)
    if start is None or end is None:
        return frame.iloc[0:0].copy()
    return frame.loc[start:end].copy()


def visible_series_keys(workspace: Mapping[str, WorkspaceSeries]) -> list[str]:
    return [key for key, item in workspace.items() if item.visible]


def build_layer_frame(
    workspace: Mapping[str, WorkspaceSeries],
    prepared: PreparedData,
    selected_keys: Sequence[str],
    layer: str,
) -> pd.DataFrame:
    keys = [key for key in selected_keys if key in workspace]
    if not keys:
        return pd.DataFrame()
    if layer == "Prepared analysis":
        frame = prepared.analysis.loc[:, keys].copy()
    elif layer == "Harmonized":
        frame = prepared.harmonized.loc[:, keys].copy()
    elif layer == "Raw":
        # Raw uses the union of provider-native observation dates. It is never
        # clipped to the prepared common-overlap sample.
        frame = pd.concat(
            {key: workspace[key].fetched.value_series.copy(deep=True) for key in keys},
            axis=1,
        ).sort_index()
    else:
        raise ValueError(f"Unknown visualization layer: {layer}.")
    return trim_empty_edges(frame)


def filter_date_window(
    frame: pd.DataFrame,
    option: str | None,
    custom_start=None,
    custom_end=None,
) -> pd.DataFrame:
    frame = trim_empty_edges(frame)
    # Streamlit single-select segmented controls can briefly yield None while
    # changing selection during a rerun. Treat that transient state as Full.
    option = option or "Full"
    if frame.empty or option in {"Full", "Full sample"}:
        return frame
    aliases = {"1 year": 1, "3 years": 3, "5 years": 5, "10 years": 10}
    if option == "Custom":
        if custom_start is None or custom_end is None:
            raise ValueError("Custom date range requires both a start and end date.")
        start, end = pd.Timestamp(custom_start), pd.Timestamp(custom_end)
        if start > end:
            raise ValueError("Custom start date must not be after the end date.")
        return trim_empty_edges(frame.loc[start:end])
    years = aliases.get(option)
    if years is None and option.endswith("Y"):
        years = int(option[:-1])
    if years is None:
        raise ValueError(f"Unknown date range: {option}.")
    _, end = frame_bounds(frame)
    return trim_empty_edges(frame.loc[end - pd.DateOffset(years=years) : end])


def layer_bounds_by_series(
    workspace: Mapping[str, WorkspaceSeries],
    prepared: PreparedData,
    selected_keys: Sequence[str],
) -> dict[str, dict[str, tuple[pd.Timestamp | None, pd.Timestamp | None]]]:
    output = {}
    for key in selected_keys:
        if key not in workspace:
            continue
        output[key] = {
            "Raw": frame_bounds(workspace[key].fetched.value_series),
            "Harmonized": frame_bounds(prepared.harmonized[key]),
            "Prepared analysis": frame_bounds(prepared.analysis[key]),
        }
    return output
