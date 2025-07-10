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

"""This module serves as a comprehensive data generator based on the entropy
of different regions of space. The main objectives are to produce samples
and cases from a given set of dimensions and then evaluate these cases to
determine their stability. Parallel execution is used to evaluate the
stability of each case.
"""
import os

import numpy
import numpy as np
import pandas as pd
import random


from sklearn.ensemble import RandomForestClassifier

from scipy.stats import qmc
from sklearn.preprocessing import StandardScaler

from .utils import check_dims, flatten_list, get_dimension, concat_df_dict, \
    generate_unique_id
from .dimensions import Cell, Dimension
from .viz import plot_divs, plot_stabilities, plot_importances_and_divisions
from ..tests.utils import unique
try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
    from pycompss.api.constraint import constraint
except ImportError:
    from datagen.dummies.task import task
    from datagen.dummies.api import compss_wait_on
    from datagen.dummies.constraint import constraint

from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at, NumericalCircuit

@task(returns=4)
def explore_cell(func, n_samples, entropy, depth, ax, dimensions,
                 cases_heritage_df, dims_heritage_df, use_sensitivity,
                 max_depth, divs_per_cell, generator, feasible_rate, func_params,
                 total_dataframes=None
                 ):
    """Explore every cell in the algorithm while its delta entropy is positive.
    It receives a dataframe (cases_df) and an entropy from its parent, and
    calculates own delta entropy.
    If delta entropy is positive, the cell will subdivide itself according to
    the divisions assigned to each dimension.
    Otherwise, it will return the cases and logs taken until this point.


    :param func: Objective function
    :param n_samples: Number of samples to produce
    :param entropy: Entropy of the father calculated from the cases that fits
    into this cell's space
    :param depth: Recursivity depth
    :param ax: Plottable object
    :param dimensions: Cell dimensions
    :param cases_heritage_df: Inherited cases dataframe
    :param dims_heritage_df: Inherited independent_dims dataframe
    :param use_sensitivity: Boolean indicating whether sensitivity analysis is
    used or not
    :param max_depth: Maximum recursivity depth (it won't subdivide itself if
    exceeded)
    :param dims_heritage_df: Inherited independent_dims dataframe
    :param divs_per_cell: Number of resultant cells from each recursive call
    :param generator: Numpy generator for random values
    :return children_total: List of children dimensions, entropy,
    delta_entropy and depth
    :return cases_df: Concatenation of inherited cases and those produced by
    the cell
    :return dims_df: Concatenation of inherited independent_dims and those produced by
    the cell
    """
    print("New cell", flush=True)
    # Generate samples (n_samples for each dimension)
    samples_df = gen_samples(n_samples, dimensions, generator)
    # Generate cases (n_cases (attribute of the class Dimension) for each dim)
    cases_df, dims_df = gen_cases(samples_df, dimensions, generator)

    stabilities = []
    output_dataframes_list = []
    feasible_cases = 0
    for _, case in cases_df.iterrows():
        stability, output_dataframes = eval_stability(case=case, f=func,
                                                      func_params=func_params,
                                                      dimensions=dimensions,
                                                      generator=generator
                                                      )
        feasible_cases += 1
        stabilities.append(stability)
        output_dataframes_list.append(output_dataframes)

    stabilities = compss_wait_on(stabilities)
    output_dataframes_list = compss_wait_on(output_dataframes_list)
    cases_df["Stability"] = stabilities
    # Collect each cases dictionary of dataframes into total_dataframes
    for output_dfs in output_dataframes_list:
        if total_dataframes:
            total_dataframes = concat_df_dict(total_dataframes,
                                              output_dfs)
        else:
            total_dataframes = output_dfs
    # Remove elements of the dict of dataframes that are not a dataframe
    labels_to_remove = []
    if total_dataframes:
        for label, df in total_dataframes.items():
            if df is not None and type(df) is not pd.DataFrame:
                # Keep None values that work as a placeholder
                labels_to_remove.append(label)
        for label in labels_to_remove:
            total_dataframes.pop(label)

    # Add rectangle to plot axes representing cell borders
    if ax is not None and len(dimensions) == 2:
        plot_stabilities(ax, cases_df, dims_df)

    cases_df = pd.concat([cases_df, cases_heritage_df], ignore_index=True)
    dims_df = pd.concat([dims_df, dims_heritage_df], ignore_index=True)

    entropy, delta_entropy = eval_entropy(stabilities, entropy)

    total_cases = n_samples * dimensions[0].n_cases
    # Finish recursivity if entropy decreases or cell become too small
    if (delta_entropy < 0 or not check_dims(dimensions) or depth >= max_depth or
            feasible_cases/total_cases < feasible_rate):
        print("Stopped cell:")
        print("    Entropy: ", entropy)
        print("    Delta entropy: ", delta_entropy)
        print("    Depth: ", depth)
        return ((dimensions, entropy, delta_entropy, depth), cases_df, dims_df,
                total_dataframes)
    else:
        if use_sensitivity:
            dimensions = sensitivity(cases_df, dimensions, divs_per_cell, generator)
        children_grid = gen_grid(dimensions)

        if ax is not None and len(dimensions) == 2:
            plot_divs(ax, children_grid)

        cases_df, dims_df, children_total, total_dataframes = (
            explore_grid(ax=ax, cases_df=cases_df, grid=children_grid,
                         depth=depth, dims_df=dims_df, func=func,
                         n_samples=n_samples, use_sensitivity=use_sensitivity,
                         max_depth=max_depth, divs_per_cell=divs_per_cell,
                         generator=generator, feasible_rate=feasible_rate,
                         func_params=func_params, dataframes=total_dataframes))
        return children_total, cases_df, dims_df, total_dataframes


