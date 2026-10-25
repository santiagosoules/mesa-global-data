from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from .sensors import SENSORS


SOURCE_BY_SENSOR = {
    sensor_id: (
        "cftc" if sensor_id.startswith("nq_cot_")
        else "treasury" if sensor_id in {"us2y_yield", "us10y_yield", "us10y_real_yield"}
        else "h41" if sensor_id in {"fed_balance_assets", "tga_balance", "bank_reserves"}
        else "nyfed" if sensor_id == "on_rrp_usage"
        else "ofr"
    )
    for sensor_id in SENSORS
}

LABELS = {
    "updated": "actualizado",
    "delayed": "retrasado",
    "source_error": "error de fuente",
    "unavailable": "no disponible",
}


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def sensor_update_status(
    sensor_id: str,
    latest: Optional[Dict[str, Any]],
    generated_at: str,
    source_health: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    definition = SENSORS[sensor_id]
    source_identifier = SOURCE_BY_SENSOR[sensor_id]
    health = source_health.get(source_identifier)
    if latest is None:
        status = "unavailable"
        age_days = None
    else:
        age_days = max(0, (_day(generated_at) - _day(latest["as_of"])).days)
        if health and health.get("status") == "error":
            status = "source_error"
        elif age_days > definition.max_age_days:
            status = "delayed"
        else:
            status = "updated"
    return {
        "status": status,
        "label": LABELS[status],
        "source_identifier": source_identifier,
        "checked_at": health.get("checked_at") if health else None,
        "detail": (
            "source check passed" if health and health.get("status") == "ok"
            else "source check failed" if health
            else "source has not been checked"
        ),
        "age_days": age_days,
        "max_age_days": definition.max_age_days,
        "last_valid_as_of": latest.get("as_of") if latest else None,
        "last_valid_retrieved_at": latest.get("retrieved_at") if latest else None,
    }
