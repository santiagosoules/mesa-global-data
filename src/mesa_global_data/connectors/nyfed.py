from __future__ import annotations

import json
from datetime import date, timedelta
from typing import List, Optional
from urllib.parse import urlencode

from ..http import fetch
from ..models import Observation
from ..sensors import SENSORS


BASE_URL = "https://markets.newyorkfed.org/api/rp/results/search.json"


def collect(retrieved_at: str, start_date: Optional[str] = None) -> List[Observation]:
    end_date = date.fromisoformat(retrieved_at[:10])
    start = start_date or (end_date - timedelta(days=400)).isoformat()
    url = "{}?{}".format(BASE_URL, urlencode({
        "startDate": start,
        "endDate": end_date.isoformat(),
        "operationTypes": "Reverse Repo",
        "method": "fixed",
        "term": "overnight",
    }))
    body, _ = fetch(url)
    payload = json.loads(body.decode("utf-8"))
    operations = payload.get("repo", {}).get("operations", [])
    sensor = SENSORS["on_rrp_usage"]
    observations: List[Observation] = []
    for operation in operations:
        if operation.get("operationType") != "Reverse Repo":
            continue
        as_of = str(operation["operationDate"])
        observations.append(Observation(
            sensor_id=sensor.id,
            value=float(operation["totalAmtAccepted"]) / 1_000_000_000.0,
            unit=sensor.unit,
            source="Federal Reserve Bank of New York",
            source_identifier="nyfed_on_rrp:{}".format(operation["operationId"]),
            source_url=url,
            as_of=as_of,
            publication_date=as_of,
            retrieved_at=retrieved_at,
            instrument=sensor.instrument,
            frequency=sensor.frequency,
            quality="official_primary",
            data_kind="observed",
            latency="publication",
            methodology="Accepted amount for official fixed-rate overnight reverse repo operation; USD converted to billions.",
            metadata={
                "operation_id": operation["operationId"],
                "last_updated": operation.get("lastUpdated"),
                "unit_conversion": "USD / 1,000,000,000",
                "publication_date_method": "operation_date",
            },
        ))
    if not observations:
        raise ValueError("New York Fed API returned no overnight reverse repo operations")
    return observations