def explore_grid(ax, cases_df, grid, depth, dims_df, func, n_samples,
                 use_sensitivity, max_depth, divs_per_cell, generator,
                 feasible_rate, func_params, dataframes):
    """
    For a given grid (children grid) and cases taken, this function is in
    charge of distributing those samples among those cells and, finally,
    retrieving its results.

    :param ax: Plottable object
    :param cases_df: Concatenation of inherited cases and those produced by
    the cell
    :param grid: Children grid
    :param depth: Recursivity depth
    :param dims_df: Samples dataframe(one for each case)
    :param func: Objective function
    :param n_samples: Number of samples to produce
    :param use_sensitivity: Boolean indicating whether sensitivity analysis is
    used or not
    :param max_depth: Maximum recursivity depth (it won't subdivide itself if
    exceeded)
    :param divs_per_cell: Number of resultant cells from each recursive call
    :param generator: Numpy generator for random values
    :return: Children independent_dims, cases and parameters
    """
    total_cases_df, total_dims_df, total_dataframes, total_entropies = (
        get_children_parameters(grid, dims_df, cases_df, dataframes))
    children_total_params = []
    list_cases_children_df = []
    list_dims_children_df = []
    list_dataframes_children = []
    for (children_cell, cases_heritage_df, dims_heritage_df,
         heritage_dataframes, entropy_children) \
            in zip(grid, total_cases_df, total_dims_df, total_dataframes,
                   total_entropies):
        dim = children_cell.dimensions
        (child_total_params, cases_children_df, dims_children_df,
         children_dataframes) = (
            explore_cell(func=func, n_samples=n_samples,
                         entropy=entropy_children, depth=depth + 1, ax=ax,
                         dimensions=dim, cases_heritage_df=cases_heritage_df,
                         dims_heritage_df=dims_heritage_df,
                         use_sensitivity=use_sensitivity,
                         max_depth=max_depth, divs_per_cell=divs_per_cell,
                         generator=generator, feasible_rate=feasible_rate,
                         func_params=func_params,
                         total_dataframes=heritage_dataframes))

        children_total_params.append(child_total_params)
        list_cases_children_df.append(cases_children_df)
        list_dims_children_df.append(dims_children_df)
        list_dataframes_children.append(children_dataframes)

    children_total_params = compss_wait_on(children_total_params)
    list_cases_children_df = compss_wait_on(list_cases_children_df)
    list_dims_children_df = compss_wait_on(list_dims_children_df)
    list_dataframes_children = compss_wait_on(list_dataframes_children)

    cases_df = pd.concat(list_cases_children_df, ignore_index=True)
    dims_df = pd.concat(list_dims_children_df, ignore_index=True)
    children_total_params = flatten_list(children_total_params)
    dataframes = concat_df_dict(list_dataframes_children)

    return cases_df, dims_df, children_total_params, dataframes


