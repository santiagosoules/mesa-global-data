from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Tuple

from ..http import fetch
from ..models import Observation
from ..sensors import SENSORS


URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
NQ_CODE = "209742"
MNQ_CODE = "209747"
CONSOLIDATED_CODE = "20974+"
MNQ_TO_NQ = 0.1  # $2/point divided by $20/point


class COTDiscrepancyError(ValueError):
    pass


def _number(row: Dict[str, str], field: str) -> int:
    return int(row[field].strip())


def _friday_after_tuesday(as_of: str) -> str:
    day = date.fromisoformat(as_of)
    return (day + timedelta(days=(4 - day.weekday()) % 7)).isoformat()


def _category_fields(category: str) -> Tuple[str, str, str, str]:
    if category == "leveraged_funds":
        return (
            "Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All",
            "Change_in_Lev_Money_Long_All", "Change_in_Lev_Money_Short_All",
        )
    if category == "asset_manager":
        return (
            "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All",
            "Change_in_Asset_Mgr_Long_All", "Change_in_Asset_Mgr_Short_All",
        )
    raise ValueError("Unsupported COT category: {}".format(category))


def reconcile_category(
    nq: Dict[str, str], mnq: Dict[str, str], consolidated: Dict[str, str], category: str,
    tolerance: float = 1.0,
) -> Dict[str, Any]:
    long_field, short_field, change_long_field, change_short_field = _category_fields(category)
    nq_long, nq_short = _number(nq, long_field), _number(nq, short_field)
    mnq_long, mnq_short = _number(mnq, long_field), _number(mnq, short_field)
    official_long, official_short = _number(consolidated, long_field), _number(consolidated, short_field)

    nq_net = nq_long - nq_short
    mnq_net = mnq_long - mnq_short
    derived_equivalent = nq_net + mnq_net * MNQ_TO_NQ
    official_net = official_long - official_short
    discrepancy = official_net - derived_equivalent

    nq_change_net = _number(nq, change_long_field) - _number(nq, change_short_field)
    mnq_change_net = _number(mnq, change_long_field) - _number(mnq, change_short_field)
    derived_change = nq_change_net + mnq_change_net * MNQ_TO_NQ
    official_change = _number(consolidated, change_long_field) - _number(consolidated, change_short_field)
    change_discrepancy = official_change - derived_change

    if abs(discrepancy) > tolerance or abs(change_discrepancy) > tolerance:
        raise COTDiscrepancyError(
            "CFTC consolidated discrepancy for {}: net={} change={}".format(
                category, discrepancy, change_discrepancy
            )
        )

    return {
        "category": category,
        "normalization": "NQ equivalent = NQ contracts + MNQ contracts * (USD 2/point / USD 20/point)",
        "mnq_to_nq_factor": MNQ_TO_NQ,
        "nq": {"long": nq_long, "short": nq_short, "net": nq_net, "change_net": nq_change_net},
        "mnq": {
            "long": mnq_long, "short": mnq_short, "net": mnq_net,
            "net_nq_equivalent": mnq_net * MNQ_TO_NQ,
            "change_net": mnq_change_net,
            "change_nq_equivalent": mnq_change_net * MNQ_TO_NQ,
        },
        "derived_consolidated": {
            "net_nq_equivalent": derived_equivalent,
            "weekly_change_nq_equivalent": derived_change,
        },
        "official_consolidated": {
            "long": official_long, "short": official_short, "net_nq_equivalent": official_net,
            "weekly_change_nq_equivalent": official_change,
        },
        "rounding_discrepancy": discrepancy,
        "weekly_change_rounding_discrepancy": change_discrepancy,
    }


def reconcile_open_interest(
    nq: Dict[str, str], mnq: Dict[str, str], consolidated: Dict[str, str], tolerance: float = 1.0
) -> Dict[str, Any]:
    nq_oi = _number(nq, "Open_Interest_All")
    mnq_oi = _number(mnq, "Open_Interest_All")
    official_oi = _number(consolidated, "Open_Interest_All")
    derived = nq_oi + mnq_oi * MNQ_TO_NQ
    nq_change = _number(nq, "Change_in_Open_Interest_All")
    mnq_change = _number(mnq, "Change_in_Open_Interest_All")
    official_change = _number(consolidated, "Change_in_Open_Interest_All")
    derived_change = nq_change + mnq_change * MNQ_TO_NQ
    if abs(official_oi - derived) > tolerance or abs(official_change - derived_change) > tolerance:
        raise COTDiscrepancyError("CFTC consolidated open-interest discrepancy")
    return {
        "normalization": "NQ equivalent = NQ contracts + MNQ contracts * 0.1",
        "mnq_to_nq_factor": MNQ_TO_NQ,
        "nq": {"open_interest": nq_oi, "weekly_change": nq_change},
        "mnq": {
            "open_interest": mnq_oi, "open_interest_nq_equivalent": mnq_oi * MNQ_TO_NQ,
            "weekly_change": mnq_change, "weekly_change_nq_equivalent": mnq_change * MNQ_TO_NQ,
        },
        "derived_consolidated": {"open_interest": derived, "weekly_change": derived_change},
        "official_consolidated": {"open_interest": official_oi, "weekly_change": official_change},
        "rounding_discrepancy": official_oi - derived,
        "weekly_change_rounding_discrepancy": official_change - derived_change,
    }


