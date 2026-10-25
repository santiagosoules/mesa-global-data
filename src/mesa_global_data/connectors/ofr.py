from __future__ import annotations

import csv
import io
from typing import Dict, List

from ..http import fetch
from ..models import Observation
from ..sensors import SENSORS


URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"
COLUMNS: Dict[str, str] = {
    "Credit": "ofr_fsi_credit",
    "United States": "ofr_fsi_us",
}


def collect(retrieved_at: str) -> List[Observation]:
    body, _ = fetch(URL)
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    observations: List[Observation] = []
    for row in reader:
        as_of = (row.get("Date") or "").strip()
        if not as_of:
            continue
        for column, sensor_id in COLUMNS.items():
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            sensor = SENSORS[sensor_id]
            observations.append(Observation(
                sensor_id=sensor_id,
                value=float(raw),
                unit=sensor.unit,
                source="U.S. Office of Financial Research",
                source_identifier="ofr_fsi:{}".format(column.lower().replace(" ", "_")),
                source_url=URL,
                as_of=as_of,
                publication_date=as_of,
                retrieved_at=retrieved_at,
                instrument=sensor.instrument,
                frequency=sensor.frequency,
                quality="official_primary",
                data_kind="derived",
                latency="publication",
                methodology="Official OFR Financial Stress Index component contribution, measured in standard deviations.",
                metadata={
                    "ofr_fsi_column": column,
                    "publication_date_method": "dataset date",
                    "citation": "Office of Financial Research Financial Stress Index",
                },
            ))
    missing = set(COLUMNS.values()) - {item.sensor_id for item in observations}
    if missing:
        raise ValueError("OFR FSI response omitted configured sensors: {}".format(sorted(missing)))
    return observations
