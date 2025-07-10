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

"""This module is responsible for visualization-related functionality. It
provides functions to print detailed information about each cell's
dimensions and the results obtained during the exploration. It helps in
understanding and visualizing the stability of each case, the entropy,
delta entropy, and depth of the explored cells. Additionally, there's a
function to plot sample data.
"""
import os
import time
import pandas as pd
from matplotlib import pyplot as plt, patches


def plot_importances_and_divisions(dimensions, importances):
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    labels = [f'Dimension {i}' for i in range(len(dimensions))]
    plt.bar(labels, importances)
    plt.ylim(0, 0.4)
    plt.xlabel('Dimensions')
    plt.ylabel('Importance')
    plt.title('Dimensions importances')

    plt.subplot(1, 2, 2)
    divisions = [dim.divs for dim in dimensions]
    plt.bar(labels, divisions)
    plt.ylim(0, 4)
    plt.xlabel('Dimensions')
    plt.ylabel('Divisions')
    plt.title('Dimensions divisions')

    plt.tight_layout()
    plt.show()


def plot_stabilities(ax, cases_df, dims_df):
    time.sleep(1)
    for idx, dim_row in dims_df.iterrows():
        color = 'green' if cases_df.loc[idx, 'Stability'] == 1 else 'red'
        ax.scatter(dim_row[0], dim_row[1], color=color, edgecolors='black')

    dir_path = "results/figures"
    file_name = format(time.time(), '.0f') + ".png"
    path = os.path.join(dir_path, file_name)
    ax.figure.savefig(fname=path, dpi=300)


def plot_divs(ax, children_grid):
    time.sleep(1)
    for cell in children_grid:
        dim0 = (cell.dimensions[0].borders[0], cell.dimensions[0].borders[1])
        dim1 = (cell.dimensions[1].borders[0], cell.dimensions[1].borders[1])
        cell = patches.Rectangle((dim0[0], dim1[0]), dim0[1] - dim0[0],
                                 dim1[1] - dim1[0], linewidth=1,
                                 edgecolor='black', facecolor='none')
        ax.add_patch(cell)
    dir_path = "results/figures"
    file_name = format(time.time(), '.0f') + ".png"
    path = os.path.join(dir_path, file_name)
    ax.figure.savefig(fname=path, dpi=300)


def boxplot(cases_df):
    labels = list(set(
        col.rsplit('_Var')[0] for col in cases_df.columns if '_Var' in col))
    dims = {}

    for label in labels:
        matching_columns = cases_df.filter(regex=f'^{label}_', axis=1)
        dims[label] = matching_columns

    for dim, variables in dims.items():
        fig, ax = plt.subplots(1, 1, figsize=(12, 4))
        boxplot_data = [variables[var].dropna() for var in variables]
        ax.boxplot(boxplot_data)
        ax.set_title(dim)
        labels = [str(i) for i in range(variables.shape[1])]
        ax.set_xticklabels(labels)
        dir_path = "results/figures"
        file_name = "boxplot_" + dim + ".png"
        path = os.path.join(dir_path, file_name)
        plt.savefig(fname=path, dpi=300)


def print_grid(grid):
    """Shows each cell's dimensions

    :param grid: list of cells
    """
    print("")
    for i in range(len(grid)):
        print("------", "casilla", i, "------")
        print("samples casilla", grid[i].n_samples)
        for j in grid[i].dimensions:
            print("        variable_borders:", j.variable_borders)
            print("        cases", j.n_cases)
            print("        divisiones", j.divs)
            print("        limites", j.borders)
            print("")
        print("")
        print("")


def print_results(execution_logs, cases_df):
    """Shows the dataframe obtained by the application and the logs for each
    cell: dimensions, entropy, delta entropy and depth

    :param execution_logs: dimensions, entropy, delta entropy and depth of each
                        cell.
    :param cases_df: dataframe containing every case evaluated by the program
                and each evaluation (stability)
    """
    pd.set_option('display.max_rows', 50)
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    print("")
    print("")
    print("samples-stability:")
    print(cases_df)
    print("")
    print("number of cells: ", len(execution_logs))

    for r in execution_logs:
        print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$", flush=True)
        print(r, flush=True)
        print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$", flush=True)
        #print("dimensions: ", r[0])
        print("entropy: ", r[1])
        print("delta entropy: ", r[2])
        print("depth: ", r[3])
        print("")
        print("")


def plot_sample(ax, x, y, z):
    ax.scatter(x, y, z)


def print_dict_as_yaml(d, indent=0):
    """ Recursively print a dictionary in a YAML-like format. """
    for key, value in d.items():
        # Create indentation based on the current nesting level
        prefix = '  ' * indent
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            print_dict_as_yaml(value, indent + 1)
        else:
            # For simple values, print key-value pair
            print(f"{prefix}{key}: {value}")
