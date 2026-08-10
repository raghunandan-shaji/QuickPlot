from __future__ import annotations

import heapq
import json
from hashlib import sha1

import pandas as pd

from series_lab.config import REQUEST_TIMEOUT
from series_lab.exceptions import ProviderUnavailableError, SeriesFetchError, SeriesResolutionError
from series_lab.models import FetchedSeries, ResolvedSeriesCandidate, SeriesCandidate
from series_lab.services.search import text_score

from .base import DataProvider


class EiaProvider(DataProvider):
    label = "EIA"
    base_url = "https://api.eia.gov/v2"

    def __init__(self, api_key: str = "") -> None:
        super().__init__()
        self.api_key = api_key
        self._metadata_cache: dict[str, dict] = {}
        self._facet_cache: dict[tuple[str, str], list[dict]] = {}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def availability_message(self) -> str | None:
        return None if self.api_key else "Configure EIA_API_KEY to search and fetch EIA data."

    def metadata(self, route: str = "") -> dict:
        if not self.api_key:
            raise ProviderUnavailableError(self.availability_message())
        route = route.strip("/")
        if route not in self._metadata_cache:
            response = self.session.get(
                f"{self.base_url}/{route}/" if route else f"{self.base_url}/",
                params={"api_key": self.api_key},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            self._metadata_cache[route] = response.json().get("response", {})
        return self._metadata_cache[route]

    def search(self, query: str, limit: int = 10) -> list[SeriesCandidate]:
        if not self.is_available():
            raise ProviderUnavailableError(self.availability_message())
        heap: list[tuple[float, int, str]] = [(0.0, 0, "")]
        visited: set[str] = set()
        results: list[tuple[float, SeriesCandidate]] = []
        requests_used = 0
        while heap and requests_used < 16 and len(results) < limit * 2:
            _, depth, route = heapq.heappop(heap)
            if route in visited or depth > 4:
                continue
            visited.add(route)
            node = self.metadata(route)
            requests_used += 1
            node_name = " ".join(str(node.get(k, "")) for k in ("id", "name", "description"))
            data_columns = node.get("data") or {}
            for field, detail in data_columns.items():
                if not isinstance(detail, dict):
                    detail = {"alias": str(detail)}
                label = detail.get("alias") or detail.get("name") or field
                combined = f"{route} {node_name} {field} {label} {detail.get('description', '')}"
                score = text_score(query, combined)
                candidate_id = f"{route}|{field}"
                results.append(
                    (
                        score,
                        SeriesCandidate(
                            provider="eia",
                            candidate_id=candidate_id,
                            title=f"{node.get('name') or route} — {label}",
                            description=detail.get("description", node.get("description", "")),
                            units=detail.get("units"),
                            start_date=node.get("startPeriod") or node.get("start"),
                            end_date=node.get("endPeriod") or node.get("end"),
                            coverage_source="EIA route metadata" if (node.get("startPeriod") or node.get("start")) and (node.get("endPeriod") or node.get("end")) else None,
                            requires_resolution=bool(node.get("facets")),
                            metadata={
                                "route": route,
                                "value_field": field,
                                "frequencies": node.get("frequency", []),
                                "facets": node.get("facets", []),
                            },
                        ),
                    )
                )
            for child in node.get("routes", []) or []:
                child_id = child.get("id", "")
                child_route = "/".join(filter(None, [route, child_id]))
                label = " ".join(str(child.get(k, "")) for k in ("id", "name", "description"))
                score = text_score(query, label)
                heapq.heappush(heap, (-score, depth + 1, child_route))
        return [item for _, item in sorted(results, key=lambda x: x[0], reverse=True)[:limit]]

    def facet_values(self, route: str, facet_id: str) -> list[dict]:
        key = (route, facet_id)
        if key not in self._facet_cache:
            response = self.session.get(
                f"{self.base_url}/{route}/facet/{facet_id}/",
                params={"api_key": self.api_key, "length": 5000},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            self._facet_cache[key] = response.json().get("response", {}).get("facets", [])
        return list(self._facet_cache[key])

    @staticmethod
    def parse_data(payload: dict, series_key: str, value_field: str) -> tuple[pd.DataFrame, pd.Series]:
        records = payload.get("response", {}).get("data", [])
        raw = pd.DataFrame(records)
        if raw.empty or value_field not in raw:
            raise SeriesFetchError("EIA returned no usable observations.")
        if raw["period"].duplicated().any():
            raise SeriesResolutionError(
                "EIA returned multiple records for a period. Select another facet to identify one series."
            )
        periods = raw["period"].astype(str)
        dates = pd.to_datetime(periods, errors="coerce")
        annual = dates.isna() & periods.str.fullmatch(r"\d{4}")
        dates.loc[annual] = pd.to_datetime(periods[annual] + "-12-31")
        quarterly = dates.isna() & periods.str.fullmatch(r"\d{4}-Q[1-4]")
        dates.loc[quarterly] = pd.PeriodIndex(periods[quarterly], freq="Q").to_timestamp(how="end").normalize()
        values = pd.Series(pd.to_numeric(raw[value_field], errors="coerce").to_numpy(), index=dates)
        values = values[~values.index.isna()].sort_index()
        values.name = series_key
        return raw, values

    def fetch(self, candidate: ResolvedSeriesCandidate, start=None, end=None) -> FetchedSeries:
        route, fallback_field = candidate.provider_series_id.split("|", 1)
        value_field = candidate.value_field or candidate.metadata.get("value_field") or fallback_field
        facets = candidate.resolution_parameters.get("facets", {})
        required = [f.get("id") for f in candidate.metadata.get("facets", []) if f.get("id")]
        missing = [facet for facet in required if facet not in facets]
        if missing:
            raise SeriesResolutionError(f"Resolve EIA facets before fetching: {', '.join(missing)}.")
        frequency = candidate.resolution_parameters.get("frequency")
        params: list[tuple[str, str]] = [("api_key", self.api_key), ("data[0]", value_field), ("length", "5000")]
        if frequency:
            params.append(("frequency", frequency))
        if start:
            params.append(("start", start))
        if end:
            params.append(("end", end))
        for facet, value in facets.items():
            params.append((f"facets[{facet}][]", str(value)))
        try:
            response = self.session.get(f"{self.base_url}/{route}/data/", params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            raw, values = self.parse_data(payload, candidate.series_key, value_field)
        except (SeriesResolutionError, SeriesFetchError):
            raise
        except Exception as exc:
            raise SeriesFetchError(f"EIA could not fetch {candidate.title}.") from exc
        return FetchedSeries(
            candidate.series_key,
            "EIA",
            candidate.title,
            raw,
            values,
            {
                **candidate.metadata,
                "provider_id": candidate.provider_series_id,
                "resolution_parameters": candidate.resolution_parameters,
                "frequency": frequency,
                "selected_value_field": value_field,
            },
            {"source": "EIA API v2", "route": route, "facets": facets},
            raw_payload=payload,
        )
