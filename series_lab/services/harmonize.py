from __future__ import annotations

import re

import pandas as pd

from series_lab.exceptions import FrequencyResolutionError
from series_lab.models import PrepareConfig, PreparedData, WorkspaceSeries
from series_lab.services.transforms import build_analysis


FREQUENCIES = {
    "daily": "D",
    "business_daily": "B",
    "weekly": "W-FRI",
    "monthly": "ME",
    "quarterly": "QE",
    "annual": "YE",
}
FREQUENCY_RANK = {"daily": 0, "business_daily": 1, "weekly": 2, "monthly": 3, "quarterly": 4, "annual": 5}
AGGREGATIONS = {"last": "last", "first": "first", "mean": "mean", "sum": "sum", "median": "median"}


def normalize_frequency(value: str | None, index: pd.DatetimeIndex | None = None) -> str | None:
    text = (value or "").strip().lower().replace("-", " ").replace("_", " ")
    if text:
        if text in {"b", "bd", "business day"}:
            return "business_daily"
        if "business" in text:
            return "business_daily"
        if "daily" in text or text in {"d", "day"}:
            return "daily"
        if "week" in text or text.startswith("w"):
            return "weekly"
        if "month" in text or text.startswith("m"):
            return "monthly"
        if "quarter" in text or text.startswith("q"):
            return "quarterly"
        if "annual" in text or "year" in text or text in {"a", "y"} or text.startswith(("a", "y")):
            return "annual"
    if index is not None and len(index) >= 3:
        inferred = pd.infer_freq(index.sort_values().unique())
        if inferred:
            return normalize_frequency(inferred)
        median_days = pd.Series(index.sort_values()).diff().median().days
        if median_days <= 2:
            return "daily"
        if median_days <= 9:
            return "weekly"
        if median_days <= 45:
            return "monthly"
        if median_days <= 120:
            return "quarterly"
        return "annual"
    return None


def _resample(series: pd.Series, frequency: str, aggregation: str) -> pd.Series:
    rule = FREQUENCIES[frequency]
    resampler = series.sort_index().resample(rule)
    return getattr(resampler, AGGREGATIONS[aggregation])()


def harmonize(workspace: list[WorkspaceSeries], config: PrepareConfig) -> PreparedData:
    if not workspace:
        raise FrequencyResolutionError("Add at least one series before preparing data.")
    source_freqs = {
        item.series_key: normalize_frequency(item.fetched.metadata.get("frequency"), item.fetched.value_series.index)
        for item in workspace
    }
    known = {freq for freq in source_freqs.values() if freq}
    target = config.frequency
    if target is None:
        if len(known) > 1:
            details = ", ".join(f"{key}: {freq}" for key, freq in source_freqs.items())
            raise FrequencyResolutionError(
                f"Source frequencies differ ({details}). Choose a common analysis frequency explicitly."
            )
        target = next(iter(known), None)
    if target not in FREQUENCIES:
        raise FrequencyResolutionError("Choose a supported analysis frequency.")
    upsampled = [
        key for key, freq in source_freqs.items()
        if freq and FREQUENCY_RANK[target] < FREQUENCY_RANK[freq]
    ]
    if upsampled and not config.upsampling_acknowledged:
        raise FrequencyResolutionError(
            "Upsampling creates dates for which the original series had no observation. "
            "Acknowledge this before building the dataset: " + ", ".join(upsampled)
        )
    prepared: dict[str, pd.Series] = {}
    starts, ends = [], []
    for item in workspace:
        source = item.fetched.value_series.copy(deep=True).sort_index()
        source = source[~source.index.duplicated(keep="last")]
        if not source.empty:
            starts.append(source.index.min())
            ends.append(source.index.max())
        source_frequency = source_freqs[item.series_key]
        aggregation = item.aggregation or config.default_aggregation
        # Providers do not consistently timestamp lower-frequency observations:
        # the same quarter may arrive as quarter-start or quarter-end. Always
        # pass anchored frequencies through the canonical target bins so valid
        # series align instead of alternating with NaN rows in line charts.
        canonicalize_target_dates = target in {"weekly", "monthly", "quarterly", "annual"}
        if source_frequency != target or canonicalize_target_dates:
            source = _resample(source, target, aggregation)
        prepared[item.series_key] = source
    frame = pd.concat(prepared, axis=1).sort_index()
    if config.date_coverage == "common_overlap" and starts and ends:
        overlap_start, overlap_end = max(starts), min(ends)
        if overlap_start > overlap_end:
            raise FrequencyResolutionError("The selected series have no common date overlap.")
        frame = frame.loc[overlap_start:overlap_end]
    elif config.date_coverage != "full_union":
        raise FrequencyResolutionError("Unknown date coverage policy.")
    warnings: list[str] = []
    if config.missing_strategy == "forward_fill":
        frame = frame.ffill()
        warnings.append("Forward fill repeats earlier observations on dates with no original value.")
    elif config.missing_strategy == "time_interpolation":
        frame = frame.interpolate(method="time")
        warnings.append("Interpolation creates synthetic values and may use future observations.")
    elif config.missing_strategy == "drop_incomplete":
        frame = frame.dropna(how="any")
    elif config.missing_strategy != "leave_missing":
        raise FrequencyResolutionError("Unknown missing-value strategy.")
    methods = {item.series_key: item.transform for item in workspace}
    analysis = build_analysis(frame, methods)
    start = frame.index.min().date().isoformat() if not frame.empty else None
    end = frame.index.max().date().isoformat() if not frame.empty else None
    return PreparedData(frame, analysis, start, end, warnings)
