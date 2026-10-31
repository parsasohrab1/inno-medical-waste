import unittest
import numpy as np
from inno_medical_waste import core


def good():
    code = core.make_code(3, "1", 261031, 7)
    return {"code": code, "type": "infectious", "container_id": "", "events": [
        {"stage": "generated", "t_h": 0, "kg": 10}, {"stage": "collected", "t_h": 5, "kg": 10}, {"stage": "stored", "t_h": 6, "kg": 10},
        {"stage": "treated", "t_h": 30, "kg": 10}, {"stage": "disposed", "t_h": 40, "kg": 10}]}


class TestWaste(unittest.TestCase):
    def test_code_roundtrip(self):
        c = core.make_code(12, "2", 261031, 99)
        self.assertTrue(core.valid_code(c)); self.assertEqual(core.parse_code(c)["type"], "sharps")

    def test_every_single_digit_error_detected(self):
        c = core.make_code(5, "1", 261001, 1234)
        for i in range(len(c)):
            for d in "0123456789":
                if d != c[i]:
                    self.assertFalse(core.valid_code(c[:i] + d + c[i + 1:]))

    def test_good_record_is_clean(self):
        self.assertEqual(core.check_record(good()), [])

    def test_each_rule(self):
        r = good(); r["events"][1]["t_h"] = 30
        self.assertIn("R2_late_collection", core.check_record(r))
        r = good(); r["events"][4]["kg"] = 5
        self.assertIn("R4_weight_mismatch", core.check_record(r))
        r = good(); r["events"].pop(2)
        self.assertIn("R1_missing_stage", core.check_record(r))
        r = good(); r["code"] = core.make_code(3, "2", 261031, 7); r["type"] = "sharps"
        self.assertIn("R5_sharps_without_container", core.check_record(r))
        r = good(); r["type"] = "general"
        self.assertIn("R6_type_mismatch", core.check_record(r))

    def test_bad_code_flagged(self):
        r = good(); r["code"] = r["code"][:-1] + str((int(r["code"][-1]) + 1) % 10)
        self.assertEqual(core.check_record(r), ["R0_bad_code"])
