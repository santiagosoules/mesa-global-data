from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from .sensors import SENSORS
from .status import sensor_update_status
from .storage import Storage
from .validation import validate_storage


SCHEMA_VERSION = "1.1.0"


def _public_observation(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {key: value for key, value in row.items() if key not in {"id", "revision"}}


def _public_source(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_identifier": row["source_identifier"],
        "source": row["source"],
        "checked_at": row["checked_at"],
        "status": row["status"],
    }


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _site_sensor_payload(
    storage: Storage, sensor_id: str, generated_at: str,
    source_health: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the compact, revision-aware history consumed by Mesa Global INTEL."""
    rows = storage.observations([sensor_id], limit_per_sensor=1_000_000, primary_only=True)
    by_date: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if row["status"] != "ok" or row["value"] is None:
            continue
        # Storage returns newest revision first, so the first row wins for each date.
        by_date.setdefault(row["as_of"], row)
    ordered = [by_date[as_of] for as_of in sorted(by_date)]
    latest = ordered[-1] if ordered else None
    previous = ordered[-2] if len(ordered) > 1 else None
    delta = (
        float(latest["value"]) - float(previous["value"])
        if latest is not None and previous is not None else None
    )
    return {
        "definition": asdict(SENSORS[sensor_id]),
        "provenance": (
            {
                key: latest[key]
                for key in (
                    "source", "source_identifier", "source_url", "unit", "instrument",
                    "frequency", "quality", "data_kind", "latency", "access", "status",
                    "methodology",
                )
            }
            if latest else None
        ),
        "latest": _public_observation(latest),
        "previous": _public_observation(previous),
        "delta": delta,
        "delta_period": "daily" if SENSORS[sensor_id].frequency == "daily" else "weekly",
        "history_start": ordered[0]["as_of"] if ordered else None,
        "history_end": latest["as_of"] if latest else None,
        "series": [
            {
                "as_of": row["as_of"],
                "value": row["value"],
                "publication_date": row["publication_date"],
                "retrieved_at": row["retrieved_at"],
                **(
                    {"metadata": row["metadata"]}
                    if sensor_id.startswith("nq_cot_") else {}
                ),
            }
            for row in ordered
        ],
        "update_status": sensor_update_status(
            sensor_id, latest, generated_at, source_health
        ),
    }


def export_all(storage: Storage, output_dir: str, generated_at: str) -> Dict[str, str]:
    directory = Path(output_dir)
    source_health_rows = storage.source_health()
    source_health = {row["source_identifier"]: row for row in source_health_rows}
    latest = {sensor_id: _public_observation(storage.latest(sensor_id)) for sensor_id in SENSORS}
    coverage = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "sensors": storage.coverage(),
        "sources": [_public_source(row) for row in source_health_rows],
    }
    analyses = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "analyses": storage.analyses(),
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "timezone": "UTC",
        "site_target": "https://mesa-global.santiago-soules.chatgpt.site/",
        "publication_status": "public_static_data",
        "observations": latest,
        "coverage": coverage["sensors"],
        "validation": validate_storage(storage, generated_at),
        "analyses": analyses["analyses"],
    }
    site_bundle = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "timezone": "UTC",
        "delivery": {
            "mode": "bundled_snapshot",
            "real_time": False,
            "update_contract": "MESA_INTEL_DATA_URL",
            "refresh_model": "scheduled_static_bundle",
            "profiles": {
                "daily": ["treasury", "nyfed", "ofr"],
                "h41": ["h41"],
                "weekly": ["cftc"],
            },
        },
        "sensors": {
            sensor_id: _site_sensor_payload(storage, sensor_id, generated_at, source_health)
            for sensor_id in SENSORS
        },
        "coverage": coverage["sensors"],
        "sources": coverage["sources"],
        "validation": validate_storage(storage, generated_at),
        "analyses": analyses["analyses"],
    }
    paths = {
        "latest": str(directory / "latest.json"),
        "coverage": str(directory / "coverage.json"),
        "analyses": str(directory / "analyses.json"),
        "snapshot": str(directory / "market_snapshot.json"),
        "site_bundle": str(directory / "site_bundle.json"),
    }
    _write(Path(paths["latest"]), {"schema_version": SCHEMA_VERSION, "generated_at": generated_at, "observations": latest})
    _write(Path(paths["coverage"]), coverage)
    _write(Path(paths["analyses"]), analyses)
    _write(Path(paths["snapshot"]), snapshot)
    _write(Path(paths["site_bundle"]), site_bundle)
    return paths