def generate_columns(dim):
    """Assigns names for every variable in a dimension.

    :param dim: Involved dimension
    :return: Names of de variable_borders
    """
    if (isinstance(dim.variable_borders, numpy.ndarray) and
            not np.all(np.isnan(dim.variable_borders))):
        return [f"{dim.label}_Var{v}" for v in
                range(len(dim.variable_borders))]
    else:
        if dim.values:
            return [f"{dim.label}_Var{v}" for v in range(len(dim.values))]
        else:
            return None

def process_p_cig_dimension(samples_df, p_cig, generator):
    """ Assigns values to g_for and g_fol dimensions.

    p_cig samples values must be distributed between g_for and g_fol assigning
    a random value between 0 and 1 as a one-to-one percentage, resulting in
    g_for plus g_fol equalling p_cig. g_for variable_borders are calculated as usual,
    while g_fol variable_borders are complimentary to g_for to sum g_fol:
        g_fol_i = p_cig_i - g_for_i

    :param generator: Random number generator
    :param samples_df: Involved samples
    :param p_cig: p_cig dimension
    :return: Cases obtained and samples extended (one sample for each case)
    """
    cases = []
    dims = []

    for _, sample in samples_df.iterrows():
        # Obtain p_cig cases
        cases_p_cig_df = pd.DataFrame(
            p_cig.get_cases_extreme(sample[p_cig.label], generator),
            columns=generate_columns(p_cig)).dropna()
        n_rows = len(cases_p_cig_df)
        dims_p_cig_df = pd.DataFrame(
            np.repeat(sample[p_cig.label], n_rows), columns=[p_cig.label])

        # Obtain the complimentary g_for and g_fol percentages
        grid_forming_perc = sample["perc_g_for"]
        g_for_sample = sample["p_cig"] * grid_forming_perc
        g_fol_sample = sample["p_cig"] - g_for_sample

        # Obtain g_for and g_fol cases
        cases_g_for = []
        cases_g_fol = []
        dims_g_for = []
        dims_g_fol = []
        for i in range(len(cases_p_cig_df)):
            # Compose g_for dimension
            # Pick bounds of each variable. The min value is p_cig dimension's
            # min bound, and max is the value sampled for ith p_cig's variable

            # g_for_variables = np.array([
            #     (p_cig.variable_borders[x, 0], cases_p_cig_df.iloc[i, x])
            #     for x in range(len(p_cig.variable_borders))])
            g_for_variables = np.array([
                (0, cases_p_cig_df.iloc[i, x])
                for x in range(len(p_cig.variable_borders))])
            g_for = Dimension(variable_borders=g_for_variables, n_cases=1, divs=1,
                              borders=(p_cig.borders[0], sample[p_cig.label]),
                              label="p_g_for", tolerance=p_cig.tolerance)
            # Create g_for case
            case_g_for = (g_for.get_cases_extreme(g_for_sample, generator))[0]
            if not np.isnan(case_g_for).any():
                # dims_g_for.append(g_for_sample)
                # cases_g_for.append(case_g_for)
                # dims_g_fol.append(g_fol_sample)
                # Compose g_fol subtracting p_cig from g_for case variable_borders
                # cases_g_fol.append(
                #     [cases_p_cig_df.iloc[i, x] - case_g_for[x] if cases_p_cig_df.iloc[i, x] - case_g_for[x] >1e-3 else 0
                #      for x in range(len(p_cig.variable_borders))])
                case_g_fol=[]
                for x in range(len(p_cig.variable_borders)):
                    if cases_p_cig_df.iloc[i, x] - case_g_for[x] >1e-3:
                        case_g_fol.append(cases_p_cig_df.iloc[i, x] - case_g_for[x])
                    else:
                        case_g_fol.append(0)
                        case_g_for[x]=case_g_for[x]+cases_p_cig_df.iloc[i, x] - case_g_for[x]
                dims_g_for.append(g_for_sample)
                cases_g_for.append(case_g_for)
                dims_g_fol.append(g_fol_sample)
                cases_g_fol.append(np.array(case_g_fol).ravel())





        cases_g_for_df = pd.DataFrame(
            cases_g_for,
            columns=[f"p_g_for_Var{v}" for v in range(len(p_cig.variable_borders))])
        dims_g_for_df = pd.DataFrame(dims_g_for, columns=["p_g_for"])
        cases_g_fol_df = pd.DataFrame(
            cases_g_fol,
            columns=[f"p_g_fol_Var{v}" for v in range(len(p_cig.variable_borders))])
        dims_g_fol_df = pd.DataFrame(dims_g_fol, columns=["p_g_fol"])

        # Error check
        check_sum = (cases_g_fol_df.sum(axis=1) + cases_g_for_df.sum(axis=1)
                     - cases_p_cig_df.sum(axis=1)).to_numpy()
        if not np.isclose(check_sum, 0).all():
            raise ValueError("Sum of p_g_for and p_g_fol must equal p_cig")

        # Concat p_cig, g_for and g_fol into a complete case dataframe
        sample_cases_df = pd.concat(
            [cases_p_cig_df, cases_g_for_df, cases_g_fol_df], axis=1)
        sample_dims_df = pd.concat(
            [dims_p_cig_df, dims_g_for_df, dims_g_fol_df], axis=1)

        # Concat samples and cases of p_cig, g_for and g_fol
        sample_cases_df = sample_cases_df.dropna().reset_index(drop=True)
        sample_dims_df = sample_dims_df.dropna().reset_index(drop=True)

        cases.append(sample_cases_df)
        dims.append(sample_dims_df)

    cases_df = pd.concat(cases, axis=0, ignore_index=True)
    dims_df = pd.concat(dims, axis=0, ignore_index=True)
    return cases_df, dims_df


