import numpy as np
import pandas as pd
import pytest

from series_lab.exceptions import TransformError
from series_lab.services.transforms import transform_series


@pytest.fixture
def values():
    return pd.Series([1.0, 2.0, 4.0, np.nan, 8.0], index=pd.date_range("2020-01-01", periods=5), name="x")


def test_all_transform_semantics(values):
    assert transform_series(values, "level").equals(values)
    assert transform_series(values, "log_level").iloc[2] == pytest.approx(np.log(4))
    assert transform_series(values, "first_difference").iloc[2] == 2
    assert transform_series(values, "log_difference").iloc[2] == pytest.approx(np.log(2))
    assert transform_series(values, "percent_change").iloc[2] == pytest.approx(100)
    z = transform_series(values, "z_score").dropna()
    assert z.mean() == pytest.approx(0)
    assert z.std(ddof=0) == pytest.approx(1)
    rebased = transform_series(values, "rebase_100")
    assert rebased.iloc[0] == 100
    assert rebased.iloc[2] == 400


def test_difference_does_not_bridge_nan(values):
    assert np.isnan(transform_series(values, "first_difference").iloc[4])
    assert np.isnan(transform_series(values, "percent_change").iloc[4])


def test_invalid_log_and_constant_zscore():
    with pytest.raises(TransformError, match="strictly positive"):
        transform_series(pd.Series([1, 0, -1], name="x"), "log_level")
    with pytest.raises(TransformError, match="constant"):
        transform_series(pd.Series([3, 3, np.nan], name="x"), "z_score")


def test_rebase_uses_first_valid_prepared_observation():
    series = pd.Series([np.nan, 5, 10], name="x")
    assert transform_series(series, "rebase_100").tolist()[1:] == [100, 200]
