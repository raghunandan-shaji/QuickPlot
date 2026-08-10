from __future__ import annotations

from copy import deepcopy
import json
from time import monotonic

from series_lab.exceptions import SeriesFetchError
from series_lab.models import ResolvedSeriesCandidate


FETCH_CACHE_TTL_SECONDS = 15 * 60


def _fetch_cache_key(candidate: ResolvedSeriesCandidate, start, end) -> tuple:
    resolution = json.dumps(candidate.resolution_parameters, sort_keys=True, default=str)
    return (
        candidate.provider,
        candidate.provider_series_id,
        resolution,
        candidate.value_field,
        str(start or ""),
        str(end or ""),
    )


def fetch_resolved(providers: dict, candidate: ResolvedSeriesCandidate, start=None, end=None):
    for provider in providers.values():
        if provider.label.lower().replace(" ", "_") == candidate.provider:
            selected_provider = provider
            break
    else:
        aliases = {"world_bank": "World Bank", "yahoo": "Yahoo", "fred": "FRED", "bls": "BLS", "eia": "EIA"}
        name = aliases.get(candidate.provider)
        if not name or name not in providers:
            raise KeyError(f"No provider registered for {candidate.provider}.")
        selected_provider = providers[name]

    key = _fetch_cache_key(candidate, start, end)
    now = monotonic()
    cache = getattr(selected_provider, "_quickplot_fetch_cache", None)
    if cache is None:
        cache = {}
        try:
            setattr(selected_provider, "_quickplot_fetch_cache", cache)
        except Exception:
            cache = None
    if cache is not None:
        cached = cache.get(key)
        if cached and now - cached[0] < FETCH_CACHE_TTL_SECONDS:
            return deepcopy(cached[1])

    fetched = selected_provider.fetch(candidate, start=start, end=end)
    if fetched.value_series.dropna().empty:
        raise SeriesFetchError(f"{candidate.title} returned no usable observations for this selection.")
    if cache is not None:
        cache[key] = (now, deepcopy(fetched))
    return fetched
