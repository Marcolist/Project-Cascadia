#!/usr/bin/env python3
"""Run the actual Apple temperature/voltage selector; no hardware access."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KC = Path(os.environ.get('CASCADIA_TEST_KERNELCACHE', ROOT / 'build/firmware/kernelcache.12H321.macho'))
ADT = Path(os.environ.get('CASCADIA_TEST_ADT', ROOT / 'build/usb-host-research/firmware/DeviceTree.p105ap.raw'))
AVAILABLE = importlib.util.find_spec('unicorn') is not None and KC.is_file() and ADT.is_file()


@unittest.skipUnless(AVAILABLE, 'needs Unicorn and locally extracted p105 12H321 kernelcache/ADT')
class ChargePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('charge_policy', ROOT / 'tools/power/emulate-charge-policy.py')
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        cls.data, cls.table, cls.limits = cls.m.load_inputs(KC, ADT)

    def policy(self, limit=None):
        return self.m.Policy(self.data, self.table, self.limits[0] if limit is None else limit)

    def test_outside_temperature_table_returns_zero_including_negative(self):
        for temperature in (-100, 0, 999, 4501, 10000):
            with self.subTest(temperature=temperature):
                self.assertEqual(self.policy().sample(temperature, 3900)['policy_ceiling_mA'], 0)

    def test_inclusive_voltage_thresholds_and_current_taper(self):
        for temperature, currents in ((1100, (2520, 2520, 2240, 2240, 1320)),
                                      (1800, (2520, 2520, 2520, 2520, 1320)),
                                      (3000, (2520, 2520, 2520, 2520, 2240))):
            for voltage, current in zip((3999, 4000, 4001, 4100, 4101), currents):
                with self.subTest(temperature=temperature, voltage=voltage):
                    self.assertEqual(self.policy().sample(temperature, voltage)['policy_ceiling_mA'], current)

    def test_first_matching_row_at_cold_start_overlap(self):
        for temperature, offset in ((1000, 0), (1500, 0), (1600, 0), (1601, 20),
                                    (2000, 20), (2100, 20), (2101, 40), (3400, 40),
                                    (3500, 40), (3501, 60), (4500, 60)):
            with self.subTest(temperature=temperature):
                self.assertEqual(self.policy().sample(temperature, 3900)['cached_row_offset'], offset)

    def test_cached_row_hysteresis_and_exit(self):
        p = self.policy()
        for temperature, offset in ((2200, 40), (2000, 40), (2100, 40), (1999, 20),
                                    (1500, 20), (1499, 0), (1600, 0), (1601, 20)):
            with self.subTest(temperature=temperature):
                self.assertEqual(p.sample(temperature, 4050)['cached_row_offset'], offset)

    def test_selected_charge_limit_caps_table_current(self):
        for limit in self.limits:
            self.assertEqual(self.policy(limit).sample(3000, 3900)['policy_ceiling_mA'], limit)

    def test_inhibition_flags_short_circuit_policy(self):
        for offset in (0x1c0, 0x1c1):
            p = self.policy()
            p.mu.mem_write(self.m.d1946.SOURCE + offset, b'\x01')
            self.assertEqual(p.sample(3000, 3900)['policy_ceiling_mA'], 0)

    def test_both_local_input_hashes_required(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / 'bad'
            bad.write_bytes(b'wrong firmware')
            for kc, adt in ((bad, ADT), (KC, bad)):
                with self.assertRaises(ValueError):
                    self.m.load_inputs(kc, adt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
