#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

import GridCalEngine.api as gce
import json
import networkx as nx

import os
import pandas as pd
from stability_analysis.preprocess import preprocess_data, read_data, \
    process_raw
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus, fill_d_grid_after_powerflow
# from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from stability_analysis.preprocess import parameters

from stability_analysis.state_space import build_ss, generate_NET, generate_elements
from stability_analysis.analysis import small_signal


def detect_islands(grid):
    """
    Builds a graph with the buses as nodes and the active branches as edges,
    and returns True if there is more than one connected component
    (i.e. at least one island), False otherwise.
    """
    graph = nx.Graph()
    # Add buses
    for bus in grid.buses:
        graph.add_node(bus)
    # Add edges only for active lines
    for line in grid.lines:
        if line.active:
            i = line.bus_from
            j = line.bus_to
            graph.add_edge(i, j)
    # Count components
    components = list(nx.connected_components(graph))
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


def check_stability_and_pf(grid, d_grid, d_raw_data):

    pf_results = GridCal_powerflow.run_powerflow(grid, Qconrol_mode=False)

    try:
        # Update PF results and operation point of generator elements
        d_pf = process_powerflow.update_OP(grid, pf_results, d_raw_data)

        d_grid, d_pf = fill_d_grid_after_powerflow.fill_d_grid(d_grid,
                                                               grid, d_pf,
                                                               d_raw_data, d_op)

        # %% READ PARAMETERS

        # Get parameters of generator units from excel files & compute pu base
        d_grid = parameters.get_params(d_grid, d_sg, d_vsc)

        # Assign slack bus and slack element
        d_grid = slack_bus.assign_slack(d_grid)

        # Compute reference angle (delta_slk)
        d_grid, REF_w, num_slk, delta_slk = slack_bus.delta_slk(d_grid)

        # %% GENERATE STATE-SPACE MODEL

        # Generate AC & DC NET State-Space Model

        """
        connect_fun: 'append_and_connect' (default) or 'interconnect'. 
            'append_and_connect': Uses a function that bypasses linearization; 
            'interconnect': use original ct.interconnect function. 
        save_ss_matrices: bool. Default is False. 
            If True, write on csv file the A, B, C, D matrices of the state space.
            False default option
        """
        connect_fun = 'append_and_connect'
        save_ss_matrices = False

        l_blocks, l_states, d_grid = generate_NET.generate_SS_NET_blocks(
            d_grid, delta_slk, connect_fun, save_ss_matrices)

        # Generate generator units State-Space Model
        l_blocks, l_states = generate_elements.generate_SS_elements(
            d_grid, delta_slk, l_blocks, l_states, connect_fun, save_ss_matrices)

        # %% BUILD FULL SYSTEM STATE-SPACE MODEL

        # Define full system inputs and ouputs
        var_in = ['NET_Rld1']
        var_out = ['all']  # ['all']  # ['GFOR3_w'] #

        # Build full system state-space model

        inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
        ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs, connect_fun,
                                  save_ss_matrices)

        # %% SMALL-SIGNAL ANALYSIS

        T_EIG = small_signal.FEIG(ss_sys, False)


        # write to excel
        # T_EIG.to_excel(path.join(path_results, "EIG_" + excel + ".xlsx"))

        if max(T_EIG['real'] >= 0):
            stability = 0
        else:
            stability = 1

        # Obtain all participation factors
        # df_PF = small_signal.FMODAL(ss_sys, plot=False)
        # # Obtain the participation factors for the selected modes
        # T_modal, df_PF = small_signal.FMODAL_REDUCED(ss_sys, plot=True, modeID = [1,3,11])
        # # Obtain the participation factors >= tol, for the selected modes
        return stability, T_EIG, gce.power_flow(grid).converged, pf_results.convergence_reports[0].converged_[0]
    except Exception as e:


        print(f"Error during stability check: {e}")
        # gce.save_file(grid, "exemple.gridcal")
        # sys.exit()
        return e, None, None, None