def process_p_load_dimension(samples_df, dim):
    total_cases = []
    total_dim = []
    for _, sample in samples_df.iterrows():
        # TODO: poner el factor de escala de la carga en el setup file
        new_sample = (sample["p_sg"] + sample["p_cig"])*0.9
        cases = [[new_sample * value for value in dim.values]
                 for _ in range(dim.n_cases)]
        for case in cases:
            if not np.isnan(case).any():
                total_cases.append(case)
                total_dim.append(new_sample)

    dims_df = pd.DataFrame(total_dim, columns=[dim.label])
    cases_df = pd.DataFrame(total_cases, columns=generate_columns(dim))
    return cases_df, dims_df

def process_control_dimension(samples_df, dim):
    total_cases = []
    total_dim = []
    for _, sample in samples_df.iterrows():
        cases = [[sample[dim.label]]
                 for _ in range(dim.n_cases)]
        for case in cases:
            if not np.isnan(case).any():
                total_cases.append(case)
                total_dim.append(case)

    dims_df = pd.DataFrame(total_dim, columns=[dim.label])
    cases_df = pd.DataFrame(total_cases, columns=[dim.label])
    return cases_df, dims_df


def process_other_dimensions(samples_df, dim, generator):
    """
    This method assigns values to the variable_borders within a generic dimension.

    :param generator:
    :param samples_df: Dataframe containing every sample in this cell
    :param dim: Involved dimension
    :return: Cases obtained and samples extended (one sample for each case)
    """
    total_cases = []
    total_dim = []
    for _, sample in samples_df.iterrows():
        cases = dim.get_cases_extreme(sample[dim.label], generator)
        for case in cases:
            if not np.isnan(case).any():
                total_cases.append(case)
                total_dim.append(sample[dim.label])

    dims_df = pd.DataFrame(total_dim, columns=[dim.label])
    cases_df = pd.DataFrame(total_cases, columns=generate_columns(dim))
    return cases_df, dims_df


