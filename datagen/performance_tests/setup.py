from datagen.src.dimensions import Dimension
from datagen.src.objective_function import matmul


def setUp_basic():
    variables_d0 = [(0, 2), (0, 1.5), (0, 1.5)]
    variables_d1 = [(0, 1), (0, 1.5), (0, 1.5), (0, 2)]
    n_samples = 2
    n_cases = 1
    rel_tolerance = 0.2
    max_depth = 5
    use_sensitivity = True
    ax = None
    divs_per_cell = 4
    plot_boxplot = False

    dimensions = [
        Dimension(variable_borders=variables_d0, n_cases=n_cases, divs=2,
                  borders=(0, 5), label="Dim_0"),
        Dimension(variable_borders=variables_d1, n_cases=n_cases, divs=1,
                  borders=(0, 6), label="Dim_1")]

    return (dimensions, n_samples, rel_tolerance, dummy, max_depth,
            use_sensitivity, ax, divs_per_cell, plot_boxplot)


def setUp_complex():
    p_sg = [(0, 2), (0, 1.5), (0, 1.5)]
    p_cig = [(0, 1), (0, 1.5), (0, 1.5), (0, 2)]
    tau_f_g_for = [(0., 2)]
    tau_v_g_for = [(0., 2)]
    tau_p_g_for = [(0., 2)]
    tau_q_g_for = [(0., 2)]
    n_samples = 10
    n_cases = 5
    rel_tolerance = 0.05
    max_depth = 10
    use_sensitivity = True
    ax = None
    divs_per_cell = 4
    plot_boxplot = False

    dimensions = [
        Dimension(variable_borders=p_sg, n_cases=n_cases, divs=2, borders=(0, 5),
                  label="p_sg"),
        Dimension(variable_borders=p_cig, n_cases=n_cases, divs=1, borders=(0, 6),
                  label="p_cig"),
        Dimension(variable_borders=tau_f_g_for, n_cases=n_cases, divs=1,
                  borders=(0, 2), label="tau_f_g_for"),
        Dimension(variable_borders=tau_v_g_for, n_cases=n_cases, divs=1,
                  borders=(0, 2), label="tau_v_g_for"),
        Dimension(variable_borders=tau_p_g_for, n_cases=n_cases, divs=1,
                  borders=(0, 2), label="tau_p_g_for"),
        Dimension(variable_borders=tau_q_g_for, n_cases=n_cases, divs=1,
                  borders=(0, 2), label="tau_q_g_for")
    ]

    return (dimensions, n_samples, rel_tolerance, matmul, max_depth,
            use_sensitivity, ax, divs_per_cell, plot_boxplot)