if __name__ == "__main__":
    # Path to the grid file
    '''
    Number of lines: 170
    Number of generators: 54
    Number of transformers: 9
    '''
    # Alternative example:
    GRID_FILE = 'stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw'

    # Open the grid
    grid = gce.open_file(GRID_FILE)

    # ----------------------------------------------------------------

    excel_headers = "IEEE_118_FULL_headers"
    excel_data = "IEEE_118_FULL"
    excel_op = "OperationData_IEEE_118_NREL"
    excel_lines_ratings = "IEEE_118_Lines"

    path_data = 'stability_analysis/stability_analysis/data/'
    excel_sys = os.path.join(path_data, "cases", excel_headers + ".xlsx")
    excel_sg = os.path.join(path_data, "cases", excel_data + "_data_sg.xlsx")
    excel_vsc = os.path.join(path_data, "cases", excel_data + "_data_vsc.xlsx")
    excel_op = os.path.join(path_data, "cases", excel_op + ".xlsx")

    excel_lines_ratings = os.path.join(
        path_data, "cases", excel_lines_ratings + ".csv")

    d_raw_data = process_raw.read_raw(GRID_FILE)
    d_op = read_data.read_data(excel_op)

    # FOR the 118-bus system
    d_raw_data['generator']['Region'] = d_op['Generators']['Region']
    d_raw_data['load']['Region'] = d_op['Loads']['Region']
    # d_raw_data['branch']['Region']=1
    d_raw_data['results_bus']['Region'] = d_op['Buses']['Region']
    d_raw_data['generator']['MBASE'] = d_op['Generators']['Snom']
    lines_ratings = pd.read_csv(excel_lines_ratings)

    # Preprocess input raw data to match Excel file format
    preprocess_data.preprocess_raw(d_raw_data)

    d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)
    d_sg = read_data.read_data(excel_sg)
    d_vsc = read_data.read_data(excel_vsc)

    idx_sg0 = list(d_op['Generators'].query('Snom_SG==0')['BusNum'])
    d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @idx_sg0').index, 'alpha_P_SG'] = 0

    idx_cig0 = list(d_op['Generators'].query('Snom_CIG==0')['BusNum'])
    d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @idx_cig0').index, 'alpha_P_GFOR'] = 0
    d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @idx_cig0').index, 'alpha_P_GFOL'] = 0

    for i in d_raw_data['generator'].index:
        alphas = d_raw_data['generator'].loc[
            i, [col for col in d_raw_data['generator'].columns if col.startswith('alpha')]]
        nan_indices = alphas[alphas.isna()].index
        d_raw_data['generator'].loc[i, nan_indices] = 1 / (alphas.isna().sum())

    for el in ['GFOL', 'GFOR']:
        d_op['Generators']['Snom_' + el] = d_raw_data['generator']['alpha_P_' + el] * d_op['Generators']['Snom_CIG']

    # ----------------------------------------------------------------
    # Print the total counts of each component type
    num_lines = len(grid.lines)
    num_generators = len(grid.generators)
    num_transformers = len(grid.transformers2w)
    print(f"Number of lines: {num_lines}")
    print(f"Number of generators: {num_generators}")
    print(f"Number of transformers: {num_transformers}")
    # ----------------------------------------------------------------
    total_cases = (
            num_lines + num_transformers + num_generators +  # fallos individuales
            num_lines * (num_lines - 1) +  # línea-línea (sin repetirse consigo misma)
            num_lines * num_transformers +  # línea-transformador
            num_lines * num_generators +  # línea-generador
            num_transformers * (num_transformers - 1) +  # transformador-transformador
            num_transformers * num_lines +  # transformador-línea
            num_transformers * num_generators +  # transformador-generador
            num_generators * (num_generators - 1) +  # generador-generador
            num_generators * num_lines +  # generador-línea
            num_generators * num_transformers  # generador-transformador
    )

    print(f"Total simulated contingency cases: {total_cases}")
    # Probability of failure (100% means any component you deactivate will fail)
    FAILURE_PROBABILITY = 100

    # Prepare results buckets for first- and second-level failures
    results = {
        'single': {
            'line': [],
            'transformer': [],
            'generator': []
        },
        'double': {
            'line': {
                'line': [],
                'transformer': [],
                'generator': []
            },
            'transformer': {
                'line': [],
                'transformer': [],
                'generator': []
            },
            'generator': {
                'line': [],
                'transformer': [],
                'generator': []
            }
        }
    }

    # --- Simulate first-level failures on lines ---
    for idx, line in enumerate(grid.lines):
        line.active = False

        stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

        results['single']['line'].append({
            'element': {'type': 'line', 'id': idx},
            'gce.powerflow_converged': pf_converged,
            'gce.run_powerflow_converged': run_pf_converged,
            'stability': stability,
            'islands': detect_islands(grid)
        })

        # 1) Second-level failures on lines
        for idx2, line2 in enumerate(grid.lines):
            if idx2 != idx:
                line2.active = False

                stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

                results['double']['line']['line'].append({
                    'elements': [
                        {'type': 'line', 'id': idx},
                        {'type': 'line', 'id': idx2}
                    ],
                    'gce.powerflow_converged': pf_converged,
                    'gce.run_powerflow_converged': run_pf_converged,
                    'stability': stability,
                    'islands': detect_islands(grid)
                })
                line2.active = True

        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False

            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results['double']['line']['transformer'].append({
                'elements': [
                    {'type': 'line', 'id': idx},
                    {'type': 'transformer', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            })
            transformer.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results['double']['line']['generator'].append({
                'elements': [
                    {'type': 'line', 'id': idx},
                    {'type': 'generator', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            })
            generator.active = True
        line.active = True

    # Ensure all components are active again
    check(grid)
    print('Lines done')



    # --- Simulate first-level failures on transformers ---
    for idx, transformer in enumerate(grid.transformers2w):
        transformer.active = False
        stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

        results['single']['transformer'].append({
            'element': {'type': 'transformer', 'id': idx},
            'gce.powerflow_converged': pf_converged,
            'gce.run_powerflow_converged': run_pf_converged,
            'stability': stability,
            'islands': detect_islands(grid)
        })


        # 1) Second-level failures on transformers
        for idx2, transformer2 in enumerate(grid.transformers2w):
            if idx2 != idx:
                transformer2.active = False

                stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

                results['double']['transformer']['transformer'].append({
                    'elements': [
                        {'type': 'transformer', 'id': idx},
                        {'type': 'transformer', 'id': idx2}
                    ],
                    'gce.powerflow_converged': pf_converged,
                    'gce.run_powerflow_converged': run_pf_converged,
                    'stability': stability,
                    'islands': detect_islands(grid)
                })
                transformer2.active = True

        # 2) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False

            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results['double']['transformer']['line'].append({
                'elements': [
                    {'type': 'transformer', 'id': idx},
                    {'type': 'line', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            })
            line.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False

            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results['double']['transformer']['generator'].append({
                'elements': [
                    {'type': 'transformer', 'id': idx},
                    {'type': 'generator', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            })
            generator.active = True
        transformer.active = True
    check(grid)
    print('Transformers done')

    # --- Simulate first-level failures on generators ---
    for idx, generator in enumerate(grid.generators):
        generator.active = False
        stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

        results['single']['generator'].append({
            'element': {'type': 'generator', 'id': idx},
            'gce.powerflow_converged': pf_converged,
            'gce.run_powerflow_converged': run_pf_converged,
            'stability': stability,
            'islands': detect_islands(grid)
        })

        # 1) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False

            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results['double']['generator']['line'].append({
                'elements': [
                    {'type': 'generator', 'id': idx},
                    {'type': 'line', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            })
            line.active = True
        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results['double']['generator']['transformer'].append({
                'elements': [
                    {'type': 'generator', 'id': idx},
                    {'type': 'transformer', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            })
            transformer.active = True
        # 3) Second-level failures on generators
        for idx2, generator2 in enumerate(grid.generators):
            if idx2 != idx:
                generator2.active = False
                stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

                results['double']['generator']['generator'].append({
                    'elements': [
                        {'type': 'generator', 'id': idx},
                        {'type': 'generator', 'id': idx2}
                    ],
                    'gce.powerflow_converged': pf_converged,
                    'gce.run_powerflow_converged': run_pf_converged,
                    'stability': stability,
                    'islands': detect_islands(grid)
                })
                generator2.active = True
        generator.active = True
    # Ensure all components are active again
    check(grid)
    print('Generators done')

    with open('results.json', 'w', encoding='utf-8') as f:
        # 2) Dump the `results` dict as pretty-printed JSON
        json.dump(results, f, ensure_ascii=False, indent=4)

    print("Results saved to results.json")
