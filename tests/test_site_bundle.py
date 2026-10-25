import json
import tempfile
import unittest
from pathlib import Path

from mesa_global_data.exporter import export_all
from mesa_global_data.models import Observation
from mesa_global_data.storage import Storage


class SiteBundleTests(unittest.TestCase):
    def test_exports_revision_aware_history_and_delta(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(str(Path(directory) / "test.sqlite"))
            try:
                for as_of, value in (("2026-10-22", 4.96), ("2026-10-23", 5.00)):
                    storage.insert_observations([Observation(
                        sensor_id="us10y_yield",
                        value=value,
                        unit="percent",
                        source="U.S. Department of the Treasury",
                        source_identifier="treasury:BC_10YEAR",
                        source_url="https://home.treasury.gov/",
                        as_of=as_of,
                        publication_date=as_of,
                        retrieved_at="2026-10-25T07:00:00+00:00",
                        instrument="U.S. Treasury 10-Year Constant Maturity",
                        frequency="daily",
                        quality="official_primary",
                    )])
                paths = export_all(storage, str(Path(directory) / "exports"), "2026-10-25T07:15:35+00:00")
            finally:
                storage.close()

            payload = json.loads(Path(paths["site_bundle"]).read_text(encoding="utf-8"))
            sensor = payload["sensors"]["us10y_yield"]
            self.assertEqual(sensor["latest"]["value"], 5.0)
            self.assertAlmostEqual(sensor["delta"], 0.04)
            self.assertEqual([point["as_of"] for point in sensor["series"]], ["2026-10-22", "2026-10-23"])
            self.assertEqual(sensor["provenance"]["source_identifier"], "treasury:BC_10YEAR")
            self.assertNotIn("id", sensor["series"][0])
            self.assertNotIn("revision", sensor["series"][0])
            self.assertFalse(payload["delivery"]["real_time"])
            self.assertEqual(sensor["update_status"]["status"], "updated")
            self.assertEqual(sensor["update_status"]["last_valid_as_of"], "2026-10-23")

    def test_marks_missing_sensor_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Storage(str(Path(directory) / "test.sqlite"))
            try:
                paths = export_all(storage, str(Path(directory) / "exports"), "2026-10-25T07:15:35+00:00")
            finally:
                storage.close()
            payload = json.loads(Path(paths["site_bundle"]).read_text(encoding="utf-8"))
            status = payload["sensors"]["us10y_yield"]["update_status"]
            self.assertEqual(status["status"], "unavailable")
            self.assertIsNone(status["last_valid_as_of"])


if __name__ == "__main__":
    unittest.main()
