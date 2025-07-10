from unittest import TestCase

from datagen import *
from datagen.tests.utils import gen_df_for_dims, linear_function, \
    dim0_func, parab_func
from datagen.src.sampling import sensitivity


class Test(TestCase):

    def setUp(self):
        """
        This code executes every time a subtest of this class is run.
        """
        variables = [(0, 10), (0, 15), (10, 20), (0, 25)]

        self.dim1 = Dimension(variable_borders=variables, n_cases=3, divs=1,
                              borders=(10, 70), label="Dim1")
        self.dim2 = Dimension(variable_borders=variables, n_cases=3, divs=2,
                              borders=(10, 70), label="Dim2")
        self.dim3 = Dimension(variable_borders=variables, n_cases=3, divs=2,
                              borders=(10, 70), label="Dim3")

        self.dims = [self.dim1, self.dim2, self.dim3]

        self.children_grid = gen_grid(self.dims)

        self.dims_df = pd.DataFrame({
            "Dim1": [10, 35, 70],
            "Dim2": [15, 39, 20],
            "Dim3": [39, 30, 60]
        })

        self.generator = np.random.default_rng(1)

        self.cases_heritage_df = pd.DataFrame({
            "Dim1_Var0": [0, 6, 10],
            "Dim1_Var1": [0, 8, 15],
            "Dim1_Var2": [10, 15, 20],
            "Dim1_Var3": [0, 6, 25],
            "Dim2_Var0": [0, 10, 5],
            "Dim2_Var1": [3, 9, 0],
            "Dim2_Var2": [10, 10, 15],
            "Dim2_Var3": [2, 10, 0],
            "Dim3_Var0": [9, 6, 0],
            "Dim3_Var1": [10, 8, 15],
            "Dim3_Var2": [10, 15, 20],
            "Dim3_Var3": [10, 1, 25],
            "Stability": [1, 0, 0]
        })

    def test_generate_columns(self):
        cols = generate_columns(self.dim1)
        self.assertTrue(cols,
                        ["Dim1_Var0", "Dim1_Var1", "Dim1_Var2", "Dim1_Var3"])

    def test_gen_samples(self):
        n_samples = 100
        df_samples = gen_samples(n_samples, self.dims, self.generator)

        for dim in self.dims:
            self.assertTrue(all(df_samples[dim.label] >= dim.borders[0]))
            self.assertTrue(all(df_samples[dim.label] <= dim.borders[1]))

    def test_gen_grid(self):
        """
        This code creates a list of expected borders based on all possible
        combinations using dimensions borders and divs, and compare it to
        gen_grid output.
        """
        grid = gen_grid(self.dims)

        expected_cells = 1 * 2 * 2
        expected_borders = [[(10., 70.), (10., 40.), (10., 40.)],
                            [(10., 70.), (10., 40.), (40., 70.)],
                            [(10., 70.), (40., 70.), (10., 40.)],
                            [(10., 70.), (40., 70.), (40., 70.)]]
        self.assertEqual(len(grid), expected_cells)
        borders = []
        for cell in grid:
            new_cell_borders = []
            for dim in cell.dimensions:
                new_cell_borders.append(dim.borders)
            borders.append(new_cell_borders)
        self.assertEqual(borders, expected_borders)

    def test_calculate_entropy(self):
        freqs = [0.25, 0.75]
        expected_entropy = -0.25 * np.log(0.25) - 0.75 * np.log(0.75)
        result_entropy = calculate_entropy(freqs)
        self.assertAlmostEqual(result_entropy, expected_entropy, places=5)

    def test_eval_entropy(self):
        stabilities = [1, 0, 0, 0]
        entropy_parent = None
        expected_freqs = [0.25, 0.75]
        expected_entropy = calculate_entropy(expected_freqs)
        expected_delta_entropy = 1

        result_entropy, result_delta_entropy = eval_entropy(stabilities,
                                                            entropy_parent)

        self.assertAlmostEqual(result_entropy, expected_entropy, places=5)
        self.assertEqual(result_delta_entropy, expected_delta_entropy)

        stabilities = [1, 0, 0, 0]
        entropy_parent = 0.3
        expected_freqs = [0.25, 0.75]
        expected_entropy = calculate_entropy(expected_freqs)
        expected_delta_entropy = expected_entropy - entropy_parent

        result_entropy, result_delta_entropy = eval_entropy(stabilities,
                                                            entropy_parent)

        self.assertAlmostEqual(result_entropy, expected_entropy, places=5)
        self.assertEqual(result_delta_entropy, expected_delta_entropy)

    def test_get_children_parameters(self):
        total_cases_df, total_dims_df, _ = (
            get_children_parameters(self.children_grid,
                                    self.dims_df,
                                    self.cases_heritage_df))

        # (Dim1: 10-70, Dim2: 10-40, Dim3: 10-40)
        self.assertEqual(len(total_cases_df[0]), 2)
        a = total_cases_df[0].astype('float')
        b = self.cases_heritage_df.iloc[0:2].astype('float')
        pd.testing.assert_frame_equal(a, b)

        # (Dim1: 10-70, Dim2: 10-40, Dim3: 40-70)
        a = total_cases_df[1].astype('float')
        b = self.cases_heritage_df.iloc[2:3].astype('float')
        b = b.reset_index(drop=True)
        self.assertEqual(len(total_cases_df[1]), 1)
        pd.testing.assert_frame_equal(a, b)

        # (Dim1: 10-70, Dim2: 40-70, Dim3: 10-40)
        self.assertEqual(len(total_cases_df[2]), 0)

        # (Dim1: 10-70, Dim2: 40-70, Dim3: 40-70)
        self.assertEqual(len(total_cases_df[3]), 0)

    def test_sensitivity(self):
        variables = [(0, 10), (0, 10), (0, 10), (0, 10)]
        dim1 = Dimension(variable_borders= variables, n_cases=3, divs=1, borders=(0, 70),
                         label="Dim1")
        dim2 = Dimension(variable_borders= variables, n_cases=3, divs=2, borders=(0, 70),
                         label="Dim2")
        dim3 = Dimension(variable_borders= variables, n_cases=3, divs=2, borders=(0, 70),
                         label="Dim3")
        dims = [dim1, dim2, dim3]

        for dim in dims:
            dim.tolerance = (dim.borders[1] - dim.borders[0]) * 0.1

        cases_df = gen_df_for_dims(dims, 1000)

        linear_cases_df = cases_df.copy()
        parab_cases_df = cases_df.copy()
        dim0_cases_df = cases_df.copy()

        linear_cases_df["Stability"] = (
            linear_cases_df.apply(linear_function, axis=1))
        parab_cases_df["Stability"] = parab_cases_df.apply(parab_func, axis=1)
        dim0_cases_df["Stability"] = dim0_cases_df.apply(dim0_func, axis=1)

        dims_linear = sensitivity(linear_cases_df, dims, divs_per_cell=2,
                                  generator=self.generator)
        dims_linear_divs = [dim.divs for dim in dims_linear]
        dims_parab = sensitivity(parab_cases_df, dims, divs_per_cell=2,
                                 generator=self.generator)
        dims_parab_divs = [dim.divs for dim in dims_parab]
        dims_dim0 = sensitivity(dim0_cases_df, dims, divs_per_cell=2,
                                generator=self.generator)
        dims_dim0_divs = [dim.divs for dim in dims_dim0]

        self.assertEqual(dims_linear_divs, [1, 1, 2])
        self.assertEqual(dims_parab_divs, [1, 2, 1])
        self.assertEqual(dims_dim0_divs, [2, 1, 1])

    def test_concat_df_dict(self):
        """
        Test the 'concat_total_dataframes()' function in a nested dictionary of
        dataframes so that the recursive feature is tested.
        """
        df1 = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': ['alpha', 'beta', 'gamma', 'delta', 'epsilon'],
            'C': [10.5, 20.1, 30.3, 40.2, 50.0]
        })
        df2 = pd.DataFrame({
            'D': [101, 102, 103, 104],
            'E': [1.1, 2.2, 3.3, 4.4],
            'F': ['A', 'B', 'C', 'D']
        })
        df_dict = {'df1': df1, 'df2': df2}

        # Concatentate df_dict with itself
        df_dict = concat_df_dict(df_dict, df_dict)

        # Run assertions
        self.assertEqual(df_dict['df1'].shape, (2 * len(df1), df1.shape[1]),
                         msg=f'Shape of df1: {df_dict["df1"].shape} differs '
                             f'from the expected shape of df1: '
                             f'{(2 * len(df1), df1.shape[1])}')
        self.assertEqual(df_dict['df2'].shape,
                         (2 * len(df2), df2.shape[1]),
                         msg=f'Shape of df2: {df_dict["df2"].shape}'
                             f'differs from the expected shape of df2: '
                             f'{(2 * len(df2), df2.shape[1])}')
        self.assertListEqual(
            df_dict['df2']['E'].tolist(),
            [1.1, 2.2, 3.3, 4.4, 1.1, 2.2, 3.3, 4.4],
            msg=f'df_dict["df2"]\n {df_dict["df2"]}\n'
                f'is not as expected')
        print(df_dict)
