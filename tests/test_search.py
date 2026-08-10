import pandas as pd
import pytest

from series_lab.models import SeriesCandidate
from series_lab.services.search import (
    apply_coverage_requirement,
    candidate_relevance,
    evaluate_coverage,
    rank_candidates_by_coverage,
    rank_candidates_by_relevance,
    rank_catalog,
    search_providers,
)
from series_lab.ui.search_section import candidate_is_added


def test_exact_id_ranks_before_fuzzy_title():
    frame = pd.DataFrame([
        {"id": "CU123", "title": "Consumer copper index"},
        {"id": "OTHER", "title": "CU123 approximate title"},
    ])
    result = rank_catalog(frame, "CU123", "id", "title")
    assert result.iloc[0]["id"] == "CU123"


def test_ranking_is_deterministic():
    frame = pd.DataFrame([{"id": "B", "title": "Copper"}, {"id": "A", "title": "Copper"}])
    first = rank_catalog(frame, "copper", "id", "title")
    second = rank_catalog(frame, "copper", "id", "title")
    assert first["id"].tolist() == second["id"].tolist() == ["A", "B"]


def candidate(candidate_id, title, start=None, end=None):
    return SeriesCandidate("test", candidate_id, title, start_date=start, end_date=end)


def test_date_span_coverage_full_partial_none_and_unknown():
    requested = ("2000-01-01", "2020-12-31")
    cases = {
        "full": candidate("full", "Copper full", "1990", "2025"),
        "late": candidate("late", "Copper late", "2005", "2025"),
        "early": candidate("early", "Copper early", "1980", "2010"),
        "small": candidate("small", "Copper small", "2005", "2010"),
        "none": candidate("none", "Copper old", "1980", "1999"),
        "unknown": candidate("unknown", "Copper unknown"),
    }
    evaluated = {name: evaluate_coverage(item, *requested) for name, item in cases.items()}
    assert evaluated["full"].coverage_status == "full"
    assert evaluated["full"].coverage_ratio == 1
    assert evaluated["late"].coverage_status == "partial"
    assert evaluated["early"].coverage_status == "partial"
    assert 0 < evaluated["small"].coverage_ratio < evaluated["late"].coverage_ratio
    assert evaluated["none"].coverage_status == "none"
    assert evaluated["none"].coverage_ratio == 0
    assert evaluated["unknown"].coverage_status == "unknown"
    assert evaluated["unknown"].coverage_ratio is None


def test_single_day_coverage_is_safe():
    available = evaluate_coverage(candidate("x", "Copper", "2020", "2020"), "2020-06-01", "2020-06-01")
    unavailable = evaluate_coverage(candidate("y", "Copper", "2019", "2019"), "2020-06-01", "2020-06-01")
    assert available.coverage_ratio == 1
    assert unavailable.coverage_ratio == 0


def test_full_coverage_filter_and_explained_partial_fallback():
    results, partial, unknown, message = apply_coverage_requirement(
        [
            candidate("full", "Copper price", "1990", "2025"),
            candidate("partial", "Copper index", "2005", "2025"),
            candidate("unknown", "Copper futures"),
        ],
        "copper",
        "2000-01-01",
        "2020-12-31",
        "require_full_coverage",
    )
    assert [item.candidate_id for item in results] == ["full"]
    assert [item.candidate_id for item in partial] == ["partial"]
    assert [item.candidate_id for item in unknown] == ["unknown"]
    assert message is None
    no_full, partial, _, message = apply_coverage_requirement(
        [candidate("partial", "Copper index", "2005", "2025")],
        "copper", "2000-01-01", "2020-12-31", "require_full_coverage",
    )
    assert no_full == []
    assert partial
    assert message == "No results fully cover the requested period."


