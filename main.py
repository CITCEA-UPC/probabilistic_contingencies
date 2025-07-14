#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

import copy

import GridCalEngine.api as gce
import networkx as nx
import json
import numpy as np
import pandas as pd
from stability_analysis.preprocess import preprocess_data, read_data, process_raw
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus, fill_d_grid_after_powerflow
# from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from stability_analysis.preprocess import parameters
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from stability_analysis.state_space import build_ss, generate_NET, generate_elements
from stability_analysis.analysis import small_signal
import warnings


warnings.filterwarnings("ignore", category=FutureWarning, message=".*connect\\(\\) is deprecated; use interconnect\\(\\).*")

warnings.filterwarnings("ignore", category=FutureWarning, message=r".*Series\.__getitem__ treating keys as positions is deprecated.*")

import json
from collections import defaultdict
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor

def save_results_to_json(all_results, filename='results.json'):
    """Guarda todos los resultados en un único archivo JSON"""
    # Convertimos la lista de resultados a un formato adecuado para JSON
    results_list = [dict(result) for result in all_results]

    # Ordenamos los resultados por case_id para mejor organización
    results_list.sort(key=lambda x: x['case_id'])

    with open(filename, 'w') as f:
        json.dump(results_list, f, indent=4)

def process_case(args):
    """Process a single case and save the result."""
    grid, d_grid, d_raw_data, result = args
    result = check_stability_and_pf(grid, d_grid, d_raw_data, result)
    return result

def detect_islands(grid):
    """Comprova si la xarxa elèctrica (grid) està dividida en illes.

    Aquesta funció analitza la topologia de la xarxa per determinar si tots
    els seus components estan connectats entre si o si, per contra, hi ha
    subxarxes aïllades (illes).

    Args:
        grid: L'objecte de la xarxa elèctrica que es vol analitzar.

    Returns:
        bool: Retorna 'True' si la xarxa té més d'un component connectat
              (és a dir, si hi ha almenys una illa), i 'False' si tota la
              xarxa forma un únic component.
    """
    # Compila el circuit numèric a partir de la xarxa.
    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)

    # Divideix el circuit en components connectats (illes).
    islas_list = nc.split_into_islands()

    # Retorna True si hi ha més d'una illa.
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


def check_stability_and_pf(grid, d_grid, d_raw_data, result):
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

        result['gce.powerflow_converged'] = gce.power_flow(grid).converged
        result['gce.run_powerflow_converged'] = pf_results.convergence_reports[0].converged_[0]
        result['stability'] = stability
        result['islands'] = detect_islands(grid)

        return result

    except Exception as e:

        #print(f"Error during stability check: {e}")
        # gce.save_file(grid, "exemple.gridcal")
        # sys.exit()
        result['gce.powerflow_converged'] = None
        result['gce.run_powerflow_converged'] = None
        result['stability'] = None
        result['islands'] = None
        return result




