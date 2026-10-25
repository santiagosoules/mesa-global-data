import json
import unittest
from pathlib import Path

from mesa_global_data.connectors.cftc import (
    COTDiscrepancyError,
    reconcile_category,
    reconcile_open_interest,
)


FIXTURE = Path(__file__).parent / "fixtures" / "cftc_2026-10-20.json"


class COTReconciliationTests(unittest.TestCase):
    def setUp(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.nq = payload["contracts"]["209742"]
        self.mnq = payload["contracts"]["209747"]
        self.consolidated = payload["contracts"]["20974+"]

    def test_leveraged_funds_normalization_matches_official(self):
        result = reconcile_category(self.nq, self.mnq, self.consolidated, "leveraged_funds")
        self.assertEqual(result["nq"]["net"], 950)
        self.assertEqual(result["mnq"]["net"], -86381)
        self.assertAlmostEqual(result["mnq"]["net_nq_equivalent"], -8638.1)
        self.assertAlmostEqual(result["derived_consolidated"]["net_nq_equivalent"], -7688.1)
        self.assertEqual(result["official_consolidated"]["net_nq_equivalent"], -7688)
        self.assertAlmostEqual(result["derived_consolidated"]["weekly_change_nq_equivalent"], 14202.7)
        self.assertEqual(result["official_consolidated"]["weekly_change_nq_equivalent"], 14203)

    def test_asset_manager_normalization_matches_official(self):
        result = reconcile_category(self.nq, self.mnq, self.consolidated, "asset_manager")
        self.assertAlmostEqual(result["derived_consolidated"]["net_nq_equivalent"], 78766.8)
        self.assertEqual(result["official_consolidated"]["net_nq_equivalent"], 78767)
        self.assertAlmostEqual(result["derived_consolidated"]["weekly_change_nq_equivalent"], 2364.8)
        self.assertEqual(result["official_consolidated"]["weekly_change_nq_equivalent"], 2365)

    def test_open_interest_normalization_matches_official(self):
        result = reconcile_open_interest(self.nq, self.mnq, self.consolidated)
        self.assertAlmostEqual(result["derived_consolidated"]["open_interest"], 285882.2)
        self.assertEqual(result["official_consolidated"]["open_interest"], 285882)

    def test_discrepancy_is_rejected(self):
        corrupted = dict(self.consolidated)
        corrupted["Lev_Money_Positions_Long_All"] = "48063"
        with self.assertRaises(COTDiscrepancyError):
            reconcile_category(self.nq, self.mnq, corrupted, "leveraged_funds")


if __name__ == "__main__":
    unittest.main()

