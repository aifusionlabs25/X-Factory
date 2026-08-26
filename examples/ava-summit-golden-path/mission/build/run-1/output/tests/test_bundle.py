from pathlib import Path
import unittest
from x_factory.acceptance import run_contract_fixture


class TestBundle(unittest.TestCase):
    def test_phase1_3_contract(self):
        result = run_contract_fixture(Path(__file__).resolve().parents[1])
        self.assertEqual(result["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
