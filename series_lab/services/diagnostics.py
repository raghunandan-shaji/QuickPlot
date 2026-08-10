from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.stats import skew
from statsmodels.tsa.stattools import acf as sm_acf
from statsmodels.tsa.stattools import adfuller, kpss

from series_lab.models import PreparedData


LAG_CONVENTION = "Positive lag k = Y observed k periods before X."


def summary_statistics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in frame.columns:
        series = frame[name]
        valid = series.dropna()
        rows.append(
            {
                "series": name,
                "observations": int(valid.size),
                "first_date": valid.index.min().date().isoformat() if not valid.empty else None,
                "last_date": valid.index.max().date().isoformat() if not valid.empty else None,
                "missing": int(series.isna().sum()),
                "mean": valid.mean() if not valid.empty else np.nan,
                "median": valid.median() if not valid.empty else np.nan,
                "std_dev": valid.std(ddof=0) if not valid.empty else np.nan,
                "minimum": valid.min() if not valid.empty else np.nan,
                "maximum": valid.max() if not valid.empty else np.nan,
                "skewness": skew(valid, bias=False) if len(valid) >= 3 else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("series") if rows else pd.DataFrame()


def prepared_summary_statistics(prepared: PreparedData) -> pd.DataFrame:
    """Summarize aligned prepared values before analysis transforms."""
    return summary_statistics(prepared.harmonized)


def correlation_matrix(frame: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    if method not in {"pearson", "spearman"}:
        raise ValueError("Correlation method must be Pearson or Spearman.")
    return frame.corr(method=method, min_periods=2)


def stationarity_tests(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in frame.columns:
        values = frame[name].dropna().astype(float)
        row = {"series": name, "adf_statistic": np.nan, "adf_p_value": np.nan, "adf_interpretation": "Unavailable", "kpss_statistic": np.nan, "kpss_p_value": np.nan, "kpss_interpretation": "Unavailable", "note": ""}
        if len(values) < 8 or values.nunique() < 2:
            row["note"] = "Too short or constant for reliable stationarity tests."
            rows.append(row)
            continue
        try:
            adf_result = adfuller(values, regression="c", autolag="AIC")
            row.update({"adf_statistic": adf_result[0], "adf_p_value": adf_result[1], "adf_interpretation": "Evidence against a unit root" if adf_result[1] < 0.05 else "Insufficient evidence against a unit root"})
        except Exception as exc:
            row["note"] = f"ADF unavailable: {exc}"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                kpss_result = kpss(values, regression="c", nlags="auto")
            row.update({"kpss_statistic": kpss_result[0], "kpss_p_value": kpss_result[1], "kpss_interpretation": "Evidence against level stationarity" if kpss_result[1] < 0.05 else "Insufficient evidence against level stationarity"})
        except Exception as exc:
            row["note"] = (row["note"] + f" KPSS unavailable: {exc}").strip()
        rows.append(row)
    return pd.DataFrame(rows).set_index("series")


def autocorrelation_values(series: pd.Series, max_lag: int) -> pd.Series:
    values = series.dropna().astype(float)
    if values.nunique() < 2 or len(values) < 3:
        raise ValueError("ACF requires at least three nonconstant observations.")
    max_lag = min(max_lag, len(values) - 1)
    result = sm_acf(values, nlags=max_lag, fft=True, missing="drop")
    return pd.Series(result, index=range(len(result)), name=series.name)


def lag_correlations(target: pd.Series, predictor: pd.Series, max_lag: int, method: str = "pearson") -> pd.Series:
    if method not in {"pearson", "spearman"}:
        raise ValueError("Correlation method must be Pearson or Spearman.")
    aligned = pd.concat({"X": target, "Y": predictor}, axis=1)
    values = {lag: aligned["X"].corr(aligned["Y"].shift(lag), method=method) for lag in range(-max_lag, max_lag + 1)}
    result = pd.Series(values, name=predictor.name)
    result.index.name = "lag"
    return result


def rolling_pair_correlation(target: pd.Series, predictor: pd.Series, window: int, method: str = "pearson") -> pd.Series:
    aligned = pd.concat({"X": target, "Y": predictor}, axis=1)
    if method == "pearson":
        return aligned["X"].rolling(window, min_periods=window).corr(aligned["Y"])
    if method == "spearman":
        output = pd.Series(index=aligned.index, dtype=float, name=predictor.name)
        for end in range(window - 1, len(aligned)):
            sample = aligned.iloc[end - window + 1 : end + 1].dropna()
            if len(sample) >= 2:
                output.iloc[end] = sample["X"].corr(sample["Y"], method="spearman")
        return output
    raise ValueError("Correlation method must be Pearson or Spearman.")
