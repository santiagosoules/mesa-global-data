import unittest

from mesa_global_data.connectors.h41 import _package_ids, _rows


class PublicConnectorParserTests(unittest.TestCase):
    def test_h41_catalog_and_table_parsers(self):
        catalog = """
        <input value="rel=H41&amp;series=abc123&amp;lastobs=1"><label>H.4.1 Statistical Release - Table 1 [csv]</label>
        <input value="rel=H41&amp;series=aaa999&amp;lastobs=1"><label>H.4.1 Statistical Release - Table 1.A [csv]</label>
        <input value="rel=H41&amp;series=def456&amp;lastobs=1"><label>H.4.1 Statistical Release - Table 5 [csv]</label>
        """
        self.assertEqual(_package_ids(catalog), {"1": "abc123", "5": "def456"})
        table = b"<table><tr><th>Series</th><th>Description</th><th>2026-10-21</th></tr><tr><th>RESH4R_N.WW</th><th>Reserve balances</th><td>2969522</td></tr></table>"
        self.assertEqual(_rows(table)[1], ["RESH4R_N.WW", "Reserve balances", "2969522"])


if __name__ == "__main__":
    unittest.main()