def remove_existing_result_file(path='results.jsonl'):
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

    # Remove old file if it exists
    remove_existing_result_file('results.jsonl')

    # ----------------------------------------------------------------
    # Print the total counts of each component type
    num_lines = len(grid.lines)
    num_generators = len(grid.generators)
    num_transformers = len(grid.transformers2w)
    print(f"Number of lines: {num_lines}")
    print(f"Number of generators: {num_generators}")
    print(f"Number of transformers: {num_transformers}")
    # ----------------------------------------------------------------
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

    # Create a list to hold all cases
    all_cases = []

    # ======================[ LINES ]======================
    # ------------------ Simulate first-level failures ------------------
    for idx, line in enumerate(grid.lines):
        line.active = False
        cases += 1
        print("First_level_Lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

        result = {
            'case_id': cases,
            'level': 'single',
            'type_combo': 'line',
            'elements': [
                {'type': 'line', 'id': idx}
            ]
        }
        all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
        #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

        # 1) Second-level failures on lines
        for idx2, line2 in enumerate(grid.lines):
            if idx2 != idx:
                line2.active = False
                cases += 1
                print("Second_level_Lines-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

                result = {
                    'case_id': cases,
                    'level': 'double',
                    'type_combo': ('line', 'line'),
                    'elements': [
                        {'type': 'line', 'id': idx},
                        {'type': 'line', 'id': idx2}
                    ]
                }
                all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
                #all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
                #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

                line2.active = True

        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            cases += 1
            print("Second_level_Lines-transformers:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('line', 'transformer'),
                'elements': [
                    {'type': 'line', 'id': idx},
                    {'type': 'transformer', 'id': idx2}
                ]
            }

            all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
            #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

            transformer.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            cases += 1
            print("Second_level_Lines-generators:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('line', 'generator'),
                'elements': [
                    {'type': 'line', 'id': idx},
                    {'type': 'generator', 'id': idx2}
                ]
            }
            all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
            #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

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

        result = {
            'case_id': cases,
            'level': 'single',
            'type_combo': 'transformer',
            'elements': [
                {'type': 'transformer', 'id': idx}
            ]
        }
        all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
        #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)


        # 1) Second-level failures on transformers
        for idx2, transformer2 in enumerate(grid.transformers2w):
            if idx2 != idx:
                transformer2.active = False
                cases += 1
                print("Second_level_Transformers-transformers:", cases, '/', total_cases,f'({cases / total_cases * 100:.2f}%)')

                result = {
                    'case_id': cases,
                    'level': 'double',
                    'type_combo': ('transformer', 'transformer'),
                    'elements': [
                        {'type': 'transformer', 'id': idx},
                        {'type': 'transformer', 'id': idx2}
                    ]
                }

                all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))

                #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

                transformer2.active = True

        # 2) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False
            cases += 1
            print("Second_level_Transformers-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('transformer', 'line'),
                'elements': [
                    {'type': 'transformer', 'id': idx},
                    {'type': 'line', 'id': idx2}
                ]
            }

            all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
            #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)


            line.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            cases += 1
            print("Second_level_Transformers-generators:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('transformer', 'generator'),
                'elements': [
                    {'type': 'transformer', 'id': idx},
                    {'type': 'generator', 'id': idx2}
                ]
            }

            all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
            #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

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

        result = {
            'case_id': cases,
            'level': 'single',
            'type_combo': 'generator',
            'elements': [
                {'type': 'generator', 'id': idx}
            ]
        }
        all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
        #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

        # 1) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False
            cases += 1
            print("Second_level_Generators-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('generator', 'line'),
                'elements': [
                    {'type': 'generator', 'id': idx},
                    {'type': 'line', 'id': idx2}
                ]
            }

            all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
            #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

            line.active = True
        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            cases += 1
            print("Second_level_Generators-transformers:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

            result = {
                'case_id': cases,
                'level': 'double',
                'type_combo': ('generator', 'transformer'),
                'elements': [
                    {'type': 'generator', 'id': idx},
                    {'type': 'transformer', 'id': idx2}
                ]
            }

            all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
            #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

            transformer.active = True
        # 3) Second-level failures on generators
        for idx2, generator2 in enumerate(grid.generators):
            if idx2 != idx:
                generator2.active = False
                cases += 1
                print("Second_level_Generators-generators:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
                result = {
                    'case_id': cases,
                    'level': 'double',
                    'type_combo': ('generator', 'generator'),
                    'elements': [
                        {'type': 'generator', 'id': idx},
                        {'type': 'generator', 'id': idx2}
                    ]
                }

                all_cases.append((grid.copy(), d_grid.copy(), d_raw_data.copy(), result.copy()))
                #result = check_stability_and_pf(grid, d_grid, d_raw_data, result)

                generator2.active = True
        generator.active = True
    # Ensure all components are active again
    check(grid)
    print('Generators done')

    # Process all cases in parallel
    print(f"Starting parallel processing of {len(all_cases)} cases...")

    all_results = []

    # Determine the number of workers (leave some CPU cores free)
    max_workers = max(1, os.cpu_count() - 2)


    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all cases to the executor
        futures = [executor.submit(process_case, case) for case in all_cases]

        # Wait for all futures to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
                print(f"Case {result['case_id']} completed")  # Opcional: feedback de progreso
            except Exception as e:
                print(f"Error processing case: {e}")
                all_results.append({'error': str(e)})

    # Guardar todos los resultados en un JSON
    save_results_to_json(all_results)

    print("All cases processed. Results saved to results.jsonl")
