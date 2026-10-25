from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .sensors import SENSORS
from .storage import Storage


RANGES = {
    "us2y_yield": (-5.0, 25.0),
    "us10y_yield": (-5.0, 25.0),
    "us10y_real_yield": (-10.0, 20.0),
    "fed_balance_assets": (0.0, 20_000_000.0),
    "tga_balance": (0.0, 5_000_000.0),
    "on_rrp_usage": (0.0, 5_000.0),
    "bank_reserves": (0.0, 10_000_000.0),
    "ofr_fsi_credit": (-20.0, 20.0),
    "ofr_fsi_us": (-20.0, 20.0),
    "nq_cot_leveraged_funds_net": (-10_000_000.0, 10_000_000.0),
    "nq_cot_asset_manager_net": (-10_000_000.0, 10_000_000.0),
    "nq_cot_open_interest": (0.0, 10_000_000.0),
}


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def validate_observation(observation: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    required = [
        "sensor_id", "unit", "source", "source_identifier", "source_url", "as_of",
        "publication_date", "retrieved_at", "instrument", "frequency", "quality",
        "data_kind", "latency", "access", "status",
    ]
    for field in required:
        if observation.get(field) in {None, ""}:
            issues.append({"type": "missing_field", "sensor_id": observation.get("sensor_id", "unknown"), "detail": field})
    sensor_id = observation.get("sensor_id")
    if sensor_id not in SENSORS:
        issues.append({"type": "unknown_sensor", "sensor_id": str(sensor_id), "detail": "not configured"})
        return issues
    if observation.get("unit") != SENSORS[sensor_id].unit:
        issues.append({"type": "wrong_unit", "sensor_id": sensor_id, "detail": str(observation.get("unit"))})
    value = observation.get("value")
    if observation.get("status") == "ok":
        if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            issues.append({"type": "invalid_value", "sensor_id": sensor_id, "detail": str(value)})
        elif sensor_id in RANGES:
            low, high = RANGES[sensor_id]
            if not low <= float(value) <= high:
                issues.append({"type": "out_of_range", "sensor_id": sensor_id, "detail": str(value)})
    try:
        if observation.get("publication_date") and _day(observation["publication_date"]) < _day(observation["as_of"]):
            issues.append({"type": "publication_before_effective", "sensor_id": sensor_id, "detail": observation["publication_date"]})
        if _day(observation["retrieved_at"]) < _day(observation["as_of"]):
            issues.append({"type": "retrieval_before_effective", "sensor_id": sensor_id, "detail": observation["retrieved_at"]})
    except (TypeError, ValueError) as exc:
        issues.append({"type": "invalid_date", "sensor_id": sensor_id, "detail": str(exc)})
    if not str(observation.get("source_url", "")).startswith("https://"):
        issues.append({"type": "invalid_source_url", "sensor_id": sensor_id, "detail": str(observation.get("source_url"))})
    return issues


def validate_storage(storage: Storage, reference_date: Optional[str] = None) -> Dict[str, Any]:
    reference = _day(reference_date) if reference_date else datetime.utcnow().date()
    issues: List[Dict[str, str]] = []
    coverage = storage.coverage()
    for row in coverage:
        if not row["observation_count"]:
            issues.append({"type": "missing_sensor", "sensor_id": row["id"], "detail": "no observations"})
            continue
        latest = storage.latest(row["id"])
        if latest is None:
            continue
        issues.extend(validate_observation(latest))
        age = (reference - _day(latest["as_of"])).days
        if age > int(row["max_age_days"]):
            issues.append({"type": "stale", "sensor_id": row["id"], "detail": "{} days".format(age)})

    for sensor_id in (
        "nq_cot_leveraged_funds_net", "nq_cot_asset_manager_net", "nq_cot_open_interest"
    ):
        latest = storage.latest(sensor_id)
        if latest is None:
            continue
        reconciliation = latest["metadata"].get("reconciliation", {})
        if abs(float(reconciliation.get("rounding_discrepancy", 999))) > 1.0:
            issues.append({"type": "cot_discrepancy", "sensor_id": sensor_id, "detail": "net/open interest"})
        if abs(float(reconciliation.get("weekly_change_rounding_discrepancy", 999))) > 1.0:
            issues.append({"type": "cot_discrepancy", "sensor_id": sensor_id, "detail": "weekly change"})

    blocking_types = {
        "missing_sensor", "invalid_value", "out_of_range", "wrong_unit", "invalid_date",
        "cot_discrepancy",
    }
    blocking = [issue for issue in issues if issue["type"] in blocking_types]
    return {
        "status": "ok" if not blocking else "error",
        "sensor_count": len(SENSORS),
        "connected_count": sum(1 for row in coverage if row["observation_count"]),
        "issue_count": len(issues),
        "blocking_issue_count": len(blocking),
        "issues": issues,
    }

