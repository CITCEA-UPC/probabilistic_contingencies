#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

import GridCalEngine.api as gce
import networkx as nx
import json
import numpy as np
import pandas as pd
from stability_analysis.preprocess import preprocess_data, read_data, process_raw
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus, fill_d_grid_after_powerflow
# from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from stability_analysis.preprocess import parameters
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from small_signal_analysis import *
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, assign_PQ_Loads_to_grid, assign_SlackBus_to_grid
import warnings


import threading

file_lock = threading.Lock()

warnings.filterwarnings("ignore", category=FutureWarning, message=".*connect\\(\\) is deprecated; use interconnect\\(\\).*")

warnings.filterwarnings("ignore", category=FutureWarning, message=r".*Series\.__getitem__ treating keys as positions is deprecated.*")


def read_excel_sheets_as_dict(file_path):
    """
    Reads an Excel file with multiple sheets and returns a dictionary.

    Parameters:
        file_path (str): Path to the Excel file.

    Returns:
        dict: A dictionary where keys are sheet names and values are DataFrames.
    """
    xls = pd.read_excel(file_path, sheet_name=None)
    return xls

def detect_islands(grid):
    """
    Builds a graph with the buses as nodes and the active branches as edges,
    and returns True if there is more than one connected component
    (i.e. at least one island), False otherwise.
    """

    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)
    '''
    options = gce.PowerFlowOptions()
    results = multi_island_pf_nc(nc, options=options)
    #print(results)'''
    islas_list = nc.split_into_islands()


    '''graph = nx.Graph()
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
    return len(components) > 1'''
    return len(islas_list) > 1


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
        return str(e), None, None, None




def remove_existing_result_file(path='results_secuencial.jsonl'):
    """
    Deletes the existing results file if it exists.

    Parameters:
    - path (str): Path to the results file (default: 'results.jsonl').
    """
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed existing file: {path}")
    else:
        print(f"No existing file found at: {path}")


def save_result(result, path='results_secuencial.jsonl'):
    """
    Saves a result as a JSON Lines entry (one JSON object per line).
    Automatically converts non-serializable types such as numpy types, sets,
    and exceptions into JSON-compatible formats.

    Parameters:
    - result (dict): Dictionary containing the result data.
    - path (str): Path to the .jsonl file (default: 'results.jsonl').
    """

    def to_serializable(obj):
        if isinstance(obj, (np.bool_, np.integer, np.floating)):
            return obj.item()  # Convert numpy types to native Python types
        if isinstance(obj, set):
            return list(obj)  # Convert sets to lists
        if isinstance(obj, BaseException):
            return str(obj)  # Convert exceptions to strings
        # Fallback: convert any unknown object to string
        return str(obj)

    with file_lock:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, default=to_serializable) + '\n')


def read_results_jsonl(route='results_secuencial.jsonl'):
    with open(route) as f:
        return [json.loads(line) for line in f]