def gen_cases(samples_df, dimensions, generator):
    """Produces sum combinations of the samples given. Each sample sum
    combination is called a "case".

    :param generator:
    :param samples_df: Involved samples (dataframe)
    :param dimensions: Involved dimensions
    :return cases_df: Samples-driven produced cases dataframe
    :return dims_df: Samples dataframe(one for each case)
    """
    total_cases = []
    total_dims = []

    for dim in dimensions:
        if dim.label == "p_cig":
            partial_cases, partial_dims = process_p_cig_dimension(samples_df,
                                                                  dim, generator)
        elif dim.label == "p_load":
            partial_cases, partial_dims = process_p_load_dimension(samples_df,
                                                                   dim)
        elif dim.label.startswith("tau"):
            partial_cases, partial_dims = process_control_dimension(samples_df,
                                                                   dim)
        else:
            partial_cases, partial_dims = process_other_dimensions(samples_df,
                                                                   dim, generator)

        # Add a new column for each p_ column in partial_cases
        for col in partial_cases.columns:
            if col.startswith("p_"):
                new_col_name = col.replace("p_", "q_")
                multiplier = np.sqrt(1 - dim.cosphi ** 2) / dim.cosphi
                partial_cases[new_col_name] = partial_cases[col] * multiplier

        sum_columns_by_prefix = partial_cases.T.groupby(
            lambda x: x.split("_Var")[0]).sum().T
        q_columns = sum_columns_by_prefix.filter(regex=r'^q_', axis=1)
        partial_dims = pd.concat([partial_dims, q_columns], axis=1)

        total_cases.append(partial_cases)
        total_dims.append(partial_dims)

    total_cases_df = pd.concat(total_cases, axis=1)
    total_dims_df = pd.concat(total_dims, axis=1)

    # Generate unique ID per case
    id_df = generate_unique_id(len(total_cases_df))
    total_cases_df = pd.concat((total_cases_df, id_df), axis=1)
    total_dims_df = pd.concat((total_dims_df, id_df), axis=1)
    return total_cases_df, total_dims_df


def gen_samples(n_samples, dimensions, generator):
    """Generates n_samples samples, which represent total sum of the variable_borders
    within a dimension.

    :param generator:
    :param n_samples: Number of samples to produce
    :param dimensions: Involved dimensions
    :return: DataFrame containing these samples with columns named after
    dimension labels
    """
    indepedent_dims = [dim for dim in dimensions if dim.independent_dimension]
    sampler = qmc.LatinHypercube(d=len(indepedent_dims), seed=generator)
    samples = sampler.random(n=n_samples)

    lower_bounds = np.array([dim.borders[0] for dim in indepedent_dims])
    upper_bounds = np.array([dim.borders[1] for dim in indepedent_dims])

    samples_scaled = lower_bounds + samples * (upper_bounds - lower_bounds)

    df_samples = pd.DataFrame(samples_scaled,
                              columns=[dim.label for dim in indepedent_dims])

    return df_samples


