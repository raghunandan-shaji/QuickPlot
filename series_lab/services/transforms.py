from __future__ import annotations

import numpy as np
import pandas as pd

from series_lab.exceptions import TransformError


TRANSFORM_LABELS = {
    "level": "Level",
    "log_level": "Log level",
    "first_difference": "First difference",
    "log_difference": "Log difference",
    "percent_change": "Percent change",
    "z_score": "Z-score",
    "rebase_100": "Rebase to 100",
}


def transform_series(series: pd.Series, method: str) -> pd.Series:
    values = pd.to_numeric(series.copy(deep=True), errors="coerce").astype(float)
    valid = values.dropna()
    if method == "level":
        result = values
    elif method in {"log_level", "log_difference"}:
        if not valid.empty and (valid <= 0).any():
            raise TransformError(f"{series.name}: logarithms require strictly positive observations.")
        logged = np.log(values)
        result = logged if method == "log_level" else logged.diff()
    elif method == "first_difference":
        result = values.diff()
    elif method == "percent_change":
        result = values.pct_change(fill_method=None) * 100.0
    elif method == "z_score":
        std = valid.std(ddof=0)
        if valid.empty or not np.isfinite(std) or std == 0:
            raise TransformError(f"{series.name}: a constant or empty series cannot be z-scored.")
        result = (values - valid.mean()) / std
    elif method == "rebase_100":
        if valid.empty:
            raise TransformError(f"{series.name}: no valid reference observation is available.")
        first = valid.iloc[0]
        if first == 0:
            raise TransformError(f"{series.name}: the first valid observation is zero and cannot be rebased.")
        result = 100.0 * values / first
    else:
        raise TransformError(f"Unknown transform: {method}.")
    result.name = series.name
    return result


def build_analysis(harmonized: pd.DataFrame, methods: dict[str, str]) -> pd.DataFrame:
    output = pd.DataFrame(index=harmonized.index)
    for column in harmonized.columns:
        output[column] = transform_series(harmonized[column], methods.get(column, "level"))
    return output
