from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List

from ..http import fetch
from ..models import Observation
from ..sensors import SENSORS


NOMINAL_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data=daily_treasury_yield_curve&field_tdr_date_value={year}"
)
REAL_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data=daily_treasury_real_yield_curve&field_tdr_date_value={year}"
)
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
}


def _properties(root: ET.Element) -> List[Dict[str, str]]:
    result = []
    for node in root.findall("a:entry/a:content/m:properties", NS):
        values: Dict[str, str] = {}
        for child in list(node):
            key = child.tag.split("}")[-1]
            values[key] = (child.text or "").strip()
        result.append(values)
    return result


def _date(value: str) -> str:
    return value[:10]


def collect(year: int, retrieved_at: str) -> List[Observation]:
    observations: List[Observation] = []
    mappings = [
        (NOMINAL_URL.format(year=year), {"BC_2YEAR": "us2y_yield", "BC_10YEAR": "us10y_yield"}),
        (REAL_URL.format(year=year), {"TC_10YEAR": "us10y_real_yield"}),
    ]
    for url, field_map in mappings:
        body, _ = fetch(url)
        root = ET.fromstring(body)
        for row in _properties(root):
            as_of = _date(row["NEW_DATE"])
            for field, sensor_id in field_map.items():
                raw = row.get(field, "")
                if not raw:
                    continue
                sensor = SENSORS[sensor_id]
                observations.append(
                    Observation(
                        sensor_id=sensor_id,
                        value=float(raw),
                        unit=sensor.unit,
                        source="U.S. Department of the Treasury",
                        source_identifier="treasury:{}".format(field),
                        source_url=url,
                        as_of=as_of,
                        publication_date=as_of,
                        retrieved_at=retrieved_at,
                        instrument=sensor.instrument,
                        frequency=sensor.frequency,
                        quality="official_primary",
                        data_kind="observed",
                        latency="publication",
                        methodology="Official Treasury daily par yield curve field {}.".format(field),
                        metadata={"treasury_field": field, "publication_date_method": "effective_date"},
                    )
                )
    return observations

