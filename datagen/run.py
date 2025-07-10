
import numpy as np
from matplotlib import pyplot as plt

from datagen.src.dimensions import Dimension
from datagen.src.start_app import start
from datagen.src.objective_function import dummy

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
except ImportError:
    from datagen.dummies.task import task
    from datagen.dummies.api import compss_wait_on


@task()
def main():
    """
    In this method we work with dimensions (main axes), which represent a
    list of variable_borders. For example, the value of each variable of a concrete
    dimension could represent the power supplied by a generator, while the
    value linked to that dimension should be the total sum of energy produced.

    For each dimension it must be declared:
        -variable_borders: list of variable_borders represented by tuples containing its
                lower and upper borders.
        -n_cases: number of cases taken for each sample (each sample represents
                the total sum of a dimension). A case is a combination of
                variable_borders where all summed together equals the sample.
        -divs: number of divisions in that dimension. It will be the growth
                order of the number of cells
        -lower: lower bound of the dimension (minimum value of a sample)
        -upper: upper bound of the dimension (maximum value of a sample)
        -label: dimension identifier
        -independent_dimension: indicates whether the dimension is true (sampleable) or not.

    Apart from that, it can also be specified the number of samples and
    the relative tolerance (indicates the portion of the size of the original
    dimension). For example, if we have a dimension of size 10 and relative
    tolerance is 0.5, the smallest cell in this dimension will have size 5.
    Lastly, user should provide the objective function. As optional parameters,
    the user can define:
        -use_sensitivity: a boolean indicating whether sensitivity analysis is
        used or not.
        -ax: plot axes in case it is desired to show stability points and cells
        divisions (dimensions length must be 2). Plots saved in
        "datagen/results/figures".
        -plot_boxplot: a boolean indicating whether boxplots for each variable
        must be obtained or not. Plots saved in "datagen/results/figures".
    """

    p_sg = [(0, 2), (0, 1.5), (0, 1.5)]
    p_cig = [(0, 1), (0, 1.5), (0, 1.5), (0, 2)]
    perc_g_for = [(0,1)]
    tau_f_g_for = [(0., 2)]
    tau_v_g_for = [(0., 2)]
    tau_p_g_for = [(0., 2)]
    tau_q_g_for = [(0., 2)]
    n_samples = 3
    n_cases = 3
    cosphi = 0.5
    d_raw_data = "d_raw_data"
    d_op = "d_op"
    GridCal_grid = "GridCal_grid"
    d_grid = "d_grid"
    d_sg= "d_sg"
    d_vsc = "d_vsc"

    rel_tolerance = 0.01
    max_depth = 3
    dimensions = [
            Dimension(variable_borders=p_sg, n_cases=n_cases, divs=2, borders=(0, 5),
                      independent_dimension=True, label="p_sg", cosphi=cosphi),
            Dimension(variable_borders=p_cig, n_cases=n_cases, divs=1, borders=(0, 6),
                      independent_dimension=True, label="p_cig", cosphi=cosphi),
            Dimension(variable_borders=perc_g_for, n_cases=n_cases, divs=1, borders=(0, 1),
                      independent_dimension=True, label="perc_g_for"),
            Dimension(values=[0.5, 0.1, 0.4], n_cases=n_cases, divs=1,
                      independent_dimension=False, label="p_load", cosphi=cosphi)
    ]
    """
    Dimension(variable_borders=tau_f_g_for, n_cases=n_cases, divs=1,
                  borders=(0, 2), label="tau_f_g_for"),
    Dimension(variable_borders=tau_v_g_for, n_cases=n_cases, divs=1,
              borders=(0, 2), label="tau_v_g_for"),
    Dimension(variable_borders=tau_p_g_for, n_cases=n_cases, divs=1,
              borders=(0, 2), label="tau_p_g_for"),
    Dimension(variable_borders=tau_q_g_for, n_cases=n_cases, divs=1,
              borders=(0, 2), label="tau_q_g_for")
    """

    fig, ax = plt.subplots()
    use_sensitivity = True
    cases_df, dims_df, execution_logs = \
        start(dimensions, n_samples, rel_tolerance, func=dummy, 
              max_depth=max_depth, use_sensitivity=use_sensitivity, ax=None, 
              divs_per_cell=2, seed=10, d_raw_data=d_raw_data,d_op=d_op, 
              GridCal_grid=GridCal_grid, d_grid=d_grid, d_sg=d_sg, d_vsc=d_vsc)

if __name__ == "__main__":
    main()
