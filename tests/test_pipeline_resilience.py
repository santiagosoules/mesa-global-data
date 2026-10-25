import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mesa_global_data.models import Observation
from mesa_global_data.pipeline import collect_all
from mesa_global_data.sensors import SENSORS
from mesa_global_data.storage import Storage


class PipelineResilienceTests(unittest.TestCase):
    def test_source_failure_keeps_last_valid_value_and_exports_error_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "data.sqlite"
            exports = root / "exports"
            sensor = SENSORS["us10y_yield"]
            storage = Storage(str(database))
            storage.insert_observations([Observation(
                sensor_id=sensor.id,
                value=5.0,
                unit=sensor.unit,
                source="U.S. Department of the Treasury",
                source_identifier="treasury:BC_10YEAR",
                source_url="https://home.treasury.gov/",
                as_of="2026-10-23",
                publication_date="2026-10-23",
                retrieved_at="2026-10-23T22:00:00+00:00",
                instrument=sensor.instrument,
                frequency=sensor.frequency,
                quality="official_primary",
            )])
            storage.close()

            with patch("mesa_global_data.pipeline.treasury.collect", side_effect=RuntimeError("upstream timeout")), patch(
                "mesa_global_data.pipeline.nyfed.collect", return_value=[]
            ), patch("mesa_global_data.pipeline.ofr.collect", return_value=[]):
                result = collect_all(
                    str(database), str(exports), profile="daily",
                    started_at="2026-10-25T12:00:00+00:00",
                )

            payload = json.loads((exports / "site_bundle.json").read_text(encoding="utf-8"))
            item = payload["sensors"]["us10y_yield"]
            self.assertEqual(item["latest"]["value"], 5.0)
            self.assertEqual(item["latest"]["as_of"], "2026-10-23")
            self.assertEqual(item["update_status"]["status"], "source_error")
            self.assertEqual(item["update_status"]["detail"], "source check failed")
            self.assertIn(result["status"], {"degraded", "error"})
            self.assertNotIn("diagnostics", payload)
            self.assertNotIn("upstream timeout", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
