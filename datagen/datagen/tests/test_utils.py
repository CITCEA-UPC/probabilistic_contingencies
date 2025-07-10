
import pandas as pd

from unittest import TestCase
from datagen.src.utils import sort_df_rows_by_another

class Test(TestCase):
    def test_sort_dataframe_by_another(self):
        # Define df1 and df2
        df1 = pd.DataFrame({'id': [3, 1, 2], 'value': ['C', 'A', 'B']})
        df2 = pd.DataFrame({'id': [1, 2, 3], 'info': ['X', 'Y', 'Z']})

        # Expected result: df2 sorted to match the order of 'id' in df1
        expected_df = pd.DataFrame({'id': [3, 1, 2], 'info': ['Z', 'X', 'Y']})

        # Run the function
        result_df = sort_df_rows_by_another(df1, df2, 'id')

        # Assert the result matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)
