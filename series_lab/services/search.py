from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from time import monotonic

import pandas as pd
from rapidfuzz.fuzz import ratio, token_set_ratio

from series_lab.models import SeriesCandidate


SEARCH_CACHE_TTL_SECONDS = 5 * 60
AVAILABILITY_CACHE_TTL_SECONDS = 30 * 60
STRONG_MARKET_TERMS = {"comex", "lbma", "futures", "future", "spot", "etf", "ticker"}
MARKET_TERMS = STRONG_MARKET_TERMS | {"price", "index"}
BLS_INTENT_TERMS = {"ppi", "cpi", "mining", "industry", "industrial"}


def normalize_text(value: object) -> str:
    text = str(value or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.=+_-]+", " ", text)).strip()


def text_score(query: str, text: str) -> float:
    q, t = normalize_text(query), normalize_text(text)
    if not q:
        return 0.0
    score = 0.0
    if q == t:
        score += 1000
    if q in t:
        score += 300
    q_tokens, t_tokens = set(q.split()), set(t.split())
    score += 150 * len(q_tokens & t_tokens) / max(1, len(q_tokens))
    score += 0.7 * token_set_ratio(q, t) + 0.3 * ratio(q, t)
    return score


def candidate_unique_key(candidate: SeriesCandidate) -> str:
    """Stable search-result identity independent of row position or query."""
    return f"{normalize_text(candidate.provider)}:{candidate.candidate_id}"


def _provider_search_cached(provider, query: str, limit: int) -> list[SeriesCandidate]:
    key = (normalize_text(query), int(limit))
    now = monotonic()
    cache = getattr(provider, "_quickplot_search_cache", None)
    if cache is None:
        cache = {}
        try:
            setattr(provider, "_quickplot_search_cache", cache)
        except Exception:
            return provider.search(query, limit)
    cached = cache.get(key)
    if cached and now - cached[0] < SEARCH_CACHE_TTL_SECONDS:
        return list(cached[1])
    results = list(provider.search(query, limit))
    cache[key] = (now, tuple(results))
    return results


def _availability_cached(provider, candidate: SeriesCandidate) -> SeriesCandidate:
    key = candidate_unique_key(candidate)
    now = monotonic()
    cache = getattr(provider, "_quickplot_availability_cache", None)
    if cache is None:
        cache = {}
        try:
            setattr(provider, "_quickplot_availability_cache", cache)
        except Exception:
            return provider.resolve_availability(candidate)
    cached = cache.get(key)
    if cached and now - cached[0] < AVAILABILITY_CACHE_TTL_SECONDS:
        return cached[1]
    result = provider.resolve_availability(candidate)
    cache[key] = (now, result)
    return result


