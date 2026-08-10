from __future__ import annotations

from collections import OrderedDict
from typing import MutableMapping

from .models import PrepareConfig, WorkspaceSeries


DEFAULTS = {
    "workspace": OrderedDict,
    "search_results": list,
    "search_failures": dict,
    "search_partial_results": list,
    "search_unknown_results": list,
    "search_coverage_message": lambda: None,
    "search_coverage_start": lambda: None,
    "search_coverage_end": lambda: None,
    "search_coverage_mode": lambda: "rank_by_coverage",
    "search_coverage_from_input": lambda: None,
    "search_coverage_to_input": lambda: None,
    "search_coverage_mode_input": lambda: "Rank by coverage",
    "search_show_partials": lambda: False,
    "search_show_unknown": lambda: False,
    "search_unavailable": dict,
    "search_resolution_active": dict,
    "search_query": lambda: "",
    "selected_providers": lambda: ["FRED", "Yahoo", "BLS", "EIA", "World Bank"],
    "target_series_key": lambda: None,
    "prepare_config": PrepareConfig,
    "prepared_data": lambda: None,
    "prepare_inline_error": lambda: None,
    "prepare_last_transform_change": lambda: None,
    "series_color_overrides": dict,
    "provider_statuses": dict,
}


def initialize_state(state: MutableMapping) -> None:
    for key, factory in DEFAULTS.items():
        if key not in state:
            state[key] = factory()


def add_to_workspace(state: MutableMapping, item: WorkspaceSeries) -> None:
    state["workspace"][item.series_key] = item
    state["prepared_data"] = None


def remove_from_workspace(state: MutableMapping, series_key: str) -> None:
    state["workspace"].pop(series_key, None)
    if state.get("target_series_key") == series_key:
        state["target_series_key"] = None
    state["prepared_data"] = None
