from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


APP_NAME = "QuickPlot"
APP_VERSION = "1.0.0"
REQUEST_TIMEOUT = (4, 16)


@dataclass(frozen=True)
class Settings:
    fred_api_key: str = ""
    eia_api_key: str = ""
    bls_api_key: str = ""


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


def get_settings() -> Settings:
    return Settings(
        fred_api_key=_secret("FRED_API_KEY"),
        eia_api_key=_secret("EIA_API_KEY"),
        bls_api_key=_secret("BLS_API_KEY"),
    )


def redact_secrets(value: Any, secrets: Settings | None = None) -> Any:
    """Recursively remove configured API key text from serializable values."""
    configured = get_settings() if secrets is None else secrets
    keys = [key for key in configured.__dict__.values() if key]
    if isinstance(value, str):
        result = value
        for key in keys:
            result = result.replace(key, "[REDACTED]")
        return result
    if isinstance(value, dict):
        return {k: redact_secrets(v, configured) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secrets(v, configured) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(v, configured) for v in value)
    return value