def sensitivity(cases_df, dimensions, divs_per_cell, generator):
    """This Sensitivity analysis is done by gathering cases and their
    evaluated outputs, then train a Random Forest, getting the importance of
    each variable in the decision. Each variable's division count is
    initialized at 1. In a loop, iterated as many times as specified, we double
    the number of subdivisions for the most influential variable and halve its
    importance.

    :param generator:
    :param cases_df: Involved cases
    :param dimensions: Involved dimensions
    :param divs_per_cell: Number of resultant cells from each recursive call
    :return: Divisions for each dimension
    """
    labels = [dim.label for dim in dimensions if dim.independent_dimension]
    dims_df = pd.DataFrame()
    for label in labels:
            matching_columns = (
                cases_df.filter(regex=r'^' + label + r'_*', axis=1).sum(axis=1))
            dims_df[label] = matching_columns
    dims_df.columns = labels
    x = np.array(dims_df)
    y = np.array(cases_df["Stability"])
    y = y.astype('int')

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)

    random_state = generator.integers (0,2**32 - 1)
    model = RandomForestClassifier(random_state=random_state)
    model.fit(x_scaled, y)

    importances = model.feature_importances_
    for d in dimensions:
        d.divs = 1
    splits_per_cell = int(np.round(np.log2(divs_per_cell)))

    for _ in range(splits_per_cell):
        # plot_importances_and_divisions(dimensions, importances)
        index_max_importance = np.argmax(importances)
        label_max_importance = list(labels)[index_max_importance]
        dim_max_importance = get_dimension(label_max_importance, dimensions)

        if ((dim_max_importance.borders[1] - dim_max_importance.borders[0]) /
                dim_max_importance.divs < dim_max_importance.tolerance):
            importances[index_max_importance] = 0

        if importances[index_max_importance] != 0:
            dim_max_importance.divs *= 2
            importances[index_max_importance] /= 2
    # plot_importances_and_divisions(dimensions, importances)
    return dimensions


@constraint(computing_units=os.environ.get('COMPUTING_UNITS', '1'))
@task(returns=2)
def eval_stability(case, f, func_params, **kwargs):
    """Call objective function and return its result.

    :param case: Involved cases
    :param f: Objective function
    :param kwargs: Additional keyword arguments
    :return: Result of the evaluation
    """
    return f(case=case, func_params=func_params, **kwargs)



def gen_grid(dimensions):
    """
    Generate grid. Every cell is made out of a list of the Dimension objects
    involved in the problem, with the only difference that the lower and upper
    bounds change for each cell.

    :param dimensions: Involved dimensions
    :return: Grid
    """
    independent_dims_subdv = [dim for dim in dimensions if dim.independent_dimension if dim.divs > 1]
    independent_dims_no_subdv = [dim for dim in dimensions if dim.independent_dimension if dim.divs == 1]
    dependent_dims = [dim for dim in dimensions if not dim.independent_dimension]
    n_dims = len(independent_dims_subdv)
    ini = tuple(dim.borders[0] for dim in independent_dims_subdv if dim.divs > 1)
    fin = tuple(dim.borders[1] for dim in independent_dims_subdv if dim.divs > 1)
    div = tuple(dim.divs for dim in independent_dims_subdv if dim.divs > 1)
    total_div = np.prod(div)
    grid = []
    for i in range(total_div):
        div_indices = np.unravel_index(i, div)
        lower = [
            ini[j] + (fin[j] - ini[j]) / div[j] * div_indices[j]
            for j in range(n_dims)]
        upper = [
            ini[j] + (fin[j] - ini[j]) / div[j] * (div_indices[j] + 1)
            for j in range(n_dims)
        ]
        dims = []
        for j in range(len(independent_dims_subdv)):
            dims.append(
                Dimension(
                    variable_borders=independent_dims_subdv[j].variable_borders,
                    n_cases=independent_dims_subdv[j].n_cases,
                    divs=independent_dims_subdv[j].divs,
                    borders=(lower[j], upper[j]),
                    label=independent_dims_subdv[j].label,
                    tolerance=independent_dims_subdv[j].tolerance,
                    cosphi=independent_dims_subdv[j].cosphi)
            )
        dims.extend(independent_dims_no_subdv)
        dims.extend(dependent_dims)
        grid.append(Cell(dims))
    return grid


