import GridCalEngine.api as gce
from pprint import pprint


def check_line_overloads(results, grid):
    """
    Checks all lines in the grid for overload.
    Uses the 'loading' values in the results and the branch data from grid.get_branches().

    Returns:
      - A list of line indices that are overloaded (i.e. loading > 1).
    """
    overloaded_lines = []
    for idx, (loading, branch) in enumerate(zip(results.loading, grid.get_branches())):
        if loading > 1:
            overloaded_lines.append(idx)
    return overloaded_lines


def check(grid):
    for idx, line in enumerate(grid.lines):
        if not line.active:
            raise Exception(f"Línea en índice {idx} no está activa")
    for idx, transformer in enumerate(grid.transformers2w):
        if not transformer.active:
            raise Exception(f"transformer en índice {idx} no está activa")
    for idx, generator in enumerate(grid.generators):
        if not generator.active:
            raise Exception(f"generator en índice {idx} no está activa")


if __name__ == "__main__":
    # GRID_FILE = 'IEEE118_opf.gridcal'
    GRID_FILE = 'IEEE_14.xlsx'
    grid = gce.open_file(GRID_FILE)
    FAILURE_PROBABILITY = 100  # 100% chance of any component failing

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

    # Simular primer error a les línies
    for idx, line in enumerate(grid.lines):
        line.active = False
        if not gce.power_flow(grid).converged:
            results['first_level_line'].append(idx)
        else:
            # Simular segon error a les línies
            for idx2, line2 in enumerate(grid.lines):
                # Comprovar que no sigui la mateixa línia
                if idx2 != idx:
                    line2.active = False
                    if not gce.power_flow(grid).converged:
                        results['second_level_line_line'].append([idx, idx2])
                    line2.active = True
            # Simular segon error als transformadors
            for idx2, transformer in enumerate(grid.transformers2w):
                transformer.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_line_transformer'].append([idx, idx2])
                transformer.active = True
            # Simular segon error als generadors
            for idx2, generator in enumerate(grid.generators):
                generator.active = False
                res = gce.power_flow(grid)
                if not gce.power_flow(grid).converged:
                    results['second_level_line_generator'].append([idx, idx2])
                generator.active = True
        line.active = True
    check(grid)
    # Simular primer error als transformadors
    for idx, transformer in enumerate(grid.transformers2w):
        transformer.active = False
        if not gce.power_flow(grid).converged:
            results['first_level_transformer'].append(idx)
        else:
            # Simular segon error a les línies
            for idx2, line in enumerate(grid.lines):
                line.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_transformer_line'].append([idx, idx2])
                line.active = True
            # Simular segon error als transformadors
            for idx2, transformer2 in enumerate(grid.transformers2w):
                # Comprovar que no sigui el mateix transformador
                if idx2 != idx:
                    transformer2.active = False
                    if not gce.power_flow(grid).converged:
                        results['second_level_transformer_transformer'].append([idx, idx2])
                    transformer2.active = True
            # Simular segon error als generadors
            for idx2, generator in enumerate(grid.generators):
                generator.active = False
                res = gce.power_flow(grid)
                if not gce.power_flow(grid).converged:
                    results['second_level_transformer_generator'].append([idx, idx2])
                generator.active = True
        transformer.active = True
    check(grid)

    # Simular primer error als generadors
    for idx, generator in enumerate(grid.generators):
        generator.active = False
        if not gce.power_flow(grid).converged:
            results['first_level_generator'].append(idx)
        else:
            # Simular segon error a les línies
            for idx2, line in enumerate(grid.lines):
                line.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_generator_line'].append([idx, idx2])
                line.active = True
            # Simular segon error als transformadors
            for idx2, transformer in enumerate(grid.transformers2w):
                transformer.active = False
                if not gce.power_flow(grid).converged:
                    results['second_level_generator_transformer'].append([idx, idx2])
                transformer.active = True
            # Simular segon error als generadors
            for idx2, generator2 in enumerate(grid.generators):
                # Comprovar que no sigui el mateix generador
                if idx2 != idx:
                    generator2.active = False
                    res = gce.power_flow(grid)
                    if not gce.power_flow(grid).converged:
                        results['second_level_generator_generator'].append([idx, idx2])
                    generator2.active = True
        generator.active = True
    check(grid)


    pprint(results)
