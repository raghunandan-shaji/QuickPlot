from __future__ import annotations

import pandas as pd

from series_lab.exceptions import ProviderUnavailableError, SeriesFetchError
from dataclasses import replace

from series_lab.models import FetchedSeries, ResolvedSeriesCandidate, SeriesCandidate

from .base import DataProvider


class YahooProvider(DataProvider):
    label = "Yahoo"
    provenance_label = "Yahoo Finance via yfinance"

    def __init__(self) -> None:
        super().__init__()
        self._availability_cache: dict[str, tuple[str | None, str | None]] = {}

    def is_available(self) -> bool:
        try:
            import yfinance  # noqa: F401

            return True
        except ImportError:
            return False

    def availability_message(self) -> str | None:
        return None if self.is_available() else "Install yfinance to use Yahoo search."

    @staticmethod
    def normalize_quotes(quotes: list[dict], limit: int = 10) -> list[SeriesCandidate]:
        results = []
        for quote in quotes[:limit]:
            symbol = quote.get("symbol")
            if not symbol:
                continue
            results.append(
                SeriesCandidate(
                    provider="yahoo",
                    candidate_id=symbol,
                    title=quote.get("longname") or quote.get("shortname") or symbol,
                    instrument_type=quote.get("quoteType"),
                    exchange=quote.get("exchange") or quote.get("exchDisp"),
                    metadata={
                        "symbol": symbol,
                        "currency": quote.get("currency"),
                        "quote_type": quote.get("quoteType"),
                        "long_name": quote.get("longname"),
                        "short_name": quote.get("shortname"),
                    },
                )
            )
        return results

    def search(self, query: str, limit: int = 10) -> list[SeriesCandidate]:
        if not self.is_available():
            raise ProviderUnavailableError(self.availability_message())
        try:
            import yfinance as yf

            search = yf.Search(query, max_results=limit, enable_fuzzy_query=False)
            return self.normalize_quotes(search.quotes, limit)
        except Exception as exc:
            raise ProviderUnavailableError("Yahoo search is temporarily unavailable.") from exc

    @staticmethod
    def _timestamp_date(value) -> str | None:
        if value in (None, ""):
            return None
        try:
            numeric = float(value)
            unit = "ms" if numeric > 10_000_000_000 else "s"
            return pd.to_datetime(numeric, unit=unit, utc=True).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            return None

    def resolve_availability(self, candidate: SeriesCandidate) -> SeriesCandidate:
        symbol = candidate.candidate_id
        if symbol not in self._availability_cache:
            try:
                import yfinance as yf

                metadata = yf.Ticker(symbol).get_history_metadata() or {}
                start = self._timestamp_date(metadata.get("firstTradeDate"))
                end = self._timestamp_date(metadata.get("regularMarketTime"))
                self._availability_cache[symbol] = (start, end)
            except Exception:
                self._availability_cache[symbol] = (None, None)
        start, end = self._availability_cache[symbol]
        if not start or not end:
            return candidate
        return replace(
            candidate,
            start_date=start,
            end_date=end,
            coverage_source="Yahoo history metadata via yfinance",
        )

    @staticmethod
    def normalize_history(raw: pd.DataFrame, series_key: str, value_field: str | None = None):
        if raw.empty:
            raise SeriesFetchError("Yahoo returned no historical observations.")
        frame = raw.copy(deep=True)
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = [c[0] if isinstance(c, tuple) else c for c in frame.columns]
        available = {str(col).lower().replace(" ", "_"): col for col in frame.columns}
        requested = (value_field or "").lower().replace(" ", "_")
        if requested and requested in available:
            chosen = available[requested]
        elif "adj_close" in available and frame[available["adj_close"]].notna().any():
            chosen = available["adj_close"]
        elif "close" in available:
            chosen = available["close"]
        else:
            raise SeriesFetchError("Yahoo history has neither adjusted close nor close values.")
        values = pd.to_numeric(frame[chosen], errors="coerce")
        values.index = pd.to_datetime(values.index).tz_localize(None)
        values.name = series_key
        return frame, values, str(chosen)

    def fetch(self, candidate: ResolvedSeriesCandidate, start=None, end=None) -> FetchedSeries:
        if not self.is_available():
            raise ProviderUnavailableError(self.availability_message())
        try:
            import yfinance as yf

            ticker = yf.Ticker(candidate.provider_series_id)
            raw = ticker.history(start=start, end=end, period=None if start else "max", auto_adjust=False)
            frame, values, chosen = self.normalize_history(raw, candidate.series_key, candidate.value_field)
            try:
                info = ticker.get_history_metadata() or {}
            except Exception:
                info = {}
        except SeriesFetchError:
            raise
        except Exception as exc:
            raise SeriesFetchError(f"Yahoo could not fetch {candidate.title}.") from exc
        metadata = {
            **candidate.metadata,
            "provider_id": candidate.provider_series_id,
            "frequency": "Daily",
            "currency": info.get("currency") or candidate.metadata.get("currency"),
            "exchange": info.get("exchangeName") or candidate.metadata.get("exchange"),
            "selected_value_field": chosen,
        }
        return FetchedSeries(
            candidate.series_key,
            self.provenance_label,
            candidate.title,
            frame,
            values,
            metadata,
            {"source": self.provenance_label, "symbol": candidate.provider_series_id},
        )
