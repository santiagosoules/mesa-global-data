import tempfile
import unittest
from pathlib import Path

from mesa_global_data.bootstrap import bootstrap_from_bundle
from mesa_global_data.exporter import export_all
from mesa_global_data.models import Observation
from mesa_global_data.sensors import SENSORS
from mesa_global_data.storage import Storage


class BootstrapTests(unittest.TestCase):
    def test_public_json_round_trip_preserves_history_without_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = Storage(str(root / "private-one.sqlite"))
            sensor = SENSORS["ofr_fsi_credit"]
            first.insert_observations([
                Observation(
                    sensor_id=sensor.id,
                    value=value,
                    unit=sensor.unit,
                    source="U.S. Office of Financial Research",
                    source_identifier="ofr_fsi:credit",
                    source_url="https://www.financialresearch.gov/financial-stress-index/data/fsi.csv",
                    as_of=as_of,
                    publication_date=as_of,
                    retrieved_at="2026-10-25T12:00:00+00:00",
                    instrument=sensor.instrument,
                    frequency=sensor.frequency,
                    quality="official_primary",
                    data_kind="derived",
                    methodology="Official OFR FSI component.",
                    metadata={"ofr_fsi_column": "Credit"},
                )
                for as_of, value in (("2026-10-22", -0.9), ("2026-10-23", -0.8))
            ])
            paths = export_all(first, str(root / "public"), "2026-10-25T12:00:00+00:00")
            first.close()

            second = Storage(str(root / "private-two.sqlite"))
            result = bootstrap_from_bundle(second, paths["site_bundle"])
            restored = second.observations([sensor.id], limit_per_sensor=10, primary_only=True)
            second.close()

            self.assertEqual(result["observations_inserted"], 2)
            self.assertEqual([row["as_of"] for row in reversed(restored)], ["2026-10-22", "2026-10-23"])


if __name__ == "__main__":
    unittest.main()