def calculate_entropy(freqs):
    """Obtain cell entropy from stability and non-stability frequencies.

    :param freqs: two-element list with the frequency (1-based) of stable and
    non-stable cases, respectively
    :return: Entropy
    """
    cell_entropy = 0
    for i in range(len(freqs)):
        if freqs[i] != 0:
            cell_entropy = cell_entropy - freqs[i] * np.log(freqs[i])
    return cell_entropy


def eval_entropy(stabilities, entropy_parent):
    """Calculate entropy of the cell using its list of stabilities.

    :param stabilities: List of stabilities (result of the evaluation of every
    case)
    :param entropy_parent: Parent entropy based on concrete cases (those which
    correspond to the cell)
    :return: Entropy and delta entropy
    """
    freqs = []
    counter = 0
    for stability in stabilities:
        if stability == 1:
            counter += 1
    freqs.append(counter / len(stabilities))
    freqs.append((len(stabilities) - counter) / len(stabilities))
    entropy = calculate_entropy(freqs)
    if entropy_parent is None:
        delta_entropy = 1
    else:
        delta_entropy = entropy - entropy_parent
    return entropy, delta_entropy


def get_children_parameters(children_grid, dims_heritage_df, cases_heritage_df,
                            heritage_dataframes):
    """Obtains dimensions, cases_df, entropy and delta_entropy of each child

    :param children_grid: Grid to obtain parameters
    :param dims_heritage_df: Samples dataframe(one for each case)
    :param cases_heritage_df: Inherited cases dataframe
    :return: List of children (with these attributes set)
    """
    total_cases = []
    total_dims = []
    total_entropies = []
    total_dataframes = []
    for cell in children_grid:
        dims = []
        cases = []
        dataframes = {}
        for idx, row in dims_heritage_df.iterrows():
            # Cell dimensions don't include g_for and g_fol, but dims_df do
            if 'p_g_for' in row.index and 'p_g_fol' in row.index:
                if not isinstance(row, pd.Series):
                    raise TypeError("Row is not a pd.Series object")
                columns_to_drop = ['p_g_for', 'p_g_fol', 'p_load']
                q_columns = row.filter(regex=r'^q_')
                columns_to_drop.extend(q_columns.index)
                row = row.drop(labels=columns_to_drop)

            # Check if every dimension in row is within cell borders
            cell_independent_dims = [dim for dim in cell.dimensions
                               if dim.independent_dimension]
            cell_borders = [cell_independent_dims[t].borders
                            for t in range(len(cell_independent_dims))]
            belongs = all(cell_borders[t][0] <= row.iloc[t] <= cell_borders[t][1]
                          for t in range(len(cell_independent_dims)))
            if belongs:
                cases.append(cases_heritage_df.iloc[[idx], :])
                dims.append(dims_heritage_df.iloc[[idx], :])
                if heritage_dataframes:
                    for label in heritage_dataframes.keys():
                        # If the dataframe is not empty, concatenate it
                        if label in dataframes.keys():
                            dataframes[label] = (
                                pd.concat([dataframes[label],
                                           heritage_dataframes[label].iloc[[idx], :]],
                                          axis=0))
                        else:
                            dataframes[label] = heritage_dataframes[label].iloc[
                                                [idx], :]

        if cases and dims:
            stabilities = [int(case["Stability"].iloc[0]) for case in cases]
            entropy, _ = eval_entropy(stabilities, None)
            cases_df = pd.concat(cases, axis=0, ignore_index=True)
            dims_df = pd.concat(dims, axis=0, ignore_index=True)
        else:
            entropy = None
            cases_df = pd.DataFrame()
            dims_df = pd.DataFrame()
        total_cases.append(cases_df)
        total_dims.append(dims_df)
        total_entropies.append(entropy)
        total_dataframes.append(dataframes)

    if cases_heritage_df is None:
        cases_heritage_df = pd.DataFrame()
    if sum([len(cases) for cases in total_cases]) != len(cases_heritage_df):
        raise Exception("Not every case was assigned to a child")
    return total_cases, total_dims, total_dataframes, total_entropies


