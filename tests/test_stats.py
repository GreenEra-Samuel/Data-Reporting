import unittest

from measurelog.stats import (HIGH, LOW, NO_LIMIT, OK, flag_outliers, median,
                              spec_status, summarize)


class SummarizeTests(unittest.TestCase):
    def test_triplicate(self):
        stats = summarize([7.01, 7.03, 6.99])
        self.assertEqual(stats.n, 3)
        self.assertAlmostEqual(stats.mean, 7.01)
        self.assertAlmostEqual(stats.sd, 0.02, places=10)
        self.assertAlmostEqual(stats.rsd, 0.2853067, places=5)
        self.assertAlmostEqual(stats.span, 0.04, places=10)

    def test_sample_not_population_sd(self):
        # Sample SD of 1,2,3 is 1.0; the population SD would be 0.816.
        self.assertAlmostEqual(summarize([1, 2, 3]).sd, 1.0)

    def test_single_value_has_no_sd(self):
        stats = summarize([5.0])
        self.assertEqual(stats.n, 1)
        self.assertEqual(stats.mean, 5.0)
        self.assertIsNone(stats.sd)
        self.assertIsNone(stats.rsd)

    def test_empty_and_blank(self):
        for values in ([], [None, None]):
            stats = summarize(values)
            self.assertEqual(stats.n, 0)
            self.assertIsNone(stats.mean)
            self.assertFalse(stats.has_data)

    def test_blanks_are_ignored_not_counted_as_zero(self):
        stats = summarize([4.0, None, 6.0])
        self.assertEqual(stats.n, 2)
        self.assertAlmostEqual(stats.mean, 5.0)

    def test_zero_mean_leaves_rsd_undefined(self):
        stats = summarize([-1.0, 1.0])
        self.assertEqual(stats.mean, 0.0)
        self.assertIsNotNone(stats.sd)
        self.assertIsNone(stats.rsd)

    def test_non_finite_values_are_dropped(self):
        stats = summarize([1.0, float("nan"), float("inf"), 3.0])
        self.assertEqual(stats.n, 2)
        self.assertAlmostEqual(stats.mean, 2.0)

    def test_strings_that_look_like_numbers_are_accepted(self):
        self.assertEqual(summarize(["2", "4"]).mean, 3.0)


class SpecStatusTests(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(spec_status(5, 1, 10), OK)

    def test_below_and_above(self):
        self.assertEqual(spec_status(0.5, 1, 10), LOW)
        self.assertEqual(spec_status(99, 1, 10), HIGH)

    def test_boundaries_are_inclusive(self):
        self.assertEqual(spec_status(1, 1, 10), OK)
        self.assertEqual(spec_status(10, 1, 10), OK)

    def test_one_sided_limits(self):
        self.assertEqual(spec_status(0.5, lower=1), LOW)
        self.assertEqual(spec_status(50, lower=1), OK)
        self.assertEqual(spec_status(50, upper=10), HIGH)

    def test_no_limits_or_no_value(self):
        self.assertEqual(spec_status(5), NO_LIMIT)
        self.assertEqual(spec_status(None, 1, 10), NO_LIMIT)


class OutlierTests(unittest.TestCase):
    def test_flags_the_odd_replicate_in_a_triplicate(self):
        # A z-score test cannot flag anything at n=3; this rule must.
        self.assertEqual(flag_outliers([1.00, 1.01, 5.00], rsd_limit=5), [2])

    def test_tight_triplicate_is_clean(self):
        self.assertEqual(flag_outliers([7.01, 7.03, 6.99], rsd_limit=5), [])

    def test_disabled_without_a_limit(self):
        self.assertEqual(flag_outliers([1.0, 1.0, 50.0]), [])

    def test_needs_three_values(self):
        self.assertEqual(flag_outliers([1.0, 50.0], rsd_limit=1), [])

    def test_identical_values_never_flag(self):
        self.assertEqual(flag_outliers([2.0, 2.0, 2.0], rsd_limit=0.1), [])

    def test_index_refers_to_the_original_position_including_blanks(self):
        self.assertEqual(flag_outliers([1.00, None, 1.01, 5.00], rsd_limit=5), [3])


class MedianTests(unittest.TestCase):
    def test_odd_and_even(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([1, 2, 3, 4]), 2.5)


if __name__ == "__main__":
    unittest.main()