def test_relevance_remains_primary_and_coverage_breaks_close_matches():
    excellent = evaluate_coverage(candidate("excellent", "Global copper price benchmark", "2000-06", "2025"), "2000-01-01", "2020-12-31")
    irrelevant = evaluate_coverage(candidate("irrelevant", "Banana crop acreage", "1990", "2025"), "2000-01-01", "2020-12-31")
    ranked = rank_candidates_by_coverage([irrelevant, excellent], "copper price")
    assert ranked[0].candidate_id == "excellent"
    lower = evaluate_coverage(candidate("lower", "Copper price index", "2005", "2025"), "2000-01-01", "2020-12-31")
    higher = evaluate_coverage(candidate("higher", "Copper price index", "1990", "2025"), "2000-01-01", "2020-12-31")
    ranked_close = rank_candidates_by_coverage([lower, higher], "copper price index")
    assert ranked_close[0].candidate_id == "higher"


def test_missing_interval_labels_are_calendar_ranges():
    result = evaluate_coverage(candidate("x", "Copper", "2005", "2010"), "2000-01-01", "2020-12-31")
    assert result.coverage_missing_ranges == (
        "2000-01-01 → 2004-12-31",
        "2011-01-01 → 2020-12-31",
    )


@pytest.mark.parametrize(
    ("query", "expected_provider"),
    [
        ("comex silver", "yahoo"),
        ("gold lbma", "yahoo"),
        ("silver ppi", "bls"),
        ("gold mining ppi", "bls"),
    ],
)
def test_query_intent_ranks_the_right_candidate_family(query, expected_provider):
    candidates = [
        SeriesCandidate("yahoo", "SI=F", "Silver and Gold Futures", instrument_type="FUTURE", exchange="COMEX"),
        SeriesCandidate("fred", "METALPRICE", "Global market price of silver and gold", description="Price index"),
        SeriesCandidate("bls", "PPI-METALS", "PPI industry data for Gold ore and silver ore mining"),
        SeriesCandidate("world_bank", "NATURAL-CAPITAL", "Nonrenewable natural capital: gold and silver"),
    ]
    ranked = rank_candidates_by_relevance(candidates, query)
    assert ranked[0].provider == expected_provider
    if query in {"comex silver", "gold lbma"}:
        assert candidate_relevance(ranked[0], query) > candidate_relevance(
            next(item for item in ranked if item.provider == "world_bank"), query
        )


def test_new_candidate_at_same_result_position_does_not_inherit_added_state():
    old = SeriesCandidate("fred", "OLD", "Old result")
    replacement = SeriesCandidate("fred", "NEW", "New result")
    workspace = {"fred:OLD": object()}
    assert candidate_is_added(old, workspace)
    assert not candidate_is_added(replacement, workspace)


def test_identical_provider_search_is_cached_but_a_new_query_is_not():
    class CountingProvider:
        def __init__(self):
            self.calls = 0

        def search(self, query, limit=8):
            self.calls += 1
            return [SeriesCandidate("test", query, query)]

    provider = CountingProvider()
    providers = {"Test": provider}
    search_providers(providers, "gold", ["Test"])
    search_providers(providers, "gold", ["Test"])
    assert provider.calls == 1
    search_providers(providers, "silver", ["Test"])
    assert provider.calls == 2


def test_yahoo_availability_is_bounded_and_cached():
    class CountingYahoo:
        def __init__(self):
            self.search_calls = 0
            self.availability_calls = 0

        def search(self, query, limit=8):
            self.search_calls += 1
            return [SeriesCandidate("yahoo", f"Y{i}", f"Gold future {i}") for i in range(6)]

        def resolve_availability(self, item):
            self.availability_calls += 1
            return item

    yahoo = CountingYahoo()
    providers = {"Yahoo": yahoo}
    kwargs = dict(requested_start="2000-01-01", requested_end="2025-12-31")
    search_providers(providers, "gold futures", ["Yahoo"], **kwargs)
    search_providers(providers, "gold futures", ["Yahoo"], **kwargs)
    assert yahoo.search_calls == 1
    assert yahoo.availability_calls == 3
