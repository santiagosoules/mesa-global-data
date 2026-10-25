import os
import unittest
from datetime import datetime, timezone

from mesa_global_data.connectors import cftc, h41, nyfed, ofr, treasury


RUN_NETWORK = os.environ.get("RUN_NETWORK_TESTS") == "1"


@unittest.skipUnless(RUN_NETWORK, "set RUN_NETWORK_TESTS=1 to query official sources")
class OfficialSourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def test_treasury_current_year(self):
        observations = treasury.collect(2026, self.retrieved_at)
        latest = {(item.sensor_id, item.as_of): item.value for item in observations}
        self.assertIn(("us10y_yield", "2026-10-23"), latest)
        self.assertEqual(latest[("us10y_yield", "2026-10-23")], 5.0)

    def test_federal_reserve_h41(self):
        observations = h41.collect(self.retrieved_at)
        self.assertEqual(
            {item.sensor_id for item in observations},
            {"fed_balance_assets", "tga_balance", "bank_reserves"},
        )

    def test_new_york_fed_on_rrp(self):
        observations = nyfed.collect(self.retrieved_at, "2026-10-01")
        latest = max(observations, key=lambda item: item.as_of)
        self.assertEqual(latest.sensor_id, "on_rrp_usage")
        self.assertEqual(latest.value, 0.2)

    def test_ofr_fsi(self):
        observations = ofr.collect(self.retrieved_at)
        self.assertEqual({item.sensor_id for item in observations}, {"ofr_fsi_credit", "ofr_fsi_us"})

    def test_cftc_official_archive(self):
        observations = cftc.collect(2026, self.retrieved_at)
        target = next(
            item for item in observations
            if item.sensor_id == "nq_cot_leveraged_funds_net" and item.as_of == "2026-10-20"
        )
        self.assertEqual(target.value, -7688.0)
        reconciliation = target.metadata["reconciliation"]
        self.assertEqual(reconciliation["mnq"]["net"], -86381)
        self.assertEqual(reconciliation["official_consolidated"]["weekly_change_nq_equivalent"], 14203)


if __name__ == "__main__":
    unittest.main()

