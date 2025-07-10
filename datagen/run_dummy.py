from matplotlib import pyplot as plt

from datagen.src.objective_function import dummy
from datagen.src.dimensions import Dimension
from datagen.src.start_app import start

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
    
    variables_d0 = [(0, 2), (0, 1.5), (0, 1.5)]
    variables_d1 = [(0, 1), (0, 1.5), (0, 1.5), (0, 2)]
    n_samples = 5
    n_cases = 2
    rel_tolerance = 0.1
    max_depth = 3
    fig, ax = plt.subplots()
    dimensions = [
        Dimension(variable_borders=variables_d0, n_cases=n_cases, divs=2,
                  borders=(0, 5), label="Dim_0"),
        Dimension(variable_borders=variables_d1, n_cases=n_cases, divs=1,
                  borders=(1, 6), label="Dim_1")
    ]
    use_sensitivity = True
    cases_df, dims_df, execution_logs = \
        start(dimensions, n_samples, rel_tolerance, func=dummy, 
              max_depth=max_depth, use_sensitivity=use_sensitivity, ax=ax, 
              divs_per_cell=2, plot_boxplot=True, seed=1)


if __name__ == '__main__':
    main()
