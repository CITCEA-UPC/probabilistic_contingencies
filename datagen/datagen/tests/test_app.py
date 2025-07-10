"""
Unit tests to verify that executions of datagen run properly. Also test the
resulting csv files for data integrity.

To run the tests and send the output to a file, run from the terminal:
>> python -m unittest test_app | tee test_app.txt
"""

import os
import pandas as pd
import re
import shutil
import sys
import unittest
import yaml


class Test(unittest.TestCase):
    results_dir = "results"
    old_results_dir = "results_old"
    current_case = None

    def test_app(self):
        """
        Run 'run_datagen_ACOPF.py' with different configurations
        of parameters:
            n_samples
            n_cases
            max_depth
            seed
        and check for errors during execution.
        """
        # Cases initialization
        hyperparam_combinations = [  # n_samples, n_cases, max_depth
            [1, 1, 1],
            [2, 2, 2],
            [2, 1, 3]
        ]
        seeds = [17, 32]
        # Repeat case for each seed
        hyperparam_combinations = [
            hyparams + [seed] for hyparams in hyperparam_combinations
            for seed in seeds
        ]

        # Directory initialization
        yaml_path = '../../setup/test_setup.yaml'
        working_dir = '.'
        if os.path.isdir(self.results_dir):
            shutil.rmtree(self.results_dir)
        os.makedirs(self.results_dir)
        if not os.path.isdir(self.old_results_dir):
            os.makedirs(self.old_results_dir)

        # Load YAML file
        with open(yaml_path) as stream:
            base_yaml = yaml.safe_load(stream)

        # Get module
        sys.path.append('../../')
        from run_datagen_ACOPF import main

        # Loop over hyperparameters
        passed = True
        failed = []
        errors_failed = []
        for n_samples, n_cases, max_depth, seed in hyperparam_combinations:
            # Update YAML
            base_yaml['n_samples'] = n_samples
            base_yaml['n_cases'] = n_cases
            base_yaml['max_depth'] = max_depth
            base_yaml['seed'] = seed
            # Set current case for messaging purposes
            self.current_case = (n_samples, n_cases, max_depth, seed)

            # Save YAML
            with open(yaml_path, 'w') as stream:
                yaml.dump(base_yaml, stream)

            # Run
            try:
                print(f'\n{"".join(["="] * 60)}\n'
                      f"=== Running with n_samples={n_samples}, "
                      f"n_cases={n_cases}, max_depth={max_depth} ==="
                      f'\n{"".join(["="] * 60)}\n', flush=True)
                main(setup_path=yaml_path, working_dir=working_dir)
                print(f"\n=== Everything went fine ===\n", flush=True)
            except Exception as e:
                passed = False
                print(f"\n=== Error with n_samples={n_samples}, "
                      f"n_cases={n_cases}, max_depth={max_depth} ===\n",
                      flush=True)
                print(f"Exception caught: {e}", flush=True)
                failed.append((n_samples, n_cases, max_depth))
                errors_failed.append(e)

            # Read results
            results_subdirs = os.listdir(self.results_dir)
            if len(results_subdirs) < 1:
                raise ValueError("No directories found inside results.")
            elif len(results_subdirs) > 1:
                raise ValueError("More than one results directory found.")

            case_dir = os.path.join(self.results_dir, results_subdirs[0])
            cases_df = pd.read_csv(os.path.join(case_dir, "cases_df.csv"),
                                   index_col=0)
            dims_df = pd.read_csv(os.path.join(case_dir, "dims_df.csv"),
                                  index_col=0)
            
            # Launch tests
            self.no_duplicate_rows(cases_df, dims_df)
            self.column_sums_match(cases_df, dims_df)

            # Move results directory when finished
            dst_dir = os.path.join(self.old_results_dir, results_subdirs[0])
            shutil.move(case_dir, dst_dir)

        # Assert executions that failed before running the subtests
        if not passed:
            for fail, error in zip(failed, errors_failed):
                print(f"Failed with configurations: {fail}")
                print(f"Errors: {error}")
        self.assertTrue(passed, f"Some configurations failed: {failed}")

    def no_duplicate_rows(self, cases_df, dims_df):
        """ Check if there are any duplicated rows in cases_df. """
        cases_duplicates = cases_df[cases_df.duplicated()]
        dims_duplicates = dims_df[dims_df.duplicated()]

        # Assert no duplicates exist
        self.assertTrue(
            cases_duplicates.empty,
            f"Duplicate rows found in cases_df:\n{cases_duplicates}")
        self.assertTrue(
            dims_duplicates.empty,
            f"Duplicate rows found in dims_df:\n{dims_duplicates}")

    def column_sums_match(self, cases_df, dims_df):
        """
        Check that sums of cases_df columns match the overall values in
        dims_df.
        """
        # Use a regex to find columns ending with '_VarXX'
        var_column_pattern = re.compile(r'^(.*)_Var\d+$')

        # Dictionary to hold column groups in cases_df that need to be summed
        columns_to_sum = {}

        for col in cases_df.columns:
            match = var_column_pattern.match(col)
            if match:
                # Extract the prefix (e.g., 'col' from 'col_Var1')
                prefix = match.group(1)
                # Group columns by their prefix to sum them later
                if prefix not in columns_to_sum:
                    columns_to_sum[prefix] = []
                columns_to_sum[prefix].append(col)
            else:
                # Direct comparison for columns without '_VarXX'
                if col in dims_df.columns:
                    with self.subTest(col=col):
                        self.assertTrue(
                            cases_df[col].equals(dims_df[col]),
                            f"Column {col} in cases_df does not match"
                            f" the same column in dims_df")
                else:
                    print(f"Warning: column {col} found in cases_df.csv "
                          f"but not in dims_df.csv")

        # Now handle the columns that need to be summed
        for prefix, related_columns in columns_to_sum.items():
            if prefix in dims_df.columns:
                # Sum the related columns in cases_df
                cases_sum = cases_df[related_columns].sum(axis=1)
                dims_col = dims_df[prefix]

                # Assert that the sums match a column in dims_df
                with self.subTest(prefix=prefix,
                                  msg=f"Current case: {self.current_case}"):
                    pd.testing.assert_series_equal(
                        cases_sum, dims_col, check_names=False, rtol=1e-3)
            else:
                self.fail(f"Column {prefix} not found in dims_df!")


if __name__ == '__main__':
    unittest.main()
