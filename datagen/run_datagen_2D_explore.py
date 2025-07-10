import numpy as np
import scienceplots
from matplotlib import pyplot as plt

from datagen.src.objective_function import complex_2d_shape_obj_func, \
    complex_2d_shape
from datagen.src.dimensions import Dimension
from datagen.src.start_app import start

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
except ImportError:
    from datagen.dummies.task import task
    from datagen.dummies.api import compss_wait_on

plt.style.use('science')


@task()
def main():
    dst_dir = "results"
    n_samples = 5
    n_cases = 3
    rel_tolerance = 0.1
    max_depth = 3
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    dimensions = [
        Dimension(label="tau_Dim_0", n_cases=n_cases, divs=3, borders=(-1, 1)),
        Dimension(label="tau_Dim_1", n_cases=n_cases, divs=3, borders=(-1, 1))
    ]
    use_sensitivity = False
    seed = 17
    divs_per_cell = 3
    feasible_rate = 0.5

    # Plot heat map
    add_color_map(ax, fig)

    cases_df, dims_df, execution_logs, output_dataframes = \
        start(dimensions, n_samples, rel_tolerance,
              func=complex_2d_shape_obj_func,
              max_depth=max_depth, dst_dir=dst_dir,
              use_sensitivity=use_sensitivity, ax=ax,
              divs_per_cell=divs_per_cell, plot_boxplot=True, seed=seed,
              feasible_rate=feasible_rate)

    fig.savefig("figures/2D_contour_plot_complex_shape.png", dpi=300)
    plt.show()


def add_color_map(ax, fig):
    # Generate the data grid
    x = np.linspace(-3, 3, 500)  # 500 points in range [-3, 3]
    y = np.linspace(-3, 3, 500)
    X, Y = np.meshgrid(x, y)  # Create a 2D grid

    # Compute Z values
    Z = complex_2d_shape(X, Y)

    # Plot the filled contour plot (heatmap)
    c = ax.contourf(X, Y, Z, levels=100, cmap='viridis')

    # Add contour lines for z = 0
    zero_contour = ax.contour(X, Y, Z, levels=[0], colors='red',
                              linewidths=1.5)
    ax.clabel(zero_contour, fmt="z=0", colors="white", fontsize=10)

    fig.colorbar(c, ax=ax, label='Z value')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_title('Heatmap of complex_2d_shape')


if __name__ == '__main__':
    main()
