import pandas as pd
import pytest

from conftest import make_workspace
from series_lab.exceptions import SeriesResolutionError
from series_lab.models import SeriesCandidate, resolve_candidate
from series_lab.state import add_to_workspace, initialize_state, remove_from_workspace


def test_world_bank_requires_explicit_geography():
    candidate = SeriesCandidate("world_bank", "NY.GDP.MKTP.CD", "GDP", requires_resolution=True)
    with pytest.raises(SeriesResolutionError, match="additional selections"):
        resolve_candidate(candidate)
    resolved = resolve_candidate(candidate, {"geography": "USA"})
    assert resolved.series_key == "world_bank:USA:NY.GDP.MKTP.CD"


def test_series_keys_and_raw_copy_are_independent():
    candidate = SeriesCandidate("fred", "GDP", "GDP")
    assert resolve_candidate(candidate).series_key == "fred:GDP"
    item = make_workspace("fred:GDP", [1, 2], pd.date_range("2024-01-01", periods=2))
    copied = item.fetched.raw_copy()
    copied.iloc[0, copied.columns.get_loc("value")] = 99
    assert item.fetched.raw_frame.iloc[0]["value"] == 1


def test_workspace_state_add_remove_and_target_cleanup():
    state = {}
    initialize_state(state)
    item = make_workspace("fred:GDP", [1, 2], pd.date_range("2024-01-01", periods=2))
    add_to_workspace(state, item)
    state["target_series_key"] = item.series_key
    assert item.series_key in state["workspace"]
    remove_from_workspace(state, item.series_key)
    assert not state["workspace"]
    assert state["target_series_key"] is None