if __name__ == "__main__":
    # Path to the grid file
    '''
    TODO: UPDATE
    Number of lines: 170
    Number of generators: 54
    Number of transformers: 9
    '''
    # Alternative example:
    GRID_FILE = 'stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw'

    # Open the grid
    grid = gce.open_file(GRID_FILE)

    filename= 'stability_analysis/stability_analysis/data/cases/IEEE118_NREL_stable_'
    d_grid = read_excel_sheets_as_dict(filename+'d_grid.xlsx')
    d_raw_data = read_excel_sheets_as_dict(filename+'d_raw_data.xlsx')
    d_opf = read_excel_sheets_as_dict(filename+'d_opf.xlsx')
    d_op = read_excel_sheets_as_dict(filename+'d_op.xlsx')

    # check d_grid Vn it has to be in [kV] !!
    d_grid['T_SG']['Vn'] = d_grid['T_SG']['Vn'] / 1e3
    d_grid['T_VSC']['Vn'] = d_grid['T_VSC']['Vn'] / 1e3

    excel_lines_ratings = "IEEE_118_Lines"
    path_data = 'stability_analysis/stability_analysis/data/'
    excel_lines_ratings = os.path.join(path_data, "cases", excel_lines_ratings + ".csv")
    lines_ratings = pd.read_csv(excel_lines_ratings)

    for line in grid.lines:
        bf = int(line.bus_from.code)
        bt = int(line.bus_to.code)
        line.rate = float(lines_ratings.loc[
            lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
                0], 'Max Flow (MW)'])

    for trafo in grid.transformers2w:
        bf = int(trafo.bus_from.code)
        bt = int(trafo.bus_to.code)
        trafo.rate = float(lines_ratings.loc[
            lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
                0], 'Max Flow (MW)'])

    excel_data = "IEEE_118_FULL"
    excel_sg = os.path.join(path_data, "cases", excel_data + "_data_sg.xlsx")
    excel_vsc = os.path.join(path_data, "cases", excel_data + "_data_vsc.xlsx")

    # Read Excel files with system data, generator data, and VSC data
    d_sg = read_data.read_data(excel_sg)
    d_vsc = read_data.read_data(excel_vsc)

    # ----------------------------------------------------------------
    # Print the total counts of each component type
    num_lines = len(grid.lines)
    num_generators = len(grid.generators)
    num_transformers = len(grid.transformers2w)
    print(f"Number of lines: {num_lines}")
    print(f"Number of generators: {num_generators}")
    print(f"Number of transformers: {num_transformers}")
    # ----------------------------------------------------------------

    assign_Generators_to_grid.assign_PVGen(GridCal_grid=grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=True, solved_point=True, d_pf=d_opf)
    assign_PQ_Loads_to_grid.assign_PQ_load(grid, d_raw_data)

    for bus in grid.buses:
        bus_num = int(bus.code)
        idx = d_opf['pf_bus'].query('bus == @bus_num').index[0]

        bus.Vm0 = d_opf['pf_bus'].loc[idx, 'Vm']
        bus.Va0 = d_opf['pf_bus'].loc[idx, 'theta'] / 180 * np.pi

    slack_bus_num = d_grid['T_global'].loc[0, 'ref_bus']
    assign_SlackBus_to_grid.assign_slack_bus(grid, slack_bus_num)

    # Calculate Power Flow
    pf_results = GridCal_powerflow.run_powerflow(grid,SolverType.NR,Qconrol_mode=False)

    # Remove old file if it exists
    remove_existing_result_file('results_secuencial.jsonl')

    if pf_results.convergence_reports[0].converged_[0]:

        d_pf = process_powerflow.update_OP(grid, pf_results, d_raw_data)

        stability, T_EIG = calculate_small_signal(d_raw_data, d_op, grid, d_grid, d_sg, d_vsc, d_pf)
    else:
        print('Base case power flow does not converge')
    cases = 0
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

    # ======================[ LINES ]======================
    # ------------------ Simulate first-level failures ------------------
    for idx, line in enumerate(grid.lines):
        line.active = False
        cases += 1
        print("First_level_Lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
        stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

        result = {
            'case_id': cases,
            'level': 'single',
            'type_combo': 'line',
            'elements': [
                {'type': 'line', 'id': idx}
            ],
            'gce.powerflow_converged': pf_converged,
            'gce.run_powerflow_converged': run_pf_converged,
            'stability': stability,
            'islands': detect_islands(grid)
        }

        save_result(result, path='results_secuencial.jsonl')

        # 1) Second-level failures on lines
        for idx2, line2 in enumerate(grid.lines):
            if idx2 != idx:
                line2.active = False
                cases += 1
                print("Second_level_Lines-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

                stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

                result = {
                    'case_id': cases,
                    'level': 'double',
                    'type_combo': ('line', 'line'),
                    'elements': [
                        {'type': 'line', 'id': idx},
                        {'type': 'line', 'id': idx2}
                    ],
                    'gce.powerflow_converged': pf_converged,
                    'gce.run_powerflow_converged': run_pf_converged,
                    'stability': stability,
                    'islands': detect_islands(grid)
                }
                save_result(result, path='results_secuencial.jsonl')
                line2.active = True

        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            cases += 1
            print("Second_level_Lines-transformers:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('line', 'transformer'),
                'elements': [
                    {'type': 'line', 'id': idx},
                    {'type': 'transformer', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            }
            save_result(results, path='results_secuencial.jsonl')

            transformer.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            cases += 1
            print("Second_level_Lines-generators:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            results = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('line', 'generator'),
                'elements': [
                    {'type': 'line', 'id': idx},
                    {'type': 'generator', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            }
            save_result(results, path='results_secuencial.jsonl')

            generator.active = True
        line.active = True

    # Ensure all components are active again
    check(grid)
    print('Lines done')

    # ======================[ TRANSFORMERS ]======================
    # ------------------ Simulate first-level failures ------------------

    for idx, transformer in enumerate(grid.transformers2w):
        transformer.active = False
        cases += 1
        print("First_level_Transformers:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
        stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

        result = {
            'case_id': cases,
            'level': 'single',
            'type_combo': 'transformer',
            'elements': [
                {'type': 'transformer', 'id': idx}
            ],
            'gce.powerflow_converged': pf_converged,
            'gce.run_powerflow_converged': run_pf_converged,
            'stability': stability,
            'islands': detect_islands(grid)
        }
        save_result(result, path='results_secuencial.jsonl')

        # 1) Second-level failures on transformers
        for idx2, transformer2 in enumerate(grid.transformers2w):
            if idx2 != idx:
                transformer2.active = False
                cases += 1
                print("Second_level_Transformers-transformers:", cases, '/', total_cases,
                      f'({cases / total_cases * 100:.2f}%)')
                stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

                result = {
                    'case_id': cases,
                    'level': 'double',
                    'type_combo': ('transformer', 'transformer'),
                    'elements': [
                        {'type': 'transformer', 'id': idx},
                        {'type': 'transformer', 'id': idx2}
                    ],
                    'gce.powerflow_converged': pf_converged,
                    'gce.run_powerflow_converged': run_pf_converged,
                    'stability': stability,
                    'islands': detect_islands(grid)
                }
                save_result(result, path='results_secuencial.jsonl')

                transformer2.active = True

        # 2) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False
            cases += 1
            print("Second_level_Transformers-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('transformer', 'line'),
                'elements': [
                    {'type': 'transformer', 'id': idx},
                    {'type': 'line', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            }
            save_result(result, path='results_secuencial.jsonl')

            line.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            cases += 1
            print("Second_level_Transformers-generators:", cases, '/', total_cases,
                  f'({cases / total_cases * 100:.2f}%)')
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('transformer', 'generator'),
                'elements': [
                    {'type': 'transformer', 'id': idx},
                    {'type': 'generator', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            }
            save_result(result, path='results_secuencial.jsonl')

            generator.active = True
        transformer.active = True
    check(grid)
    print('Transformers done')

    # ======================[ GENERATORS ]======================
    # ------------------ Simulate first-level failures ------------------

    for idx, generator in enumerate(grid.generators):
        generator.active = False
        cases += 1
        print("First_level_Generators:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
        stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

        result = {
            'case_id': cases,
            'level': 'single',
            'type_combo': 'generator',
            'elements': [
                {'type': 'generator', 'id': idx}
            ],
            'gce.powerflow_converged': pf_converged,
            'gce.run_powerflow_converged': run_pf_converged,
            'stability': stability,
            'islands': detect_islands(grid)
        }
        save_result(result, path='results_secuencial.jsonl')

        # 1) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False
            cases += 1
            print("Second_level_Generators-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('generator', 'line'),
                'elements': [
                    {'type': 'generator', 'id': idx},
                    {'type': 'line', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            }
            save_result(result, path='results_secuencial.jsonl')

            line.active = True
        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            cases += 1
            print("Second_level_Generators-transformers:", cases, '/', total_cases,
                  f'({cases / total_cases * 100:.2f}%)')
            stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('generator', 'transformer'),
                'elements': [
                    {'type': 'generator', 'id': idx},
                    {'type': 'transformer', 'id': idx2}
                ],
                'gce.powerflow_converged': pf_converged,
                'gce.run_powerflow_converged': run_pf_converged,
                'stability': stability,
                'islands': detect_islands(grid)
            }
            save_result(result, path='results_secuencial.jsonl')

            transformer.active = True
        # 3) Second-level failures on generators
        for idx2, generator2 in enumerate(grid.generators):
            if idx2 != idx:
                generator2.active = False
                cases += 1
                print("Second_level_Generators-generators:", cases, '/', total_cases,
                      f'({cases / total_cases * 100:.2f}%)')
                stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(grid, d_grid, d_raw_data)

                result = {
                    'case_id': cases,
                    'level': 'double',
                    'type_combo': ('generator', 'generator'),
                    'elements': [
                        {'type': 'generator', 'id': idx},
                        {'type': 'generator', 'id': idx2}
                    ],
                    'gce.powerflow_converged': pf_converged,
                    'gce.run_powerflow_converged': run_pf_converged,
                    'stability': stability,
                    'islands': detect_islands(grid)
                }
                save_result(result, path='results_secuencial.jsonl')

                generator2.active = True
        generator.active = True
    # Ensure all components are active again
    check(grid)
    print('Generators done')

    print("Results saved to results_secuencial.jsonl")
