from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .exporter import SCHEMA_VERSION
from .models import Observation
from .sensors import SENSORS
from .storage import Storage


POINT_FIELDS = {"as_of", "value", "publication_date", "retrieved_at"}
PROVENANCE_FIELDS = {
    "source", "source_identifier", "source_url", "unit", "instrument", "frequency",
    "quality", "data_kind", "latency", "access", "status", "methodology",
}


def bootstrap_from_bundle(storage: Storage, bundle_path: str) -> Dict[str, Any]:
    path = Path(bundle_path)
    if not path.exists():
        return {"status": "empty", "observations_inserted": 0, "analyses_restored": 0}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported bundle schema: {}".format(payload.get("schema_version")))
    sensors = payload.get("sensors")
    if not isinstance(sensors, dict) or set(sensors) != set(SENSORS):
        raise ValueError("Bundle sensor set does not match configured public sensors")

    observations = []
    for sensor_id, sensor_payload in sensors.items():
        provenance = sensor_payload.get("provenance")
        if not isinstance(provenance, dict):
            if sensor_payload.get("series"):
                raise ValueError("Bundle provenance missing for {}".format(sensor_id))
            continue
        missing_provenance = PROVENANCE_FIELDS - set(provenance)
        if missing_provenance:
            raise ValueError("Bundle provenance for {} is missing {}".format(sensor_id, sorted(missing_provenance)))
        latest = sensor_payload.get("latest") or {}
        for point in sensor_payload.get("series", []):
            missing = POINT_FIELDS - set(point)
            if missing:
                raise ValueError("Bundle point for {} is missing {}".format(sensor_id, sorted(missing)))
            metadata = point.get("metadata")
            if metadata is None and point["as_of"] == latest.get("as_of"):
                metadata = latest.get("metadata", {})
            observations.append(Observation(
                sensor_id=sensor_id,
                value=point["value"],
                as_of=point["as_of"],
                publication_date=point["publication_date"],
                retrieved_at=point["retrieved_at"],
                metadata=metadata or {},
                **{key: provenance[key] for key in PROVENANCE_FIELDS},
            ))
    inserted = storage.insert_observations(observations)

    restored_analyses = 0
    for analysis in payload.get("analyses", []):
        storage.save_analysis(analysis)
        restored_analyses += 1
    for source in payload.get("sources", []):
        storage.set_source_health(
            source["source_identifier"], source["source"], source["checked_at"],
            source["status"], "restored from public bundle",
        )
    return {
        "status": "ok",
        "observations_seen": len(observations),
        "observations_inserted": inserted,
        "analyses_restored": restored_analyses,
    }
