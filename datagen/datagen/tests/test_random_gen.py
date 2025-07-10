from random import random

import numpy as np
from matplotlib import pyplot as plt
from unittest import TestCase

from datagen import generate_columns, Dimension


def compute_avg_distance(cases):
    distances = []
    n = len(cases)
    for i in range(n):
        for j in range(i+1, n):
            dist = np.linalg.norm(np.array(cases[i]) - np.array(cases[j]))
            distances.append(dist)
    return sum(distances) / len(distances)


class Test(TestCase):

    def test_plot_sparsity(self):
        """
        Generate samples with get_cases_normal and get_cases_extreme to
        visualize how well-distributed data is.
        """
        generator = np.random.default_rng(1)
        variables = np.array([(0, 10), (0, 15), (5, 20), (0, 25)])
        n_cases = 30
        divs = None
        lower, upper = 0, 70
        label = "Test"
        tolerance = 0.1

        dim = Dimension(variable_borders=variables, n_cases=n_cases, divs=divs,
                        borders=(lower, upper),
                        label=label)
        dim.tolerance = tolerance

        samples = np.linspace(lower + 10, upper, 10).tolist()

        avg_distances_normal = []
        avg_distances_extreme = []
        percentages_normal = []
        percentages_extreme = []
        for sample in samples:
            cases_normal = dim.get_cases_normal(sample, generator)
            cases_extreme = dim.get_cases_extreme(sample, generator)

            print(f"Sample: {sample}")
            print("get_cases_normal:")
            none_flag = False
            for case in cases_normal:
                if None not in case:
                    print(case, sum(case))

            print("get_cases_extreme:")
            for case in cases_extreme:
                if None not in case:
                    print(case, sum(case))
                else:
                    none_flag = True
            if none_flag:
                continue
            print("---------------------------")

            avg_distances_normal.append(compute_avg_distance(cases_normal))
            avg_distances_extreme.append(compute_avg_distance(cases_extreme))

            # Calculate percentage of sampled content with respect bounds
            perc_normal = (cases_normal - variables[:, 0]) / (
                    variables[:, 1] - variables[:, 0])
            perc_extreme = (cases_extreme - variables[:, 0]) / (
                    variables[:, 1] - variables[:, 0])
            percentages_normal.append(perc_normal)
            percentages_extreme.append(perc_extreme)
        percentages_normal = np.concatenate(percentages_normal)
        percentages_extreme = np.concatenate(percentages_extreme)

        # Plot average distances
        plt.plot(samples, avg_distances_normal, 'o', label="get_cases_normal")
        plt.plot(samples, avg_distances_extreme, 'x',
                 label="get_cases_extreme")
        plt.xlabel("Sample")
        plt.ylabel("Average Distance Between Cases")
        plt.title("Variability Comparison")
        plt.legend()

        # Plot variable percentages
        for i in range(len(variables)):
            plt.figure()
            plt.plot(percentages_normal[:, i], 'o',
                     label="get_cases_normal")
            plt.plot(percentages_extreme[:, i], 'x',
                     label="get_cases_extreme")
            plt.ylim([0, 1])
            plt.xlabel("Sample")
            plt.ylabel("Percentage of the variable range")
            plt.title(f"Variability Comparison: Variable {i}")
            plt.legend()

        plt.show()
