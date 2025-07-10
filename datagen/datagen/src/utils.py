#  Copyright 2002-2023 Barcelona Supercomputing Center (www.bsc.es)

#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""This utility module provides functions to check the size of the
dimensions against a specified tolerance to ensure they haven't become too
small. It also includes a function to flatten nested lists into a single
list, which is useful for processing the list of logs generated during the
exploration.
"""
import os
import uuid

import numpy as np
import yaml
import sys

import pandas as pd

from collections.abc import Sequence

from .constants import NAN_COLUMN_NAME
from .viz import print_dict_as_yaml
from stability_analysis.data import get_data_path

def combine_columns_by_prefix(df, sum_columns):
    """Combine columns in a dataframe by common prefixes."""
    result_df = pd.DataFrame()

    for col in df.columns:
        prefix = col.split("_Var")[0]
        if prefix not in result_df.columns:
            result_df[prefix] = sum_columns[prefix]
        else:
            result_df[prefix] += sum_columns[prefix]

    return result_df

def clean_dir(directory):
    if os.path.exists(directory):
        files = os.listdir(directory)
        for file in files:
            path = os.path.join(directory, file)
            if os.path.isfile(path):
                os.remove(path)
    else:
        os.makedirs(directory, exist_ok=True)


def get_dimension(label, dimensions):
    if label == "g_for" or label == "g_fol":
        dim = next(
            (d for d in dimensions
             if d.label == "p_cig"), None)
    else:
        dim = next((d for d in dimensions
                    if d.label == label), None)
    return dim


def check_dims(dimensions):
    """This method checks if the size of every dimension is smaller than the
    tolerance declared.

    :param dimensions: Cell dimensions
    :return: True if tolerance is bigger than this difference, false otherwise
    """
    for d in dimensions:
        if d.independent_dimension:
            if (d.borders[1] - d.borders[0]) < d.tolerance:
                return False
    return True


def flatten_list(data):
    """This method extracts the values of the list given, obtaining one element
     for each cell.

    :param data: list of logs of the children cells
    :return: flattened list
    """
    flattened_list = []
    for item in data:
        if isinstance(item, list):
            flattened_list.extend(flatten_list(item))
        else:
            flattened_list.append(item)
    return flattened_list


def write_dataframes_to_excel(df_dict, path, filename):
    excel_file_path = os.path.join(path, filename)
    # Create a Pandas Excel writer using xlsxwriter as the engine
    with pd.ExcelWriter(excel_file_path, engine='xlsxwriter') as writer:
        # Iterate over each key-value pair in the dictionary
        for sheet_name, df in df_dict.items():
            # Write each DataFrame to a separate sheet with the sheet name as the key
            if isinstance(df, dict):
                df = pd.DataFrame(df)
            if isinstance(df, pd.DataFrame) or isinstance(df, pd.Series):
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                print(f'Warning: Not writing {sheet_name}. '
                      f'Not a DataFrame or Series')


def save_dataframes(output_dataframes_array, path_results, seed):
    index = 0
    for dataframe in output_dataframes_array:
        if dataframe is None:
            continue
        for key, value in dataframe.items():
            cu = os.environ.get("COMPUTING_UNITS")
            filename = f"cu{cu}_case_{str(index)}_{key}_seed{str(seed)}"
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
            print(key, flush=True)
            print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
            print(value, flush=True)
            print("", flush=True)
            print("", flush=True)
            if not os.path.exists(path_results):
                os.makedirs(path_results)
            if isinstance(value, dict):
                write_dataframes_to_excel(
                    value, path_results, f"{filename}.xlsx")
            else:
                pd.DataFrame.to_csv(
                    value, os.path.join(path_results, f"{filename}.csv"))
        index += 1


def sort_df_rows_by_another(df1, df2, column_name):
    """
    Sorts rows of df2 based on the ordering of values in df1 for a specified
    column.

    Args:
        df1 (pd.DataFrame): First DataFrame containing the ordering.
        df2 (pd.DataFrame): Second DataFrame to be sorted based on df1.
        column_name (str): The name of the column of interest in both
            DataFrames.

    Returns:
        pd.DataFrame: A new DataFrame sorted according to df1's order.
    """
    ordered_index = df1.set_index(column_name).index
    sorted_df2 = df2.set_index(column_name).loc[
        ordered_index].reset_index()
    return sorted_df2


def sort_df_last_columns(df):
    """
    Sort dataframe columns so that the selected columns appear at the end.
    """
    cols = df.columns.tolist()
    cols_at_the_end = ["case_id", "Stability"]
    for remove_col in cols_at_the_end:
        cols.remove(remove_col)
    for add_col in cols_at_the_end:
        cols.append(add_col)
    df = df[cols]
    return df


def save_results(cases_df, dims_df, execution_logs, output_dataframes,
                 dst_dir):
    """
    Save set of results including the main cases/dims dataframes plus
    execution logs and all elements inside the output_dataframes dictionary,
    mostly dataframes. These dataframe rows must follow the same sorting
    according to the case ids.
    """
    if dst_dir is None:
        dst_dir = ""

    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    cases_df.to_csv(os.path.join(dst_dir, "cases_df.csv"))
    dims_df.to_csv(os.path.join(dst_dir, "dims_df.csv"))

    for key, value in output_dataframes.items():
        if isinstance(value, pd.DataFrame):
            # All dataframes should have the same sorting
            sorted_df = sort_df_rows_by_another(cases_df, value, "case_id")
            # Sort columns at the end
            sorted_df = sort_df_last_columns(sorted_df)
            # Save dataframe
            sorted_df.to_csv(os.path.join(dst_dir, f"case_{key}.csv"))
        else:
            for k, v in value.items():
                if isinstance(v, pd.DataFrame):
                    value.to_csv(os.path.join(dst_dir, f"case_{k}.csv"))
                else:
                    print("Wrong format for output dataframes")

    if execution_logs!=None:
        with open(os.path.join(dst_dir, "execution_logs.txt"), "w") as log_file:
            for log_entry in execution_logs:
                log_file.write("Dimensions:\n")
                for dim in log_entry[0]:
                    log_file.write(f"{dim}\n")
                log_file.write(f"Entropy: {log_entry[1]}\n")
                log_file.write(f"Delta Entropy: {log_entry[2]}\n")
                log_file.write(f"Depth: {log_entry[3]}\n")
                log_file.write("\n")


def get_case_results(T_EIG, d_grid):
    df_op = pd.DataFrame()

    T_buses = d_grid['T_buses']
    for i in T_buses.index:
        bus = T_buses.loc[i, 'bus']
        df_op.loc[0, 'V' + str(bus)] = T_buses.loc[i, 'Vm']
        df_op.loc[0, 'theta' + str(bus)] = T_buses.loc[i, 'theta']

    T_gens = d_grid['T_gen']
    for i in T_gens.index:
        col_name = T_gens.loc[i, 'element'] + str(T_gens.loc[i, 'bus'])
        for var in ['P', 'Q', 'Sn']:
            df_op.loc[0, var + '_' + col_name] = T_gens.loc[i, var]

    T_load = d_grid['T_load']
    for i in T_load.index:
        bus = T_load.loc[i, 'bus']
        df_op.loc[0, 'PL' + str(bus)] = T_load.loc[i, 'P']
        df_op.loc[0, 'QL' + str(bus)] = T_load.loc[i, 'Q']

    # add control parameters

    T_EIG = T_EIG.set_index('mode')
    T_EIG = T_EIG.T
    df_real = T_EIG.loc[['real']].reset_index(drop=True)
    df_imag = T_EIG.loc[['imag']].reset_index(drop=True)
    df_freq = T_EIG.loc[['freq']].reset_index(drop=True)
    df_damp = T_EIG.loc[['damp']].reset_index(drop=True)

    return df_op, df_real, df_imag, df_freq, df_damp


def concat_df_dict(*dicts):
    """
    Receive a list of dictionaries of dataframes and concatenate the dataframes
    to return a unique dictionary of dataframes. Only deal with dataframes
    inside the dictionary, do not handle other types of data.
    Example:
      >> dict_list = [{'a': df1, 'b': df2}, {'a': df3, 'b': df4}]
      >> result_dict = {'a': pd.concat([df1, df3]), 'b': pd.concat([df2, df4])}

    TODO: we can simplify this function now that we do not need to preserve
     the row order on each dataframe, since they are sorted at the end of the
     run thanks to the use of a unique ID per case
    """
    # Return empty dict if all contents are empty
    if all_empty(dicts):
        return {}

    # Consider case of list inside a list
    if isinstance(dicts, Sequence):
        if len(dicts) == 1 and isinstance(dicts[0], Sequence):
            dicts = dicts[0]

    # Collect columns of the different dataframes from the first correct
    # item in the sequence
    cols_dict = {}
    n_subdicts = None
    for d in dicts:
        # Null check
        if not d:
            raise ValueError(
                f"Input must be a list of non-empty dictionaries "
                f"that contain dataframes. Received type {type(d)}.")
        # Check all cases have the same number of sub-dictionaries
        if n_subdicts is not None:
            if n_subdicts != len(d):
                raise ValueError("Differing number of sub-dictionaries while "
                                 "concatenating.")
        else:
            n_subdicts = len(d)
        # Get number of columns from each sub-dict
        if d is None:
            continue
        if isinstance(d, dict):
            for df_label, df in d.items():
                # Skip if columns were already filled
                if df_label in cols_dict:
                    continue
                # Store columns if the dataframe is not empty/undefined
                if isinstance(df, pd.DataFrame) and not df.empty:
                    if df.columns[0] != NAN_COLUMN_NAME:
                        cols_dict[df_label] = df.columns.to_list()
        else:
            raise ValueError("Input must be a list of dictionaries")

    # Concatenate items missing in cols_dict that are all NaN dataframes
    output_dict = {}
    if len(cols_dict) != n_subdicts:
        for d in dicts:
            for df_label, df in d.items():
                # Skip if already in cols_dict: next loop will deal with it
                if df_label in cols_dict:
                    continue
                # Concatenate
                if df_label not in output_dict:
                    output_dict[df_label] = df
                else:
                    output_dict[df_label] = pd.concat(
                        [output_dict[df_label], df], axis=0,
                        ignore_index=True)

    # Do normal concatenation case with well-formed dataframes
    if len(cols_dict) != 0:
        for d in dicts:
            for df_label, cols in cols_dict.items():
                # Get row to be appended
                if d[df_label].columns[0] == NAN_COLUMN_NAME:
                    # 'd' only contains NaN dataframes with no column names
                    n = len(d[df_label])
                    m = len(cols)
                    to_append = pd.DataFrame(np.full((n, m), np.nan),
                                             columns=cols)
                    # Add content of additional columns that may not be NaN
                    if len(d[df_label].columns) > 1:
                        missing_cols_df = d[df_label].drop(NAN_COLUMN_NAME,
                                                           axis=1)
                        to_append[missing_cols_df.columns] = missing_cols_df
                elif isinstance(d, dict):
                    # Normal case: directly append the content of the input df
                    to_append = d[df_label]
                else:
                    raise ValueError(
                        f"Input must be a list of dictionaries of dataframes. "
                        f"Received type {type(d)} with entry '{df_label}' of "
                        f"type {type(d[df_label])}.")

                # Concatenate dataframes
                if df_label not in output_dict:
                    output_dict[df_label] = to_append
                else:
                    output_dict[df_label] = pd.concat(
                        [output_dict[df_label], to_append], axis=0,
                        ignore_index=True)

    return output_dict


def all_empty(data):
    if isinstance(data, (list, tuple)):  # Check for list or tuple
        return all(all_empty(item) for item in data)
    elif isinstance(data, dict):  # Check for dictionary
        # Dict is empty when no keys exist
        return all_empty(list(data.values())) and not data
    else:  # For non-container types, consider them "non-empty" if present
        return False


def parse_setup_file(setup_path):
    # Check setup file path
    if not setup_path:
        current_directory = os.path.dirname(__file__)
        setup_path = os.path.join(current_directory,
                                  "../../setup/default_setup.yaml")
        print (f"Setup file not specified. Using default setup file: "
                f"{setup_path}")
    else:
        print(f"Setup file: {setup_path}")
    if not os.path.exists(setup_path):
        raise FileNotFoundError(f"Setup file {setup_path} not found")

    # Load case parameters
    setup = load_yaml(setup_path)
    n_pf = setup["n_pf"]
    voltage_profile = setup["voltage_profile"]
    v_set = setup["v_set"]
    v_min_v_max_delta_v = setup["v_min_v_max_delta_v"]
    loads_power_factor = setup["loads_power_factor"]
    generators_power_factor = setup["generators_power_factor"]
    n_samples = setup["n_samples"]
    n_cases = setup["n_cases"]
    rel_tolerance = setup["rel_tolerance"]
    max_depth = setup["max_depth"]
    seed = setup["seed"]
    grid_name = setup["grid_name"]
    # Print case configuration
    print(f"\n{''.join(['='] * 30)}\n"
          f"Running application with the following parameters:"
          f"\n{''.join(['='] * 30)}")
    print_dict_as_yaml(setup)
    print()
    return generators_power_factor, grid_name, loads_power_factor, n_cases, \
        n_pf, n_samples, seed, v_min_v_max_delta_v, voltage_profile, v_set, \
        rel_tolerance, max_depth, setup


def parse_args(argv):
    working_dir = None
    path_data = None
    setup_path = None

    args = argv[1:]
    # Do not mix flagged arguments with non-flagged arguments
    i = 0
    use_flag_args = True
    while args:
        arg = args.pop(0)
        if arg.startswith('--working_dir='):
            working_dir = arg.split('=', 1)[1]
        elif arg.startswith('--path_data='):
            path_data = arg.split('=', 1)[1]
        elif arg.startswith('--setup='):
            setup_path = arg.split('=', 1)[1]
        else:
            use_flag_args = False
            if i == 0:
                working_dir = arg
            elif i == 1:
                path_data = arg
            elif i == 2:
                setup_path = arg
        i += 1
    if not use_flag_args:
        print("Using arguments without flags")

    # Check paths
    if not working_dir:
        working_dir = ""
        print(f"Working directory not specified. Using current directory: "
              f"{os.getcwd()}")
    else:
        if not os.path.exists(working_dir):
            raise FileNotFoundError(
                f"Working directory {working_dir} not found")
        else:
            print("Working directory:", working_dir)
    if not path_data:
        path_data = get_data_path()
        print(f"Path data not specified. Using default path: {path_data}")
    else:
        if not os.path.exists(path_data):
            raise FileNotFoundError(f"Path data {path_data} not found")
        else:
            print("Path data:", path_data)

    return working_dir, path_data, setup_path


def load_yaml(content):
    try:
        content = os.path.expanduser(content)
        # Try to interpret content as a file path
        with open(content, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        try:
            # If not a file, try to interpret content as a YAML string
            return yaml.safe_load(content)
        except yaml.YAMLError as exc:
            print(f"Error parsing YAML content: {exc}")
            sys.exit(1)


def generate_unique_id(n):
    """ Return a column dataframe with n unique ids."""
    id_list = [str(uuid.uuid4()) for _ in range(n)]
    return pd.DataFrame(id_list, columns=["case_id"])
