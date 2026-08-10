from __future__ import annotations

import html
from datetime import date

import streamlit as st

from series_lab.config import redact_secrets
from series_lab.models import WorkspaceSeries, resolve_candidate
from series_lab.services.fetch import fetch_resolved
from series_lab.services.search import candidate_unique_key, search_providers
from series_lab.state import add_to_workspace


def _meta(candidate) -> str:
    parts = [candidate.provider.replace("_", " ").title(), candidate.candidate_id]
    for value in (candidate.frequency, candidate.units, candidate.instrument_type, candidate.exchange):
        if value:
            parts.append(str(value))
    if candidate.start_date or candidate.end_date:
        parts.append(f"{candidate.start_date or '—'} — {candidate.end_date or 'present'}")
    return html.escape(" · ".join(parts))


def _coverage_html(candidate) -> str:
    if candidate.coverage_status == "unknown":
        return '<div class="coverage-line coverage-unknown">coverage unavailable until selected or resolved</div>'
    percent = round(100 * candidate.coverage_ratio)
    label = "full coverage" if candidate.coverage_status == "full" else f"coverage: {percent}%"
    missing = ""
    if candidate.coverage_missing_ranges:
        missing = " · missing: " + "; ".join(candidate.coverage_missing_ranges)
    source = f" · {candidate.coverage_source}" if candidate.coverage_source else ""
    return (
        f'<div class="coverage-line coverage-{candidate.coverage_status}">'
        f'{html.escape(label + missing + source)}</div>'
    )


def candidate_is_added(candidate, workspace, resolution=None, value_field=None) -> bool:
    try:
        resolved = resolve_candidate(candidate, resolution, value_field)
    except Exception:
        return False
    return resolved.series_key in workspace


def _fetch_and_add(candidate, providers, resolution=None, value_field=None) -> tuple[bool, str]:
    resolved = resolve_candidate(candidate, resolution, value_field)
    try:
        with st.spinner(f"Fetching {candidate.title}…"):
            fetched = fetch_resolved(providers, resolved)
    except Exception as exc:
        message = str(redact_secrets(str(exc))) or "This series is unavailable for the selected resolution."
        st.session_state.search_unavailable[resolved.series_key] = message
        return False, resolved.series_key
    add_to_workspace(st.session_state, WorkspaceSeries(fetched))
    st.session_state.search_unavailable.pop(resolved.series_key, None)
    return True, resolved.series_key


