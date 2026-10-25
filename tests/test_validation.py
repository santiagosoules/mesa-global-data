import unittest

from mesa_global_data.validation import validate_observation


def valid_observation():
    return {
        "sensor_id": "us10y_yield",
        "value": 5.0,
        "unit": "percent",
        "source": "U.S. Department of the Treasury",
        "source_identifier": "treasury:BC_10YEAR",
        "source_url": "https://home.treasury.gov/",
        "as_of": "2026-10-23",
        "publication_date": "2026-10-23",
        "retrieved_at": "2026-10-25T07:00:00+00:00",
        "instrument": "U.S. Treasury 10-Year Constant Maturity",
        "frequency": "daily",
        "quality": "official_primary",
        "data_kind": "observed",
        "latency": "publication",
        "access": "public",
        "status": "ok",
    }


class ObservationValidationTests(unittest.TestCase):
    def test_valid_observation(self):
        self.assertEqual(validate_observation(valid_observation()), [])

    def test_missing_publication_date_detected(self):
        observation = valid_observation()
        observation["publication_date"] = None
        issue_types = {issue["type"] for issue in validate_observation(observation)}
        self.assertIn("missing_field", issue_types)

    def test_out_of_range_detected(self):
        observation = valid_observation()
        observation["value"] = 50.0
        issue_types = {issue["type"] for issue in validate_observation(observation)}
        self.assertIn("out_of_range", issue_types)

    def test_wrong_unit_detected(self):
        observation = valid_observation()
        observation["unit"] = "basis_points"
        issue_types = {issue["type"] for issue in validate_observation(observation)}
        self.assertIn("wrong_unit", issue_types)


if __name__ == "__main__":
    unittest.main()