def rank_catalog(
    frame: pd.DataFrame,
    query: str,
    id_column: str,
    title_column: str,
    limit: int = 10,
    extra_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    q = normalize_text(query)
    scored = frame.copy()
    def score(row):
        item_id = normalize_text(row.get(id_column, ""))
        title = normalize_text(row.get(title_column, ""))
        extras = " ".join(normalize_text(row.get(c, "")) for c in extra_columns)
        value = text_score(q, f"{item_id} {title} {extras}")
        if item_id == q:
            value += 10000
        if title == q:
            value += 2000
        elif q and q in title:
            value += 500
        return value
    scored["_score"] = scored.apply(score, axis=1)
    return scored.sort_values(["_score", id_column], ascending=[False, True]).head(limit).drop(columns="_score")


@dataclass
class SearchOutcome:
    results: list[SeriesCandidate]
    failures: dict[str, str]
    partial_results: list[SeriesCandidate] = field(default_factory=list)
    unknown_results: list[SeriesCandidate] = field(default_factory=list)
    coverage_message: str | None = None


def _availability_date(value: object, side: str) -> pd.Timestamp | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.lower() in {"present", "current", "today"}:
        return pd.Timestamp.today().normalize() if side == "end" else None
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        return pd.Timestamp(year, 12, 31) if side == "end" else pd.Timestamp(year, 1, 1)
    if re.fullmatch(r"\d{4}-\d{2}", text):
        date = pd.Timestamp(f"{text}-01")
        return date + pd.offsets.MonthEnd(0) if side == "end" else date
    try:
        return pd.Timestamp(text).tz_localize(None)
    except (TypeError, ValueError):
        return None


def evaluate_coverage(
    candidate: SeriesCandidate,
    requested_start,
    requested_end,
) -> SeriesCandidate:
    request_start = pd.Timestamp(requested_start).normalize()
    request_end = pd.Timestamp(requested_end).normalize()
    if request_start > request_end:
        raise ValueError("Coverage start date must not be after the end date.")
    series_start = _availability_date(candidate.start_date, "start")
    series_end = _availability_date(candidate.end_date, "end")
    if series_start is None or series_end is None:
        return replace(
            candidate,
            available_start=series_start.date().isoformat() if series_start is not None else None,
            available_end=series_end.date().isoformat() if series_end is not None else None,
            coverage_ratio=None,
            coverage_status="unknown",
            coverage_missing_ranges=(),
        )
    if series_end < series_start:
        return replace(candidate, coverage_ratio=None, coverage_status="unknown")
    if request_start == request_end:
        ratio_value = 1.0 if series_start <= request_start <= series_end else 0.0
    else:
        intersection_start = max(request_start, series_start)
        intersection_end = min(request_end, series_end)
        if intersection_end < intersection_start:
            ratio_value = 0.0
        else:
            ratio_value = (intersection_end - intersection_start).days / (request_end - request_start).days
    ratio_value = max(0.0, min(1.0, float(ratio_value)))
    if ratio_value >= 1.0 - 1e-9:
        status = "full"
        ratio_value = 1.0
    elif ratio_value > 0:
        status = "partial"
    else:
        status = "none"
    missing = []
    if series_start > request_start:
        missing_end = min(request_end, series_start - pd.Timedelta(days=1))
        if request_start <= missing_end:
            missing.append(f"{request_start.date().isoformat()} → {missing_end.date().isoformat()}")
    if series_end < request_end:
        missing_start = max(request_start, series_end + pd.Timedelta(days=1))
        if missing_start <= request_end:
            missing.append(f"{missing_start.date().isoformat()} → {request_end.date().isoformat()}")
    return replace(
        candidate,
        available_start=series_start.date().isoformat(),
        available_end=series_end.date().isoformat(),
        coverage_ratio=ratio_value,
        coverage_status=status,
        coverage_missing_ranges=tuple(missing),
    )


def candidate_relevance(candidate: SeriesCandidate, query: str) -> float:
    metadata = " ".join(f"{key} {value}" for key, value in sorted(candidate.metadata.items()))
    searchable = " ".join(
        filter(
            None,
            [
                candidate.candidate_id,
                candidate.title,
                candidate.description,
                candidate.instrument_type,
                candidate.exchange,
                metadata,
            ],
        )
    )
    score = text_score(query, searchable)
    query_text = normalize_text(query)
    query_tokens = set(query_text.split())
    candidate_text = normalize_text(searchable)
    provider = normalize_text(candidate.provider).replace(" ", "_")
    strong_market_intent = bool(query_tokens & STRONG_MARKET_TERMS)
    market_intent = strong_market_intent or bool(query_tokens & MARKET_TERMS)
    bls_intent = bool(query_tokens & BLS_INTENT_TERMS) or "producer price" in query_text
    market_evidence = any(
        term in candidate_text
        for term in ("price", "spot", "future", "futures", "index", "etf", "commodity", "bullion")
    )

    if bls_intent and provider == "bls":
        score += 500
    if market_intent:
        if provider == "yahoo":
            score += 420 if strong_market_intent else 180
            if any(term in candidate_text for term in query_tokens & {"comex", "lbma"}):
                score += 220
        elif provider == "fred":
            score += 220 if market_evidence else 40
        elif provider == "bls" and not bls_intent:
            score -= 520 if strong_market_intent else 220
        elif provider == "world_bank":
            score -= 520 if strong_market_intent else 220
            if "natural capital" in candidate_text:
                score -= 260
        elif provider == "eia" and market_evidence:
            score += 80
    return max(0.0, score)


def rank_candidates_by_relevance(
    candidates: list[SeriesCandidate],
    query: str,
) -> list[SeriesCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate_relevance(candidate, query),
            candidate.title.lower(),
            candidate.provider,
            candidate.candidate_id,
        ),
    )