def render_search(providers: dict) -> None:
    st.markdown("## add series")
    available = list(providers)
    with st.form("series_search_form"):
        query = st.text_input("Search", value=st.session_state.search_query, placeholder="search economic, financial, commodity or energy series…")
        selected = st.multiselect("Sources", available, default=[p for p in st.session_state.selected_providers if p in available])
        with st.expander("date coverage (optional)"):
            date_left, date_right = st.columns(2)
            with date_left:
                coverage_start = st.date_input(
                    "From",
                    min_value=date(1800, 1, 1),
                    max_value=date(2100, 12, 31),
                    key="search_coverage_from_input",
                )
            with date_right:
                coverage_end = st.date_input(
                    "To",
                    min_value=date(1800, 1, 1),
                    max_value=date(2100, 12, 31),
                    key="search_coverage_to_input",
                )
            coverage_mode_label = st.segmented_control(
                "Coverage mode",
                ["Rank by coverage", "Require full coverage"],
                key="search_coverage_mode_input",
            ) or "Rank by coverage"
        submitted = st.form_submit_button("search series", width="content")
    unavailable = [f"{name}: {provider.availability_message()}" for name, provider in providers.items() if not provider.is_available() and provider.availability_message()]
    if unavailable:
        st.caption(" · ".join(unavailable))
    if submitted:
        st.session_state.search_query = query.strip()
        st.session_state.selected_providers = selected
        st.session_state.search_results = []
        st.session_state.search_failures = {}
        st.session_state.search_partial_results = []
        st.session_state.search_unknown_results = []
        st.session_state.search_coverage_message = None
        st.session_state.search_unavailable = {}
        st.session_state.search_resolution_active = {}
        if not query.strip():
            st.warning("Enter a search phrase or exact series ID.")
        elif not selected:
            st.warning("Select at least one source.")
        elif (coverage_start is None) != (coverage_end is None):
            st.warning("Choose both coverage dates or leave both blank.")
        elif coverage_start is not None and coverage_start > coverage_end:
            st.warning("Coverage start date must not be after the end date.")
        else:
            coverage_mode = "require_full_coverage" if coverage_mode_label == "Require full coverage" else "rank_by_coverage"
            with st.spinner("Searching selected sources…"):
                outcome = search_providers(
                    providers,
                    query.strip(),
                    selected,
                    requested_start=coverage_start,
                    requested_end=coverage_end,
                    coverage_mode=coverage_mode,
                )
            st.session_state.search_results = outcome.results
            st.session_state.search_failures = outcome.failures
            st.session_state.search_partial_results = outcome.partial_results
            st.session_state.search_unknown_results = outcome.unknown_results
            st.session_state.search_coverage_message = outcome.coverage_message
            st.session_state.search_coverage_start = coverage_start
            st.session_state.search_coverage_end = coverage_end
            st.session_state.search_coverage_mode = coverage_mode
            st.session_state.search_show_partials = False
            st.session_state.search_show_unknown = False
    has_search_output = bool(st.session_state.search_query or st.session_state.search_results or st.session_state.search_failures)
    if has_search_output:
        st.markdown('<div class="results-label">search results</div>', unsafe_allow_html=True)
        with st.container(height=340, border=True, key="search_results_region"):
            for source, message in st.session_state.search_failures.items():
                st.caption(f"{source} unavailable — {message}")
            if st.session_state.search_coverage_message:
                st.caption(st.session_state.search_coverage_message)
            show_partials = False
            if st.session_state.search_partial_results:
                show_partials = st.checkbox(
                    "Show best partial matches",
                    key="search_show_partials",
                )
            show_unknown = False
            if st.session_state.search_unknown_results:
                show_unknown = st.checkbox(
                    "Show coverage not yet verified",
                    key="search_show_unknown",
                )
            display_results = list(st.session_state.search_results)
            if show_partials:
                display_results.extend(st.session_state.search_partial_results)
            if show_unknown:
                display_results.extend(st.session_state.search_unknown_results)
            if st.session_state.search_query and not display_results and not st.session_state.search_failures and not st.session_state.search_coverage_message:
                st.caption("No matching series found.")
            coverage_active = st.session_state.search_coverage_start is not None and st.session_state.search_coverage_end is not None
            for candidate in display_results:
                identity = candidate_unique_key(candidate)
                left, right = st.columns([0.86, 0.14], vertical_alignment="center")
                with left:
                    coverage = _coverage_html(candidate) if coverage_active else ""
                    st.markdown(f'<div class="search-row"><div class="search-title">{html.escape(candidate.title)}</div><div class="meta-line">{_meta(candidate)}</div>{coverage}</div>', unsafe_allow_html=True)
                with right:
                    immediate = not candidate.requires_resolution
                    if immediate:
                        resolved_key = resolve_candidate(candidate).series_key
                        added = candidate_is_added(candidate, st.session_state.workspace)
                        if st.button("added" if added else "+ add", key=f"add:{identity}", width="stretch", disabled=added):
                            success, _ = _fetch_and_add(candidate, providers)
                            if success:
                                st.rerun()
                if immediate and resolved_key in st.session_state.search_unavailable:
                    st.caption(f"Unavailable — {st.session_state.search_unavailable[resolved_key]}")
                if candidate.requires_resolution:
                    with st.expander("resolve before adding"):
                        active = st.session_state.search_resolution_active.get(identity, False)
                        if not active:
                            if st.button("load resolution options", key=f"load:{identity}"):
                                st.session_state.search_resolution_active[identity] = True
                                st.rerun()
                        elif candidate.provider == "world_bank":
                            try:
                                countries = providers["World Bank"].countries()
                                labels = {f"{item['name']} ({item['id']})": item["id"] for item in countries}
                                selected_label = st.selectbox("Geography / economy", list(labels), key=f"geo:{identity}")
                                resolution = {"geography": labels[selected_label]}
                                resolved_key = resolve_candidate(candidate, resolution).series_key
                                added = candidate_is_added(candidate, st.session_state.workspace, resolution)
                                if st.button("added" if added else "add resolved series", key=f"resolve:{resolved_key}", disabled=added):
                                    success, _ = _fetch_and_add(candidate, providers, resolution)
                                    if success:
                                        st.rerun()
                                if resolved_key in st.session_state.search_unavailable:
                                    st.caption(f"Unavailable for {selected_label} — {st.session_state.search_unavailable[resolved_key]}")
                            except Exception as exc:
                                st.caption(f"Unavailable — {redact_secrets(str(exc))}")
                        elif candidate.provider == "eia":
                            try:
                                route = candidate.metadata.get("route", "")
                                selections = {}
                                for facet in candidate.metadata.get("facets", []):
                                    facet_id = facet.get("id") if isinstance(facet, dict) else str(facet)
                                    values = providers["EIA"].facet_values(route, facet_id)
                                    options = {f"{v.get('name', v.get('id'))} ({v.get('id')})": v.get("id") for v in values}
                                    if options:
                                        label = st.selectbox(facet.get("description", facet_id) if isinstance(facet, dict) else facet_id, list(options), key=f"eia:{identity}:{facet_id}")
                                        selections[facet_id] = options[label]
                                frequencies = candidate.metadata.get("frequencies", [])
                                frequency_options = [f.get("id") if isinstance(f, dict) else str(f) for f in frequencies]
                                frequency = st.selectbox("Frequency", frequency_options, key=f"eia-frequency:{identity}") if frequency_options else None
                                resolution = {"facets": selections, "frequency": frequency}
                                value_field = candidate.metadata.get("value_field")
                                resolved_key = resolve_candidate(candidate, resolution, value_field).series_key
                                added = candidate_is_added(candidate, st.session_state.workspace, resolution, value_field)
                                if st.button("added" if added else "add resolved series", key=f"resolve:{resolved_key}", disabled=added):
                                    success, _ = _fetch_and_add(candidate, providers, resolution, value_field)
                                    if success:
                                        st.rerun()
                                if resolved_key in st.session_state.search_unavailable:
                                    st.caption(f"Unavailable for this resolution — {st.session_state.search_unavailable[resolved_key]}")
                            except Exception as exc:
                                st.caption(f"Unavailable — {redact_secrets(str(exc))}")
                st.markdown("<hr>", unsafe_allow_html=True)
