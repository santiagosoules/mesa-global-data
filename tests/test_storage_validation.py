import tempfile
import unittest
from pathlib import Path

from mesa_global_data.models import Observation
from mesa_global_data.sensors import SENSORS
from mesa_global_data.storage import Storage
from mesa_global_data.validation import validate_storage


VALUES = {
    "us2y_yield": 4.69,
    "us10y_yield": 5.00,
    "us10y_real_yield": 2.66,
    "fed_balance_assets": 6753604,
    "tga_balance": 945153,
    "on_rrp_usage": 0.2,
    "bank_reserves": 2969522,
    "ofr_fsi_credit": -0.92,
    "ofr_fsi_us": -1.15,
    "nq_cot_leveraged_funds_net": -7688,
    "nq_cot_asset_manager_net": 78767,
    "nq_cot_open_interest": 285882,
}


class StorageValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.storage = Storage(str(Path(self.directory.name) / "test.sqlite"))

    def tearDown(self):
        self.storage.close()
        self.directory.cleanup()

    def populate(self, omit=None, stale=None, cot_discrepancy=0.1):
        observations = []
        for sensor_id, sensor in SENSORS.items():
            if sensor_id == omit:
                continue
            if sensor_id.startswith("nq_cot_"):
                as_of, publication = "2026-10-20", "2026-10-23"
                metadata = {
                    "reconciliation": {
                        "rounding_discrepancy": cot_discrepancy,
                        "weekly_change_rounding_discrepancy": 0.3,
                    }
                }
                quality = "official_primary_reconciled"
                source_identifier = "cftc:20974+:{}".format(sensor_id)
            elif sensor.frequency == "weekly":
                as_of, publication = "2026-10-21", "2026-10-22"
                metadata = {}
                quality = "official_primary"
                source_identifier = "h41:{}".format(sensor_id)
            else:
                as_of, publication = "2026-10-23", "2026-10-23"
                metadata = {}
                quality = "official_primary"
                source_identifier = "official:{}".format(sensor_id)
            if sensor_id == stale:
                as_of, publication = "2026-09-01", "2026-09-01"
            observations.append(Observation(
                sensor_id=sensor_id,
                value=float(VALUES[sensor_id]),
                unit=sensor.unit,
                source="Official test fixture",
                source_identifier=source_identifier,
                source_url="https://example.gov/source",
                as_of=as_of,
                publication_date=publication,
                retrieved_at="2026-10-25T07:00:00+00:00",
                instrument=sensor.instrument,
                frequency=sensor.frequency,
                quality=quality,
                metadata=metadata,
            ))
        self.storage.insert_observations(observations)

    def test_complete_current_storage_is_valid(self):
        self.populate()
        self.assertEqual(validate_storage(self.storage, "2026-10-25")["status"], "ok")

    def test_missing_sensor_detected(self):
        self.populate(omit="ofr_fsi_us")
        issues = validate_storage(self.storage, "2026-10-25")["issues"]
        self.assertTrue(any(i["type"] == "missing_sensor" and i["sensor_id"] == "ofr_fsi_us" for i in issues))

    def test_stale_sensor_detected(self):
        self.populate(stale="on_rrp_usage")
        issues = validate_storage(self.storage, "2026-10-25")["issues"]
        self.assertTrue(any(i["type"] == "stale" and i["sensor_id"] == "on_rrp_usage" for i in issues))

    def test_cot_discrepancy_detected(self):
        self.populate(cot_discrepancy=2.0)
        issues = validate_storage(self.storage, "2026-10-25")["issues"]
        self.assertTrue(any(i["type"] == "cot_discrepancy" for i in issues))


if __name__ == "__main__":
    unittest.main()

