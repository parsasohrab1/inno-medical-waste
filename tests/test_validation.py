import os, tempfile, unittest
from inno_medical_waste import core, __main__ as cli


class TestValidation(unittest.TestCase):
    def test_generate_is_reproducible_and_nonempty(self):
        a, b = core.generate(5), core.generate(5)
        self.assertEqual(a, b)
        self.assertTrue(a and all(len(v) > 0 for v in a.values()))
        self.assertNotEqual(core.generate(6), a)

    def test_csv_export(self):
        with tempfile.TemporaryDirectory() as d:
            cli.write_tables(core.generate(1), d)
            self.assertTrue(any(f.endswith(".csv") for f in os.listdir(d)))

    def test_trl4_criteria_hold_on_three_seeds(self):
        rep = cli.validate(0, 3)
        failed = [(r["seed"], c["metric"], c["value"]) for r in rep["runs"] for c in r["criteria"] if not c["pass"]]
        self.assertEqual(failed, [])

    def test_demo_runs(self):
        self.assertTrue(core.demo(0))


if __name__ == "__main__":
    unittest.main()
