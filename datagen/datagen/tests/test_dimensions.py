from unittest import TestCase

import numpy as np

from datagen import Dimension


class Test(TestCase):
    def setUp(self):
        """
        This code executes every time a subtest of this class is run.
        """
        variables = np.array([(0, 10), (0, 15), (0, 20), (0, 25)])
        n_cases = 10
        divs = None
        lower, upper = 0, 70
        label = "Test"
        tolerance = 0.1
        dim1 = Dimension(variable_borders=variables, n_cases=n_cases, divs=divs,
                         borders=(lower, upper),
                         label=label)
        dim1.tolerance = tolerance
        self.generator = np.random.default_rng(1)

        variables = np.array([(0, 0.1), (0, 0.1), (0, 0.1), (10, 25)])
        n_cases = 10
        divs = None
        lower, upper = 10, 25.3
        label = "Test"
        tolerance = 0.1
        dim2 = Dimension(variable_borders=variables, n_cases=n_cases, divs=divs,
                         borders=(lower, upper),
                         label=label)
        dim2.tolerance = tolerance
        self.samples = np.random.uniform(0, 70, 300)
        self.dims = [dim1, dim2]

    def test_get_cases_extreme(self):
        for dim in self.dims:
            for sample in self.samples:
                variables_sum = dim.variable_borders.sum(axis=0)
                if not variables_sum[0] <= sample <= variables_sum[1]:
                    self.assertRaises(
                        ValueError, dim.get_cases_extreme, sample, self.generator)
                else:
                    cases = dim.get_cases_extreme(sample, self.generator)
                    for idx in range(len(cases)):
                        self.assertAlmostEqual(sum(cases[idx]), sample,
                                               places=2)
                        for var in range(len(cases[idx])):
                            self.assertTrue(dim.variable_borders[var, 0] <=
                                            cases[idx][var] <=
                                            dim.variable_borders[var, 1])
                            self.assertIsNotNone(cases[idx][var])

    def test_get_cases_normal(self):
        for dim in self.dims:
            for sample in self.samples:
                variables_sum = dim.variable_borders.sum(axis=0)
                if not variables_sum[0] <= sample <= variables_sum[1]:
                    self.assertRaises(
                        ValueError, dim.get_cases_extreme, sample, self.generator)
                else:
                    cases = dim.get_cases_extreme(sample, self.generator)
                    for idx in range(len(cases)):
                        for var in range(len(cases[idx])):
                            self.assertTrue(dim.variable_borders[var, 0] <=
                                            cases[idx][var] <=
                                            dim.variable_borders[var, 1])
                            self.assertIsNotNone(cases[idx][var])

