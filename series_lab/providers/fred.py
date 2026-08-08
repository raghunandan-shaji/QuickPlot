from __future__ import annotations

import pandas as pd

from series_lab.config import REQUEST_TIMEOUT
from series_lab.exceptions import ProviderAuthenticationError, ProviderUnavailableError, SeriesFetchError
from series_lab.models import FetchedSeries, ResolvedSeriesCandidate, SeriesCandidate

from .base import DataProvider


class FredProvider(DataProvider):
    label = "FRED"
    base_url = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self.api_key = api_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    def availability_message(self) -> str | None:
        if not self.api_key:
            return "Configure FRED_API_KEY to search and fetch FRED series."
        return None

    def _get(self, path: str, **params):
        if not self.api_key:
            raise ProviderUnavailableError(self.availability_message())
        try:
            params.update({"api_key": self.api_key, "file_type": "json"})
            response = self.session.get(
                f"{self.base_url}/{path}", params=params, timeout=REQUEST_TIMEOUT
            )
            if response.status_code in (401, 403, 400) and "api_key" in response.text.lower():
                raise ProviderAuthenticationError("FRED rejected the configured API key.")
            response.raise_for_status()
            return response.json()
        except ProviderAuthenticationError:
            raise
        except Exception:
            # Requests errors may include the prepared URL, which contains the key.
            raise ProviderUnavailableError("FRED is temporarily unavailable.") from None

    @staticmethod
    def parse_search(payload: dict) -> list[SeriesCandidate]:
        return [
            SeriesCandidate(
                provider="fred",
                candidate_id=item["id"],
                title=item.get("title", item["id"]),
                description=item.get("notes", ""),
                frequency=item.get("frequency_short") or item.get("frequency"),
                units=item.get("units_short") or item.get("units"),
                start_date=item.get("observation_start"),
                end_date=item.get("observation_end"),
                coverage_source="FRED series search metadata",
                metadata={
                    "seasonal_adjustment": item.get("seasonal_adjustment"),
                    "notes": item.get("notes"),
                },
            )
            for item in payload.get("seriess", [])
        ]

    def search(self, query: str, limit: int = 10) -> list[SeriesCandidate]:
        payload = self._get("series/search", search_text=query, limit=limit, order_by="search_rank")
        return self.parse_search(payload)

    def fetch(self, candidate: ResolvedSeriesCandidate, start=None, end=None) -> FetchedSeries:
        try:
            obs = self._get(
                "series/observations",
                series_id=candidate.provider_series_id,
                observation_start=start or "1776-07-04",
                observation_end=end or "9999-12-31",
            )
            metadata_payload = self._get("series", series_id=candidate.provider_series_id)
        except Exception as exc:
            if isinstance(exc, (ProviderUnavailableError, ProviderAuthenticationError)):
                raise
            raise SeriesFetchError(f"FRED could not fetch {candidate.title}.") from exc
        raw = pd.DataFrame(obs.get("observations", []))
        if raw.empty:
            raise SeriesFetchError(f"FRED returned no observations for {candidate.title}.")
        values = pd.to_numeric(raw["value"].replace(".", pd.NA), errors="coerce")
        values.index = pd.to_datetime(raw["date"])
        values.name = candidate.series_key
        info = (metadata_payload.get("seriess") or [{}])[0]
        metadata = {
            **candidate.metadata,
            "provider_id": candidate.provider_series_id,
            "description": info.get("notes", ""),
            "units": info.get("units"),
            "frequency": info.get("frequency_short") or info.get("frequency"),
            "seasonal_adjustment": info.get("seasonal_adjustment"),
            "observation_start": info.get("observation_start"),
            "observation_end": info.get("observation_end"),
            "selected_value_field": "value",
        }
        return FetchedSeries(
            candidate.series_key,
            "FRED",
            candidate.title,
            raw,
            values,
            metadata,
            {"source": "FRED API", "series_id": candidate.provider_series_id},
            raw_payload=obs,
        )
