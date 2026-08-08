from __future__ import annotations

import pandas as pd

from series_lab.config import REQUEST_TIMEOUT
from series_lab.exceptions import SeriesFetchError, SeriesResolutionError
from series_lab.models import FetchedSeries, ResolvedSeriesCandidate, SeriesCandidate
from series_lab.services.search import rank_catalog

from .base import DataProvider
from .catalog_cache import cached_world_bank_records


class WorldBankProvider(DataProvider):
    label = "World Bank"
    base_url = "https://api.worldbank.org/v2"

    def __init__(self) -> None:
        super().__init__()
        self._indicators: pd.DataFrame | None = None
        self._countries: list[dict] | None = None

    def is_available(self) -> bool:
        return True

    def _all_pages(self, resource: str) -> list[dict]:
        return cached_world_bank_records(self.base_url, resource)

    def load_indicators(self) -> pd.DataFrame:
        if self._indicators is None:
            records = self._all_pages("indicator")
            self._indicators = pd.DataFrame(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("sourceNote", ""),
                    "source": (item.get("source") or {}).get("value"),
                }
                for item in records
            )
        return self._indicators

    def countries(self) -> list[dict]:
        if self._countries is None:
            records = self._all_pages("country")
            self._countries = sorted(
                [
                    {"id": item.get("id"), "name": item.get("name")}
                    for item in records
                    if item.get("id") and item.get("name")
                ],
                key=lambda x: x["name"],
            )
        return self._countries

    def search(self, query: str, limit: int = 10) -> list[SeriesCandidate]:
        ranked = rank_catalog(
            self.load_indicators(), query, "id", "name", limit, extra_columns=("description",)
        )
        return [
            SeriesCandidate(
                provider="world_bank",
                candidate_id=row["id"],
                title=row["name"],
                description=row.get("description", ""),
                frequency="Annual",
                requires_resolution=True,
                metadata={"source": row.get("source"), "description": row.get("description", "")},
            )
            for row in ranked.to_dict("records")
        ]

    @staticmethod
    def parse_observations(payload: list, series_key: str) -> tuple[pd.DataFrame, pd.Series, dict]:
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            raise SeriesFetchError("World Bank returned no observations.")
        raw = pd.DataFrame(payload[1])
        dates = pd.to_datetime(raw["date"].astype(str) + "-12-31", errors="coerce")
        values = pd.Series(pd.to_numeric(raw["value"], errors="coerce").to_numpy(), index=dates)
        values = values[~values.index.isna()].sort_index()
        values.name = series_key
        return raw, values, payload[0] or {}

    def fetch(self, candidate: ResolvedSeriesCandidate, start=None, end=None) -> FetchedSeries:
        geography = candidate.resolution_parameters.get("geography")
        if not geography:
            raise SeriesResolutionError("Choose a geography before fetching a World Bank indicator.")
        params = {"format": "json", "per_page": 20000}
        if start or end:
            params["date"] = f"{pd.Timestamp(start or '1900').year}:{pd.Timestamp(end or 'today').year}"
        try:
            response = self.session.get(
                f"{self.base_url}/country/{geography}/indicator/{candidate.provider_series_id}",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            raw, values, header = self.parse_observations(payload, candidate.series_key)
        except (SeriesFetchError, SeriesResolutionError):
            raise
        except Exception as exc:
            raise SeriesFetchError(f"World Bank could not fetch {candidate.title}.") from exc
        country_name = raw.iloc[0].get("country", {}).get("value") if not raw.empty else geography
        return FetchedSeries(
            candidate.series_key,
            "World Bank",
            candidate.title,
            raw,
            values,
            {
                **candidate.metadata,
                "provider_id": candidate.provider_series_id,
                "geography": geography,
                "geography_name": country_name,
                "frequency": "Annual",
                "selected_value_field": "value",
            },
            {"source": "World Bank Indicators API V2", "indicator": candidate.provider_series_id},
            raw_payload=payload,
        )
