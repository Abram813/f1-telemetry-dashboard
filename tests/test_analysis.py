import unittest

import pandas as pd

from f1lab.analysis import (
    braking_difference, first_braking_sample, format_lap_time,
    select_section, summarize_section,
)


class SectionAnalysisTests(unittest.TestCase):
    def telemetry(self, brakes, distances=None):
        return pd.DataFrame({
            "Distance": distances or [3700, 3800, 3900, 4000],
            "Speed": [300, 290, 270, 230],
            "Brake": pd.array(brakes, dtype="boolean"),
        }, index=[236, 238, 240, 242])

    def test_observed_onset_keeps_previous_off_sample(self):
        result = summarize_section(self.telemetry([False, False, True, False]), 3700, 4100)
        self.assertEqual(result.brake_status, "observed_onset")
        self.assertEqual(result.brake_distance, 3900)
        self.assertEqual(result.previous_distance, 3800)
        self.assertEqual(result.brake_speed, 270)
        self.assertEqual(result.minimum_speed, 230)

    def test_already_braking_at_range_start_is_not_an_onset(self):
        result = summarize_section(self.telemetry([False, False, True, False]), 3900, 4100)
        self.assertEqual(result.brake_status, "active_at_start")
        self.assertIsNone(braking_difference(result, result))

    def test_empty_range_and_no_braking_have_distinct_meanings(self):
        data = self.telemetry([False] * 4)
        self.assertEqual(summarize_section(data, 2000, 3000).brake_status, "no_samples")
        self.assertEqual(summarize_section(data, 3700, 4100).brake_status, "no_braking")
        self.assertIsNone(first_braking_sample(data, 3700, 4100))

    def test_missing_brake_data_does_not_become_off(self):
        result = summarize_section(self.telemetry([pd.NA] * 4), 3700, 4100)
        self.assertEqual(result.brake_status, "missing_brake_data")
        result = summarize_section(self.telemetry([False, pd.NA, True, False]), 3700, 4100)
        self.assertEqual(result.brake_status, "unknown_previous_sample")

    def test_signed_difference_and_swapping_drivers(self):
        first = summarize_section(self.telemetry([False, False, True, False]), 3700, 4100)
        second = summarize_section(self.telemetry([False, False, True, False],
                                                   [3700, 3800, 3911.1, 4000]), 3700, 4100)
        self.assertAlmostEqual(braking_difference(first, second), 11.1)
        self.assertAlmostEqual(braking_difference(second, first), -11.1)

    def test_nonconsecutive_labels_do_not_change_first_sample(self):
        result = first_braking_sample(self.telemetry([False, False, True, False]), 3700, 4100)
        self.assertEqual(result.name, 240)
        self.assertEqual(result["Distance"], 3900)

    def test_invalid_windows_are_rejected(self):
        for start, end in [(10, 10), (11, 10), (float("nan"), 4000)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                select_section(self.telemetry([False] * 4), start, end)

    def test_lap_time_formatting_carries_rounding_into_next_minute(self):
        self.assertEqual(format_lap_time(86.023), "1:26.023")
        self.assertEqual(format_lap_time(59.9999), "1:00.000")


if __name__ == "__main__":
    unittest.main()