def _group_rows(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, Dict[str, str]]]:
    grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
    for row in rows:
        code = row["CFTC_Contract_Market_Code"].strip()
        if code not in {NQ_CODE, MNQ_CODE, CONSOLIDATED_CODE}:
            continue
        as_of = row["Report_Date_as_YYYY-MM-DD"].strip()
        grouped.setdefault(as_of, {})[code] = row
    return grouped


def collect(year: int, retrieved_at: str) -> List[Observation]:
    url = URL.format(year=year)
    body, headers = fetch(url)
    last_modified = headers.get("Last-Modified", "")
    latest_publication = None
    if last_modified:
        latest_publication = parsedate_to_datetime(last_modified).astimezone(timezone.utc).date().isoformat()
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")))
    grouped = _group_rows(rows)
    if not grouped:
        raise ValueError("CFTC archive did not contain the requested Nasdaq contract codes")
    latest_as_of = max(grouped)
    observations: List[Observation] = []
    for as_of in sorted(grouped):
        contracts = grouped[as_of]
        missing = {NQ_CODE, MNQ_CODE, CONSOLIDATED_CODE} - set(contracts)
        if missing:
            raise ValueError("Missing CFTC contract codes for {}: {}".format(as_of, sorted(missing)))
        nq, mnq, consolidated = contracts[NQ_CODE], contracts[MNQ_CODE], contracts[CONSOLIDATED_CODE]
        publication_date = latest_publication if as_of == latest_as_of and latest_publication else _friday_after_tuesday(as_of)
        common_metadata = {
            "cftc_report": "Traders in Financial Futures, Futures Only",
            "contract_codes": {"nq": NQ_CODE, "mnq": MNQ_CODE, "consolidated": CONSOLIDATED_CODE},
            "contract_multipliers_usd_per_point": {"nq": 20, "mnq": 2},
            "publication_date_method": "HTTP Last-Modified" if as_of == latest_as_of and latest_publication else "scheduled Friday after Tuesday",
        }
        for sensor_id, category in (
            ("nq_cot_leveraged_funds_net", "leveraged_funds"),
            ("nq_cot_asset_manager_net", "asset_manager"),
        ):
            reconciliation = reconcile_category(nq, mnq, consolidated, category)
            sensor = SENSORS[sensor_id]
            metadata = dict(common_metadata)
            metadata["reconciliation"] = reconciliation
            observations.append(
                Observation(
                    sensor_id=sensor_id,
                    value=float(reconciliation["official_consolidated"]["net_nq_equivalent"]),
                    unit=sensor.unit,
                    source="U.S. Commodity Futures Trading Commission",
                    source_identifier="cftc:{}:{}".format(CONSOLIDATED_CODE, category),
                    source_url=url,
                    as_of=as_of,
                    publication_date=publication_date,
                    retrieved_at=retrieved_at,
                    instrument=sensor.instrument,
                    frequency=sensor.frequency,
                    quality="official_primary_reconciled",
                    data_kind="derived",
                    latency="publication",
                    methodology=reconciliation["normalization"],
                    metadata=metadata,
                )
            )
        oi_reconciliation = reconcile_open_interest(nq, mnq, consolidated)
        sensor = SENSORS["nq_cot_open_interest"]
        metadata = dict(common_metadata)
        metadata["reconciliation"] = oi_reconciliation
        observations.append(
            Observation(
                sensor_id=sensor.id,
                value=float(oi_reconciliation["official_consolidated"]["open_interest"]),
                unit=sensor.unit,
                source="U.S. Commodity Futures Trading Commission",
                source_identifier="cftc:{}:open_interest".format(CONSOLIDATED_CODE),
                source_url=url,
                as_of=as_of,
                publication_date=publication_date,
                retrieved_at=retrieved_at,
                instrument=sensor.instrument,
                frequency=sensor.frequency,
                quality="official_primary_reconciled",
                data_kind="observed",
                latency="publication",
                methodology=oi_reconciliation["normalization"],
                metadata=metadata,
            )
        )
    return observations

