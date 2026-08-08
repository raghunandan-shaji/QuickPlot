from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd
import yaml

from series_lab import __version__
from series_lab.config import APP_NAME, Settings, get_settings, redact_secrets
from series_lab.models import PrepareConfig, PreparedData, WorkspaceSeries
from series_lab.services.diagnostics import summary_statistics


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")[:120] or "series"


def analysis_csv(prepared: PreparedData) -> bytes:
    return prepared.analysis.to_csv(index_label="date").encode("utf-8")


def experiment_manifest(
    workspace: Iterable[WorkspaceSeries],
    config: PrepareConfig,
    prepared: PreparedData,
    target_series_key: str | None,
    secrets: Settings | None = None,
) -> dict:
    series_entries = []
    for item in workspace:
        meta = item.fetched.metadata
        series_entries.append(
            {
                "series_key": item.series_key,
                "provider": item.fetched.provider,
                "provider_id": meta.get("provider_id"),
                "title": item.fetched.title,
                "resolution_parameters": meta.get("resolution_parameters", {}),
                "original_frequency": meta.get("frequency"),
                "analysis_frequency": config.frequency,
                "units": meta.get("units"),
                "selected_value_field": meta.get("selected_value_field"),
                "transform": item.transform,
                "aggregation": item.aggregation or config.default_aggregation,
                "visible": item.visible,
            }
        )
    return redact_secrets(
        {
            "app_name": APP_NAME,
            "app_version": __version__,
            "export_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_series": target_series_key,
            "analysis_frequency": config.frequency,
            "date_coverage_policy": config.date_coverage,
            "missing_strategy": config.missing_strategy,
            "effective_analysis_dates": {"start": prepared.effective_start, "end": prepared.effective_end},
            "series": series_entries,
        },
        secrets,
    )


def metadata_document(workspace: Iterable[WorkspaceSeries], secrets: Settings | None = None) -> dict:
    return redact_secrets(
        {
            item.series_key: {
                "series_key": item.series_key,
                "provider": item.fetched.provider,
                "title": item.fetched.title,
                "metadata": item.fetched.metadata,
                "provenance": item.fetched.provenance,
                "fetched_at_utc": item.fetched.fetched_at_utc,
            }
            for item in workspace
        },
        secrets,
    )


def research_bundle(
    workspace: Iterable[WorkspaceSeries],
    config: PrepareConfig,
    prepared: PreparedData,
    target_series_key: str | None = None,
    chart_html: str | None = None,
) -> bytes:
    items = list(workspace)
    configured_secrets = get_settings()
    manifest = experiment_manifest(items, config, prepared, target_series_key, configured_secrets)
    metadata = metadata_document(items, configured_secrets)
    summary = summary_statistics(prepared.analysis).reset_index().to_dict("records")
    buffer = io.BytesIO()
    prefix = "quickplot-export"
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{prefix}/experiment.yaml", yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
        archive.writestr(f"{prefix}/metadata.json", json.dumps(metadata, indent=2, default=str))
        for item in items:
            filename = safe_filename(item.series_key) + ".csv"
            raw_csv = item.fetched.raw_copy().to_csv(index=True)
            archive.writestr(f"{prefix}/raw/{filename}", redact_secrets(raw_csv, configured_secrets))
        archive.writestr(f"{prefix}/processed/harmonized.csv", prepared.harmonized.to_csv(index_label="date"))
        archive.writestr(f"{prefix}/processed/analysis.csv", prepared.analysis.to_csv(index_label="date"))
        archive.writestr(f"{prefix}/diagnostics/summary.json", json.dumps(summary, indent=2, default=str))
        if chart_html:
            archive.writestr(f"{prefix}/figures/main_chart.html", redact_secrets(chart_html, configured_secrets))
    return buffer.getvalue()
