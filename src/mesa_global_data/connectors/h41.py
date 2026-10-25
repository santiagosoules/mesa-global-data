from __future__ import annotations

import html
import re
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

from ..http import fetch
from ..models import Observation
from ..sensors import SENSORS


CATALOG_URL = "https://www.federalreserve.gov/datadownload/choose.aspx?rel=H41"
TABLE_URL = "https://www.federalreserve.gov/datadownload/DownloadTable.aspx"
SERIES = {
    "RESPPMA_N.WW": "fed_balance_assets",
    "RESPPLLDT_N.WW": "tga_balance",
    "RESH4R_N.WW": "bank_reserves",
}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: List[List[str]] = []
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._row is not None and self._cell is not None:
            self._row.append(html.unescape("".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _package_ids(body: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    pattern = re.compile(
        r'value="([^"]*series=([a-f0-9]+)[^"]*)"[^>]*>\s*'
        r'<label[^>]*>H\.4\.1 Statistical Release\s*-\s*Table\s+(1|5)(?=\s|\[)',
        re.IGNORECASE,
    )
    for _, series_hash, table_number in pattern.findall(body):
        result[table_number] = series_hash
    if set(result) != {"1", "5"}:
        raise ValueError("H.4.1 catalog did not expose table 1 and table 5 packages")
    return result


def _rows(body: bytes) -> List[List[str]]:
    parser = _TableParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    if not parser.rows:
        raise ValueError("H.4.1 download did not contain a data table")
    return parser.rows


def _publication_date(as_of: str) -> str:
    return (date.fromisoformat(as_of) + timedelta(days=1)).isoformat()


def collect(retrieved_at: str) -> List[Observation]:
    catalog, _ = fetch(CATALOG_URL)
    package_ids = _package_ids(catalog.decode("utf-8", errors="replace"))
    observations: List[Observation] = []
    for table_number in ("1", "5"):
        url = "{}?{}".format(
            TABLE_URL,
            urlencode({
                "filetype": "spreadsheetml",
                "from": "",
                "label": "include",
                "lastobs": "400",
                "layout": "seriescolumn",
                "rel": "H41",
                "series": package_ids[table_number],
                "to": "",
            }),
        )
        body, _ = fetch(url)
        rows = _rows(body)
        dates = rows[0][2:]
        for row in rows[1:]:
            if len(row) < 3 or row[0] not in SERIES:
                continue
            sensor_id = SERIES[row[0]]
            sensor = SENSORS[sensor_id]
            for as_of, raw in zip(dates, row[2:]):
                if not raw or raw in {"ND", "NA"}:
                    continue
                observations.append(Observation(
                    sensor_id=sensor_id,
                    value=float(raw.replace(",", "")),
                    unit=sensor.unit,
                    source="Board of Governors of the Federal Reserve System",
                    source_identifier="federal_reserve_h41:{}".format(row[0]),
                    source_url=url,
                    as_of=as_of,
                    publication_date=_publication_date(as_of),
                    retrieved_at=retrieved_at,
                    instrument=sensor.instrument,
                    frequency=sensor.frequency,
                    quality="official_primary",
                    data_kind="observed",
                    latency="publication",
                    methodology="Official H.4.1 Wednesday-level series from the Federal Reserve Data Download Program.",
                    metadata={
                        "h41_series_id": row[0],
                        "h41_table": table_number,
                        "publication_date_method": "scheduled Thursday after Wednesday level",
                    },
                ))
    missing = set(SERIES.values()) - {item.sensor_id for item in observations}
    if missing:
        raise ValueError("H.4.1 response omitted configured sensors: {}".format(sorted(missing)))
    return observations
