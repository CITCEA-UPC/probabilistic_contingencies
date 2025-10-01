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

"""This module is the main entry point for the application. The main
goal is to explore the various cells (or combinations of dimensions) and
produce both a record of execution logs and a DataFrame containing specific
cases and their associated stability."""
import random

import numpy as np
import pandas as pd

from .sampling import explore_cell
from .viz import print_results, boxplot
from .utils import clean_dir, save_results

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
except ImportError:
    from datagen.datagen.dummies.task import task
    from datagen.datagen.dummies.api import compss_wait_on


def start(dimensions, n_samples, rel_tolerance, func, max_depth, dst_dir="",
          seed=None, use_sensitivity=False, ax=None, divs_per_cell=2, plot_boxplot=False,
          feasible_rate=0.5, func_params = {}):
    """In this method we work with dimensions (main axes), which represent a
    list of variable_borders. For example, the value of each variable of a concrete
    dimension could represent the power supplied by a generator, while the
    value linked to that dimension should be the total sum of energy produced.

    The function explores each initial cells and obtains two objects from it:
        -execution_logs: dimensions, entropy, delta entropy and depth of each
                        cell.
        -cases_df: dataframe containing each case and associated stability
                taken during the execution.

    :param seed:
    :param divs_per_cell:
    :param dimensions: List of dimensions involved
    :param n_samples: Number of different values for each dimension
    :param rel_tolerance: Fraction of the dimension's range that will be used
        as the minimum size of new cells in grid generation. 
        e.g., if rel_tolerance = 0.1 the dimension's tolerance will be 10 % of
        its range
    :param ax: Plottable object
    :param use_sensitivity: Boolean indicating whether sensitivity analysis is
    used or not
    :param func: Objective function
    :param max_depth: Maximum depth for a cell to be subdivided
    :param plot_boxplot: Indicates whether a boxplot representing all variable_borders
    should be plotted
    """
    clean_dir("results")
    if ax is not None and len(dimensions) == 2:
        clean_dir("results/figures")

    for dim in dimensions:
        if dim.independent_dimension:
            dim.tolerance = (dim.borders[1] - dim.borders[0]) * rel_tolerance

    if ax is not None and len(dimensions) == 2:
        x_lims = (dimensions[0].borders[0], dimensions[0].borders[1])
        y_lims = (dimensions[1].borders[0], dimensions[1].borders[1])
        ax.set_xlim(left=x_lims[0], right=x_lims[1])
        ax.set_ylim(bottom=y_lims[0], top=y_lims[1])

    if seed is None:
        seed = random.randint(1,100)

    generator = np.random.default_rng(seed)
    execution_logs, cases_df, dims_df, output_dataframes = (
        explore_cell(func=func, n_samples=n_samples, entropy=None, depth=0,
                     ax=ax, dimensions=dimensions, cases_heritage_df=None,
                     dims_heritage_df=pd.DataFrame(),
                     use_sensitivity=use_sensitivity, max_depth=max_depth,
                     divs_per_cell=divs_per_cell, generator=generator,
                     feasible_rate=feasible_rate, func_params=func_params))
    execution_logs = compss_wait_on(execution_logs)
    cases_df = compss_wait_on(cases_df)
    dims_df = compss_wait_on(dims_df)
    output_dataframes = compss_wait_on(output_dataframes)
    if not isinstance(execution_logs, list):
        execution_logs = [execution_logs]

    if plot_boxplot:
        boxplot(cases_df)
    print_results(execution_logs, cases_df)
    save_results(cases_df, dims_df, execution_logs, output_dataframes, dst_dir)

    return cases_df, dims_df, execution_logs, output_dataframes

