from __future__ import annotations

from series_lab.models import ResolvedSeriesCandidate


def fetch_resolved(providers: dict, candidate: ResolvedSeriesCandidate, start=None, end=None):
    for provider in providers.values():
        if provider.label.lower().replace(" ", "_") == candidate.provider:
            return provider.fetch(candidate, start=start, end=end)
    aliases = {"world_bank": "World Bank", "yahoo": "Yahoo", "fred": "FRED", "bls": "BLS", "eia": "EIA"}
    name = aliases.get(candidate.provider)
    if name and name in providers:
        return providers[name].fetch(candidate, start=start, end=end)
    raise KeyError(f"No provider registered for {candidate.provider}.")
