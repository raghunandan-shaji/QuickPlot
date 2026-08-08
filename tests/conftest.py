from __future__ import annotations

import pandas as pd

from series_lab.models import FetchedSeries, WorkspaceSeries


def make_workspace(key, values, dates, frequency="Daily", transform="level", aggregation=None):
    index = pd.to_datetime(dates)
    series = pd.Series(values, index=index, name=key, dtype=float)
    raw = pd.DataFrame({"date": index, "value": values})
    fetched = FetchedSeries(
        key, "Test", key, raw, series,
        {"provider_id": key, "frequency": frequency, "units": "units", "selected_value_field": "value"},
        {"source": "test"},
    )
    return WorkspaceSeries(fetched, transform=transform, aggregation=aggregation)