def rank_candidates_by_coverage(
    candidates: list[SeriesCandidate],
    query: str,
) -> list[SeriesCandidate]:
    if not candidates:
        return []
    relevance = {id(candidate): candidate_relevance(candidate, query) for candidate in candidates}
    maximum = max(relevance.values()) or 1.0

    def sort_key(candidate: SeriesCandidate):
        relevance_normalized = relevance[id(candidate)] / maximum
        # Coverage is intentionally secondary. Unknown receives a neutral 0.45,
        # not zero, so it remains discoverable without being advertised as full.
        coverage_feature = candidate.coverage_ratio if candidate.coverage_ratio is not None else 0.45
        combined = 0.85 * relevance_normalized + 0.15 * coverage_feature
        known = candidate.coverage_ratio is not None
        return (-combined, -relevance[id(candidate)], -int(known), -(candidate.coverage_ratio or 0.0), candidate.title.lower(), candidate.candidate_id)

    return sorted(candidates, key=sort_key)


def apply_coverage_requirement(
    candidates: list[SeriesCandidate],
    query: str,
    requested_start,
    requested_end,
    mode: str = "rank_by_coverage",
) -> tuple[list[SeriesCandidate], list[SeriesCandidate], list[SeriesCandidate], str | None]:
    evaluated = [evaluate_coverage(candidate, requested_start, requested_end) for candidate in candidates]
    ranked = rank_candidates_by_coverage(evaluated, query)
    if mode == "rank_by_coverage":
        return ranked, [], [], None
    if mode != "require_full_coverage":
        raise ValueError(f"Unknown coverage mode: {mode}.")
    full = [candidate for candidate in ranked if candidate.coverage_status == "full"]
    partial = [candidate for candidate in ranked if candidate.coverage_status in {"partial", "none"}]
    unknown = [candidate for candidate in ranked if candidate.coverage_status == "unknown"]
    message = None if full else "No results fully cover the requested period."
    return full, partial, unknown, message


def search_providers(
    providers: dict,
    query: str,
    selected: list[str],
    limit: int = 8,
    requested_start=None,
    requested_end=None,
    coverage_mode: str = "rank_by_coverage",
) -> SearchOutcome:
    results: list[SeriesCandidate] = []
    failures: dict[str, str] = {}
    active = {name: providers[name] for name in selected if name in providers}
    with ThreadPoolExecutor(max_workers=min(5, max(1, len(active)))) as pool:
        futures = {
            pool.submit(_provider_search_cached, provider, query, limit): name
            for name, provider in active.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results.extend(future.result())
            except Exception as exc:
                failures[name] = str(exc) or f"{name} search failed."
    results = rank_candidates_by_relevance(results, query)
    if requested_start is None and requested_end is None:
        return SearchOutcome(results, failures)
    if requested_start is None or requested_end is None:
        raise ValueError("Choose both coverage dates or leave both blank.")

    # Yahoo search results frequently omit history bounds. Resolve only the top
    # three semantic matches, then cache those lightweight metadata results in
    # the provider instance. Other unknown candidates remain explicitly unknown.
    yahoo_provider = providers.get("Yahoo")
    if yahoo_provider:
        yahoo_candidates = [candidate for candidate in results if candidate.provider == "yahoo" and (not candidate.start_date or not candidate.end_date)]
        top_yahoo = sorted(yahoo_candidates, key=lambda candidate: candidate_relevance(candidate, query), reverse=True)[:3]
        with ThreadPoolExecutor(max_workers=max(1, len(top_yahoo))) as pool:
            enriched_results = list(
                pool.map(
                    lambda candidate: _availability_cached(yahoo_provider, candidate),
                    top_yahoo,
                )
            )
        enriched = {candidate.candidate_id: candidate for candidate in enriched_results}
        results = [enriched.get(candidate.candidate_id, candidate) if candidate.provider == "yahoo" else candidate for candidate in results]

    ranked, partial, unknown, message = apply_coverage_requirement(
        results, query, requested_start, requested_end, coverage_mode
    )
    return SearchOutcome(ranked, failures, partial, unknown, message)
