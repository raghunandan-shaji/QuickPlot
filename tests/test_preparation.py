from collections import OrderedDict

import pandas as pd

from conftest import make_workspace
from series_lab.models import PrepareConfig
from series_lab.services.preparation import apply_aggregation_setting, apply_transform_setting
from series_lab.ui.prepare_section import _series_token


def workspace_pair():
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    first = make_workspace("first", [1, 2, 3, 4], dates)
    second = make_workspace("second", [2, 4, 6, 8], dates)
    return OrderedDict(((first.series_key, first), (second.series_key, second)))


def test_changing_one_series_transform_inline():
    workspace = workspace_pair()
    calls = []

    def build(items, config):
        calls.append(list(items))
        return "prepared"

    result = apply_transform_setting(
        workspace, "second", "z_score", PrepareConfig(frequency="daily"), harmonizer=build
    )
    assert result == "prepared"
    assert workspace["first"].transform == "level"
    assert workspace["second"].transform == "z_score"
    assert len(calls) == 1


def test_changing_one_series_aggregation_inline():
    workspace = workspace_pair()
    calls = []

    def build(items, config):
        calls.append(1)
        return "prepared"

    apply_aggregation_setting(
        workspace, "first", "mean", PrepareConfig(frequency="daily"), harmonizer=build
    )
    assert workspace["first"].aggregation == "mean"
    assert workspace["second"].aggregation is None
    assert len(calls) == 1


def test_apply_transform_to_all_rebuilds_once():
    workspace = workspace_pair()
    calls = []

    def build(items, config):
        calls.append([item.transform for item in items])
        return "prepared"

    result = apply_transform_setting(
        workspace,
        "first",
        "percent_change",
        PrepareConfig(frequency="daily"),
        apply_to_all=True,
        harmonizer=build,
    )
    assert result == "prepared"
    assert [item.transform for item in workspace.values()] == ["percent_change", "percent_change"]
    assert calls == [["percent_change", "percent_change"]]


def test_series_key_state_is_stable_when_workspace_order_changes():
    workspace = workspace_pair()
    original_token = _series_token("first")
    workspace.move_to_end("first")
    apply_transform_setting(
        workspace, "first", "log_level", PrepareConfig(frequency="daily"), harmonizer=lambda items, config: "prepared"
    )
    assert _series_token("first") == original_token
    assert workspace["first"].transform == "log_level"
    assert workspace["second"].transform == "level"


def test_bulk_transform_returns_rebuilt_analysis():
    workspace = workspace_pair()
    prepared = apply_transform_setting(
        workspace,
        "first",
        "z_score",
        PrepareConfig(frequency="daily"),
        apply_to_all=True,
    )
    assert list(prepared.analysis.columns) == ["first", "second"]
    assert prepared.analysis.notna().all().all()
    assert prepared.analysis.mean().abs().max() < 1e-12
