from unittest import TestCase

import pandas as pd
import numpy as np

from datagen import Dimension, start, dummy


class Test(TestCase):
    def setUp(self):
        p_sg = [(0, 0.1), (0, 0.1), (0, 0.1), (10, 25)]
        p_cig = [(0, 1), (0, 1.5), (0, 1.5), (0, 2)]
        perc_g_for = [(0,1)]
        tau_f_g_for = [(0., 2)]
        tau_v_g_for = [(0., 2)]
        tau_p_g_for = [(0., 2)]
        tau_q_g_for = [(0., 2)]
        p_load = [0.5,0.4,0.1]
        self.cosphi = 0.5
        self.n_samples = 3
        self.n_cases = 3
        # ax = plt.figure().add_subplot(projection='3d')
        self.ax = None
        self.use_sensitivity = False
        self.rel_tolerance = 0.01
        self.max_depth = 5
        self.func = dummy
        self.dimensions = [
            Dimension(variable_borders=p_sg, n_cases=self.n_cases, divs=2,
                      borders=(10, 25.3), label="p_sg", cosphi=self.cosphi),
            Dimension(variable_borders=p_cig, n_cases=self.n_cases, divs=1,
                      borders=(0, 6), label="p_cig", cosphi=self.cosphi),
            Dimension(variable_borders=tau_f_g_for, n_cases=self.n_cases, divs=1,
                      borders=(0, 2), label="tau_f_g_for"),
            Dimension(variable_borders=tau_v_g_for, n_cases=self.n_cases, divs=1,
                      borders=(0, 2), label="tau_v_g_for"),
            Dimension(variable_borders=tau_p_g_for, n_cases=self.n_cases, divs=1,
                      borders=(0, 2), label="tau_p_g_for"),
            Dimension(variable_borders=tau_q_g_for, n_cases=self.n_cases, divs=1,
                      borders=(0, 2), label="tau_q_g_for"),
            Dimension(variable_borders=perc_g_for, n_cases=self.n_cases, divs=1,
                      borders=(0,1), label="perc_g_for"),
            Dimension(values=p_load, n_cases=self.n_cases, label="p_load",
                      independent_dimension=False, cosphi=self.cosphi)
        ]

    def test_start(self):
        cases_df, dims_df, execution_logs = \
            start(self.dimensions, self.n_samples, self.rel_tolerance,
                  self.func, self.max_depth,
                  use_sensitivity=self.use_sensitivity, ax=self.ax)
        # assert that cases_df must have 44 columns and dims_df 15
        self.assertEqual(cases_df.shape[1], 44)
        self.assertEqual(dims_df.shape[1], 15)

        # assert that the sum of the variable_borders of a concrete dimension in
        # cases_df almost equals the value in dims_df
        dim_labels = list(set(col.rsplit('_Var')[0]
                          for col in cases_df.columns if '_Var' in col))
        dims_expected_df = pd.DataFrame()
        for label in dim_labels:
            matching_columns = (
                cases_df.filter(
                    regex=r'^' + label + r'_*', axis=1).sum(axis=1))
            dims_expected_df[label] = matching_columns
        dims_expected_df.columns = dim_labels
        dims_expected_df = dims_expected_df[dims_df.columns]
        pd.testing.assert_frame_equal(dims_expected_df, dims_df,
                                      check_exact=False, atol=1e-5)

        # assert that each value is within dimension borders
        for idx, row in dims_df.iterrows():
            q_columns = row.filter(regex=r'^q_')
            row = row.drop(labels=q_columns.index)
            for label, value in row.items():
                if label == "p_g_for" or label == "p_g_fol":
                    dim = next(
                        (d for d in self.dimensions
                         if d.label == "p_cig"), None)
                else:
                    dim = next((d for d in self.dimensions
                                if d.label == label), None)
                if dim.independent_dimension:
                    if not dim.borders[0] <= value <= dim.borders[1]:
                        pass
                    self.assertTrue(dim.borders[0] <= value <= dim.borders[1])

        # assert that there is no null value in cases_df and that every value
        # is within associated variable limits
        for idx, row in cases_df.iterrows():
            q_columns = row.filter(regex=r'^q_')
            row = row.drop(labels=q_columns.index)
            for label, value in row.items():
                if label != "Stability":
                    self.assertIsNotNone(value)
                    dim_label = label.rsplit('_Var')[0]
                    var_idx = int(label.rsplit('_Var')[1])
                    if dim_label == "p_g_for" or dim_label == "p_g_fol":
                        dim = next(
                            (d for d in self.dimensions
                             if d.label == "p_cig"), None)
                    else:
                        dim = next((d for d in self.dimensions
                                    if d.label == dim_label), None)
                    if (isinstance(dim.variable_borders, np.ndarray) and
                            not np.all(np.isnan(dim.variable_borders))):
                        self.assertTrue(dim.variable_borders[var_idx][0] <=
                                        value <=
                                        dim.variable_borders[var_idx][1])

        # assert that p_load dims are equal to p_sg plus p_cig
        for idx, row in dims_df.iterrows():
            self.assertAlmostEqual(row["p_load"], row["p_sg"] + row["p_cig"])

        # assert that, for all indices in a DataFrame named dims_df that start
        # with 'p_', there exists an index in dims_df with the same name by
        # replacing 'p_' with 'q_', such that the value of the column starting
        # with 'p_' multiplied by np.sqrt(1 - dim.cosphi ** 2) / dim.cosphi is
        # almost equal to the value of the column starting with 'q_'
        p_columns = dims_df.filter(regex=r'^p_')
        for idx, row in p_columns.iterrows():
            for p_col_name, p_col_value in row.items():
                expected_q_value = (np.sqrt(
                    1 - self.cosphi ** 2) / self.cosphi * p_col_value)
                q_col_name = p_col_name.replace('p_', 'q_')
                q_col_value = dims_df.at[idx, q_col_name]
                self.assertAlmostEquals(expected_q_value, q_col_value)

