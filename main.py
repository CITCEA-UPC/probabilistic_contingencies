#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import GridCalEngine.api as gce
from pprint import pprint
import json
import networkx as nx


def detect_islands(grid):
    """
    Builds a graph with the buses as nodes and the active branches as edges,
    and returns True if there is more than one connected component
    (i.e. at least one island), False otherwise.
    """
    G = nx.Graph()
    # Add buses
    for bus in grid.buses:
        G.add_node(bus)
    # Add edges only for active lines
    for line in grid.lines:
        if line.active:
            i = line.bus_from
            j = line.bus_to
            G.add_edge(i, j)
    # Count components
    components = list(nx.connected_components(G))
    return len(components) > 1


def check_line_overloads(results, grid):
    """
    Checks every line in the grid for overload conditions.
    Uses the 'loading' array from the results object and the branch data
    provided by grid.get_branches().

    Returns:
      - A list of line indices where loading > 1 (i.e., overloaded lines).
    """
    overloaded_lines = []
    for idx, (loading, branch) in enumerate(zip(results.loading, grid.get_branches())):
        if loading > 1:
            overloaded_lines.append(idx)
    return overloaded_lines


def check(grid):
    """
    Verifies that no component remains deactivated at the end of all simulations.
    Raises an Exception if any line, transformer, or generator is still inactive.
    """
    for idx, line in enumerate(grid.lines):
        if not line.active:
            raise Exception(f"Line at index {idx} is not active")
    for idx, transformer in enumerate(grid.transformers2w):
        if not transformer.active:
            raise Exception(f"Transformer at index {idx} is not active")
    for idx, generator in enumerate(grid.generators):
        if not generator.active:
            raise Exception(f"Generator at index {idx} is not active")


if __name__ == "__main__":
    # Path to the grid file
    GRID_FILE = 'grids/IEEE118_opf.gridcal'
    '''
    Number of lines: 170
    Number of generators: 54
    Number of transformers: 9
    '''
    # Alternative example:
    # GRID_FILE = 'grids/IEEE_14.xlsx'

    # Open the grid
    grid = gce.open_file(GRID_FILE)

    # ----------------------------------------------------------------
    # Print the total counts of each component type
    num_lines = len(grid.lines)
    num_generators = len(grid.generators)
    num_transformers = len(grid.transformers2w)
    print(f"Number of lines: {num_lines}")
    print(f"Number of generators: {num_generators}")
    print(f"Number of transformers: {num_transformers}")
    # ----------------------------------------------------------------

    # Probability of failure (100% means any component you deactivate will fail)
    FAILURE_PROBABILITY = 100

    # Prepare results buckets for first- and second-level failures
    results = {
        'first_level_line': [],
        'first_level_transformer': [],
        'first_level_generator': [],
        'second_level_line_line': [],
        'second_level_line_transformer': [],
        'second_level_line_generator': [],
        'second_level_transformer_line': [],
        'second_level_transformer_transformer': [],
        'second_level_transformer_generator': [],
        'second_level_generator_line': [],
        'second_level_generator_transformer': [],
        'second_level_generator_generator': [],
    }

    # --- Simulate first-level failures on lines ---
    for idx, line in enumerate(grid.lines):
        line.active = False
        if not gce.power_flow(grid).converged:
            # If power flow fails, record this line index
            results['first_level_line'].append([idx, detect_islands(grid)])
        else:
            # Otherwise, simulate second-level failures:

            # 1) Second-level failures on other lines
            for idx2, line2 in enumerate(grid.lines):
                if idx2 != idx:
                    line2.active = False
                    if not gce.power_flow(grid).converged:
                        results['second_level_line_line'].append([idx, idx2, detect_islands(grid)])
                    line2.active = True

            # 2) Second-level failures on transformers
            for idx2, transformer in enumerate(grid.transformers2w):
                transformer.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_line_transformer'].append([idx, idx2, detect_islands(grid)])
                transformer.active = True

            # 3) Second-level failures on generators
            for idx2, generator in enumerate(grid.generators):
                generator.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_line_generator'].append([idx, idx2, detect_islands(grid)])
                generator.active = True

        line.active = True

    # Ensure all components are active again
    check(grid)
    print('Lines done')
    # --- Simulate first-level failures on transformers ---
    for idx, transformer in enumerate(grid.transformers2w):
        transformer.active = False
        if not gce.power_flow(grid).converged:
            results['first_level_transformer'].append([idx, detect_islands(grid)])
        else:
            # Second-level on lines
            for idx2, line in enumerate(grid.lines):
                line.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_transformer_line'].append([idx, idx2, detect_islands(grid)])
                line.active = True

            # Second-level on other transformers
            for idx2, transformer2 in enumerate(grid.transformers2w):
                if idx2 != idx:
                    transformer2.active = False
                    if not gce.power_flow(grid).converged:
                        results['second_level_transformer_transformer'].append([idx, idx2, detect_islands(grid)])
                    transformer2.active = True

            # Second-level on generators
            for idx2, generator in enumerate(grid.generators):
                generator.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_transformer_generator'].append([idx, idx2, detect_islands(grid)])
                generator.active = True

        transformer.active = True

    check(grid)
    print('Transformers done')
    # --- Simulate first-level failures on generators ---
    for idx, generator in enumerate(grid.generators):
        generator.active = False
        if not gce.power_flow(grid).converged:
            results['first_level_generator'].append([idx, detect_islands(grid)])
        else:
            # Second-level on lines
            for idx2, line in enumerate(grid.lines):
                line.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_generator_line'].append([idx, idx2, detect_islands(grid)])
                line.active = True

            # Second-level on transformers
            for idx2, transformer in enumerate(grid.transformers2w):
                transformer.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_generator_transformer'].append([idx, idx2, detect_islands(grid)])
                transformer.active = True

            # Second-level on other generators
            for idx2, generator2 in enumerate(grid.generators):
                if idx2 != idx:
                    generator2.active = False
                    if not gce.power_flow(grid).converged:
                        results['second_level_generator_generator'].append([idx, idx2, detect_islands(grid)])
                    generator2.active = True

        generator.active = True

    check(grid)
    print('Generators done')
    # Print the aggregated results
    pprint(results)
    with open('results.json', 'w', encoding='utf-8') as f:
        # 2) Dump the `results` dict as pretty-printed JSON
        json.dump(results, f, ensure_ascii=False, indent=4)

    print("Results saved to results.json")
