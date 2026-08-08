from __future__ import annotations

from series_lab.config import Settings, get_settings

from .bls import BlsProvider
from .eia import EiaProvider
from .fred import FredProvider
from .world_bank import WorldBankProvider
from .yahoo import YahooProvider


def build_provider_registry(settings: Settings | None = None):
    settings = settings or get_settings()
    return {
        "FRED": FredProvider(settings.fred_api_key),
        "Yahoo": YahooProvider(),
        "BLS": BlsProvider(settings.bls_api_key),
        "EIA": EiaProvider(settings.eia_api_key),
        "World Bank": WorldBankProvider(),
    }
