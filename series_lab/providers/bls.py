from __future__ import annotations

from io import StringIO

import pandas as pd

from series_lab.config import REQUEST_TIMEOUT
from series_lab.exceptions import SeriesFetchError
from series_lab.models import FetchedSeries, ResolvedSeriesCandidate, SeriesCandidate
from series_lab.services.search import rank_catalog

from .base import DataProvider
from .catalog_cache import cached_catalog_text


CATALOGS = {
    "CPI": "https://download.bls.gov/pub/time.series/cu/cu.series",
    "PPI": "https://download.bls.gov/pub/time.series/pc/pc.series",
}


class BlsProvider(DataProvider):
    label = "BLS"
    api_url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self.api_key = api_key
        self._catalog: pd.DataFrame | None = None

    def is_available(self) -> bool:
        return True

    def load_catalog(self) -> pd.DataFrame:
        if self._catalog is not None:
            return self._catalog
        frames = []
        for family, url in CATALOGS.items():
            frame = pd.read_csv(StringIO(cached_catalog_text(url)), sep="\t", dtype=str)
            frame.columns = [str(c).strip() for c in frame.columns]
            for column in frame.select_dtypes(include="object"):
                frame[column] = frame[column].str.strip()
            frame["catalog"] = family
            frames.append(frame)
        self._catalog = pd.concat(frames, ignore_index=True)
        return self._catalog

    def search(self, query: str, limit: int = 10) -> list[SeriesCandidate]:
        catalog = self.load_catalog()
        ranked = rank_catalog(catalog, query, "series_id", "series_title", limit)
        return [
            SeriesCandidate(
                provider="bls",
                candidate_id=row["series_id"],
                title=row.get("series_title", row["series_id"]),
                frequency="Monthly" if row.get("periodicity_code") in ("R", "M") else None,
                units=row.get("base_code"),
                start_date=self._catalog_date(row, "begin"),
                end_date=self._catalog_date(row, "end"),
                coverage_source="BLS CPI/PPI catalog",
                metadata={k: v for k, v in row.items() if pd.notna(v)},
            )
            for row in ranked.to_dict("records")
        ]

    @staticmethod
    def _catalog_date(row: dict, side: str) -> str | None:
        year = row.get(f"{side}_year")
        period = row.get(f"{side}_period")
        if not year or pd.isna(year):
            return None
        if isinstance(period, str) and period.startswith("M") and period[1:].isdigit():
            month = int(period[1:])
            if 1 <= month <= 12:
                date = pd.Timestamp(int(year), month, 1)
                if side == "end":
                    date += pd.offsets.MonthEnd(0)
                return date.date().isoformat()
        return str(year)

    @staticmethod
    def parse_series(payload: dict, series_id: str) -> tuple[pd.DataFrame, pd.Series]:
        series_list = payload.get("Results", {}).get("series", [])
        if not series_list:
            raise SeriesFetchError(f"BLS returned no data for {series_id}.")
        records = series_list[0].get("data", [])
        raw = pd.DataFrame(records)
        if raw.empty:
            raise SeriesFetchError(f"BLS returned no observations for {series_id}.")
        raw = raw[raw["period"].isin([f"M{i:02d}" for i in range(1, 13)])].copy()
        dates = pd.to_datetime(
            raw["year"].astype(str) + "-" + raw["period"].str[1:] + "-01"
        ) + pd.offsets.MonthEnd(0)
        values = pd.Series(pd.to_numeric(raw["value"], errors="coerce").to_numpy(), index=dates)
        values = values.sort_index()
        values.name = series_id
        return raw, values

    def fetch(self, candidate: ResolvedSeriesCandidate, start=None, end=None) -> FetchedSeries:
        end_year = pd.Timestamp(end or "today").year
        start_year = pd.Timestamp(start).year if start else max(1913, end_year - 20)
        body = {
            "seriesid": [candidate.provider_series_id],
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self.api_key:
            body["registrationkey"] = self.api_key
        try:
            response = self.session.post(self.api_url, json=body, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            raw, values = self.parse_series(payload, candidate.series_key)
        except SeriesFetchError:
            raise
        except Exception as exc:
            raise SeriesFetchError(f"BLS could not fetch {candidate.title}.") from exc
        return FetchedSeries(
            candidate.series_key,
            "BLS",
            candidate.title,
            raw,
            values,
            {**candidate.metadata, "provider_id": candidate.provider_series_id, "frequency": "Monthly", "selected_value_field": "value"},
            {"source": "BLS Public Data API", "series_id": candidate.provider_series_id},
            raw_payload=payload,
        )
