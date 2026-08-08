from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SeriesCandidate:
    provider: str
    candidate_id: str
    title: str
    description: str = ""
    frequency: str | None = None
    units: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    instrument_type: str | None = None
    exchange: str | None = None
    requires_resolution: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    available_start: str | None = None
    available_end: str | None = None
    coverage_ratio: float | None = None
    coverage_status: str = "unknown"
    coverage_missing_ranges: tuple[str, ...] = ()
    coverage_source: str | None = None


@dataclass(frozen=True)
class ResolvedSeriesCandidate:
    provider: str
    series_key: str
    provider_series_id: str
    title: str
    resolution_parameters: dict[str, Any] = field(default_factory=dict)
    value_field: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchedSeries:
    series_key: str
    provider: str
    title: str
    raw_frame: pd.DataFrame
    value_series: pd.Series
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    fetched_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    raw_payload: Any = None

    def __post_init__(self) -> None:
        self.raw_frame = self.raw_frame.copy(deep=True)
        self.value_series = self.value_series.copy(deep=True)
        if not isinstance(self.value_series.index, pd.DatetimeIndex):
            self.value_series.index = pd.to_datetime(self.value_series.index)
        self.value_series = self.value_series.sort_index()

    def raw_copy(self) -> pd.DataFrame:
        return self.raw_frame.copy(deep=True)


@dataclass
class WorkspaceSeries:
    fetched: FetchedSeries
    visible: bool = True
    transform: str = "level"
    aggregation: str | None = None

    @property
    def series_key(self) -> str:
        return self.fetched.series_key


@dataclass
class PrepareConfig:
    frequency: str | None = None
    date_coverage: str = "common_overlap"
    missing_strategy: str = "leave_missing"
    default_aggregation: str = "last"
    upsampling_acknowledged: bool = False


@dataclass
class PreparedData:
    harmonized: pd.DataFrame
    analysis: pd.DataFrame
    effective_start: str | None
    effective_end: str | None
    warnings: list[str] = field(default_factory=list)


def resolve_candidate(
    candidate: SeriesCandidate,
    resolution_parameters: dict[str, Any] | None = None,
    value_field: str | None = None,
) -> ResolvedSeriesCandidate:
    params = resolution_parameters or {}
    provider = candidate.provider.lower()
    if candidate.requires_resolution and not params:
        from .exceptions import SeriesResolutionError

        raise SeriesResolutionError(f"{candidate.title} requires additional selections.")
    if provider == "world_bank":
        geography = params.get("geography")
        if not geography:
            from .exceptions import SeriesResolutionError

            raise SeriesResolutionError("Choose a geography before adding this indicator.")
        key = f"world_bank:{geography}:{candidate.candidate_id}"
    elif provider == "eia":
        facets = params.get("facets", {})
        facet_key = ":".join(f"{k}={facets[k]}" for k in sorted(facets))
        key = f"eia:{candidate.candidate_id}:{facet_key or 'unresolved'}"
    else:
        key = f"{provider}:{candidate.candidate_id}"
    return ResolvedSeriesCandidate(
        provider=provider,
        series_key=key,
        provider_series_id=candidate.candidate_id,
        title=candidate.title,
        resolution_parameters=params,
        value_field=value_field,
        metadata=dict(candidate.metadata),
    )
