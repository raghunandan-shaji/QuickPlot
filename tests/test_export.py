import io
import zipfile

import pandas as pd

from conftest import make_workspace
from series_lab.models import PrepareConfig
from series_lab.services.export import research_bundle
from series_lab.services.harmonize import harmonize


def test_bundle_contents_and_secret_redaction(monkeypatch):
    secret = "NEVER-EXPORT-THIS-KEY"
    monkeypatch.setenv("FRED_API_KEY", secret)
    item = make_workspace("fred:X", [1, 2, 3], pd.date_range("2024-01-01", periods=3))
    item.fetched.metadata["unsafe_url"] = f"https://example.test?api_key={secret}"
    config = PrepareConfig(frequency="daily")
    prepared = harmonize([item], config)
    bundle = research_bundle([item], config, prepared)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = archive.namelist()
        for expected in ("experiment.yaml", "metadata.json", "processed/harmonized.csv", "processed/analysis.csv"):
            assert any(name.endswith(expected) for name in names)
        manifest = archive.read("quickplot-export/experiment.yaml").decode()
        assert "app_name: QuickPlot" in manifest
        assert any("/raw/" in name for name in names)
        all_bytes = b"".join(archive.read(name) for name in names)
        assert secret.encode() not in all_bytes
