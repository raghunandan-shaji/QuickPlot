from __future__ import annotations

from collections.abc import Callable, MutableMapping

from series_lab.models import PrepareConfig, PreparedData, WorkspaceSeries
from series_lab.services.harmonize import AGGREGATIONS, harmonize
from series_lab.services.transforms import TRANSFORM_LABELS


Harmonizer = Callable[[list[WorkspaceSeries], PrepareConfig], PreparedData]


def apply_transform_setting(
    workspace: MutableMapping[str, WorkspaceSeries],
    series_key: str,
    method: str,
    config: PrepareConfig,
    *,
    apply_to_all: bool = False,
    harmonizer: Harmonizer = harmonize,
) -> PreparedData:
    if series_key not in workspace:
        raise KeyError(f"Unknown workspace series: {series_key}.")
    if method not in TRANSFORM_LABELS:
        raise ValueError(f"Unknown transform: {method}.")
    targets = workspace.values() if apply_to_all else (workspace[series_key],)
    for item in targets:
        item.transform = method
    # One transaction, one harmonization pass, and no provider fetch.
    return harmonizer(list(workspace.values()), config)


def apply_aggregation_setting(
    workspace: MutableMapping[str, WorkspaceSeries],
    series_key: str,
    aggregation: str | None,
    config: PrepareConfig,
    *,
    harmonizer: Harmonizer = harmonize,
) -> PreparedData:
    if series_key not in workspace:
        raise KeyError(f"Unknown workspace series: {series_key}.")
    if aggregation is not None and aggregation not in AGGREGATIONS:
        raise ValueError(f"Unknown aggregation: {aggregation}.")
    workspace[series_key].aggregation = aggregation
    return harmonizer(list(workspace.values()), config)
