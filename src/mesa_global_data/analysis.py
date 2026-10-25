from __future__ import annotations

from typing import Any, Dict

from .storage import Storage


def cot_reconciliation_analysis(storage: Storage, created_at: str) -> Dict[str, Any]:
    observation = storage.latest("nq_cot_leveraged_funds_net")
    if observation is None:
        raise ValueError("COT leveraged-funds observation unavailable")
    reconciliation = observation["metadata"]["reconciliation"]
    nq = reconciliation["nq"]
    mnq = reconciliation["mnq"]
    derived = reconciliation["derived_consolidated"]
    official = reconciliation["official_consolidated"]
    return {
        "id": "cot_nq_mnq_reconciliation_{}".format(observation["as_of"]),
        "mode": "weekly",
        "as_of": observation["as_of"],
        "created_at": created_at,
        "title": "CFTC NQ/MNQ leveraged funds reconciliation",
        "evidence_level": "derived_from_official_observations",
        "payload": {
            "corrected_conclusion": (
                "Leveraged Funds were net short on a consolidated, NQ-equivalent basis; "
                "the NQ-only +950 net omitted the MNQ -86,381 net."
            ),
            "nq_net_contracts": nq["net"],
            "mnq_net_contracts": mnq["net"],
            "mnq_net_nq_equivalent": mnq["net_nq_equivalent"],
            "derived_consolidated_net_nq_equivalent": derived["net_nq_equivalent"],
            "official_consolidated_net_nq_equivalent": official["net_nq_equivalent"],
            "derived_weekly_change_nq_equivalent": derived["weekly_change_nq_equivalent"],
            "official_weekly_change_nq_equivalent": official["weekly_change_nq_equivalent"],
            "rounding_note": "CFTC 20974+ is reported in whole NQ-equivalent contracts.",
            "methodology": reconciliation["normalization"],
            "source_url": observation["source_url"],
            "source_codes": observation["metadata"]["contract_codes"],
        },
    }