def gen_voltage_profile(vmin,vmax,delta_v,d_raw_data,slack_bus,GridCal_grid,generator):

    # Find Index of slack bus
    i_slack_bus= d_raw_data['results_bus'].query('I==@slack_bus').index[0]

    # Assign random voltage to slack bus
    V = generator.random() * (vmax - vmin) + vmin
    # d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @slack_bus').index[0],'V']=V

    # Initialize voltage matrix
    # adj_matrix=GridCal_grid.get_adjacent_matrix()
    main_circuit=compile_numerical_circuit_at(GridCal_grid)
    C=main_circuit.Cf+main_circuit.Ct
    adj_matrix=C.T.dot(C)


    # Find buses adjacents to slack_bus
    idx_adj_buses=list(GridCal_grid.get_adjacent_buses(adj_matrix, int(i_slack_bus)))
    adj_buses= d_raw_data['results_bus'].loc[idx_adj_buses,'I']

    # Relation table between index and ID for all the nodes
    indx_id=np.zeros([len(d_raw_data['results_bus']),2])
    indx_id[:,0]=d_raw_data['results_bus'].index
    indx_id[:,1]=d_raw_data['results_bus']['I']


    # initialize generators_id and generators_index
    generators_id = d_raw_data['generator']['I'].tolist()
    generators_index_list = []
    for row in indx_id:
        if row[1] in generators_id:
            generators_index_list.append(row[0])


    # Choose start parameters
    start_node = i_slack_bus
    pending = [start_node]
    # node: distancia, num_modificacions 
    distances = {start_node:[0,1]}
    # Initialize a row to store de voltages calculated, with a length equal to the number of nodes
    voltages = [0]*len(indx_id)
    voltages[start_node]=V

    while len(pending)>0:
        to_calculate = []
        current_node = pending[0]
        current_node_distance = distances[current_node][0]
        adjacent_nodes_list = list(GridCal_grid.get_adjacent_buses(adj_matrix, int(current_node)))
        for adjacent_node in adjacent_nodes_list:
            if adjacent_node != current_node:
        # for adjacent_node, num in enumerate(adj_matrix[current_node]):
            # if num == 1:
                adjacent_node_distance = distances.get(adjacent_node, None)
                if adjacent_node_distance is None :
                    to_calculate.append(adjacent_node)
                    pending.append(adjacent_node)
                    distances[adjacent_node]=[current_node_distance+1,0]
                elif adjacent_node_distance[0] > current_node_distance:
                    to_calculate.append(adjacent_node)
        for adjacent_node in to_calculate:
            calculate_voltage(adjacent_node, current_node, delta_v, distances, generators_index_list, voltages, vmin, vmax, generator)
    #    print(f"El node {current_node} donara a {to_calculate}")
        current_bus=d_raw_data['results_bus'].loc[current_node,'I']
        to_calculate_bus=list(d_raw_data['results_bus'].loc[to_calculate,'I'])
        # print(f"El bus {current_bus} donara a {to_calculate_bus}")
        pending.pop(0)
        # print(voltages)
    # print(distances)

    return voltages, indx_id

def calculate_voltage(adjacent_node, current_node, delta_v, distances, generators_index_list, voltages, vmin, vmax, generator):
    # Aumento en una unitat el nombre de modificacions
    distances[adjacent_node][1]+=1
    num_modifications = distances[adjacent_node][1]
    # Miro si el node contigu es generador
    if adjacent_node in generators_index_list:
        V = generator.random() * (delta_v + delta_v) -delta_v + voltages[current_node]
        if num_modifications == 1:
            V_adjacent_node = V
        elif num_modifications > 1:
            V_adjacent_node = (num_modifications-1)*(voltages[adjacent_node]/num_modifications) + V/num_modifications
        if V_adjacent_node < vmin:
            voltages[adjacent_node]=vmin
        elif V_adjacent_node > vmax:
            voltages[adjacent_node]=vmax
        else:
            voltages[adjacent_node]=V_adjacent_node
    else:
        voltages[adjacent_node]=voltages[current_node]

