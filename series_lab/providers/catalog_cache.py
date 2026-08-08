from __future__ import annotations

import streamlit as st

from series_lab.config import REQUEST_TIMEOUT

from .base import resilient_session


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_catalog_text(url: str) -> str:
    # The official BLS download host currently blocks Requests' TLS signature.
    # curl_cffi's browser impersonation reaches the same documented public file.
    from curl_cffi import requests as curl_requests

    response = curl_requests.get(url, impersonate="chrome", timeout=REQUEST_TIMEOUT[1])
    response.raise_for_status()
    return response.text


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_world_bank_records(base_url: str, resource: str) -> list[dict]:
    session = resilient_session()
    first = session.get(
        f"{base_url}/{resource}",
        params={"format": "json", "per_page": 1000, "page": 1},
        timeout=REQUEST_TIMEOUT,
    )
    first.raise_for_status()
    payload = first.json()
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    records = list(payload[1] or [])
    pages = int(payload[0].get("pages", 1))
    for page in range(2, pages + 1):
        response = session.get(
            f"{base_url}/{resource}",
            params={"format": "json", "per_page": 1000, "page": page},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        records.extend(response.json()[1] or [])
    return records
