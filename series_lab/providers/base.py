from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from series_lab.config import REQUEST_TIMEOUT
from series_lab.models import FetchedSeries, ResolvedSeriesCandidate, SeriesCandidate


def resilient_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    # BLS' official bulk-download host rejects generic library user agents.
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; QuickPlot/1.0; research time-series client)",
            "Accept": "application/json,text/plain,*/*",
        }
    )
    return session


class DataProvider(ABC):
    label: str

    def __init__(self) -> None:
        self.session = resilient_session()

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[SeriesCandidate]:
        raise NotImplementedError

    @abstractmethod
    def fetch(
        self,
        candidate: ResolvedSeriesCandidate,
        start: str | None = None,
        end: str | None = None,
    ) -> FetchedSeries:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    def availability_message(self) -> str | None:
        return None

    def resolve_availability(self, candidate: SeriesCandidate) -> SeriesCandidate:
        """Optionally enrich cheap availability metadata without fetching observations."""
        return candidate
