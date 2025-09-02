#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import threading
import warnings
import numpy as np
import pandas as pd
import memory_profiler as mp


# from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType

# Small signal imports
from small_signal_analysis import *
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, assign_PQ_Loads_to_grid, \
    assign_SlackBus_to_grid
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow
from stability_analysis.preprocess import read_data

# PyCOMPSs imports
from pycompss.api.task import task
from pycompss.api.api import compss_wait_on

global DEBUG
DEBUG = True

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
    Detecta si hay islas, es decir elementos aislados
    """

    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)
    '''
    options = gce.PowerFlowOptions()
    results = multi_island_pf_nc(nc, options=options)
    #print(results)'''
    islas_list = nc.split_into_islands()


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

@task(returns=4)
def check_stability_and_pf(grid, d_grid, d_raw_data):

    try:
        pf_results = gce.power_flow(grid)
        pf_converged = pf_results.converged
    except Exception as e:

        print(f"Error during powerflow and run powerflow check: {e}")
        # gce.save_file(grid, "exemple.gridcal")
        # sys.exit()
        pf_converged = None
        run_pf_converged = None
    try:
        run_pf_results = GridCal_powerflow.run_powerflow(grid, Qconrol_mode=False)
        run_pf_converged = run_pf_results.convergence_reports[0].converged_[0]

        # Update PF results and operation point of generator elements
        d_pf = process_powerflow.update_OP(grid, run_pf_results, d_raw_data)

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
        return stability, pf_converged, run_pf_converged, detect_islands(grid)
    except Exception as e:

        print(f"Error during stability check: {e}")
        # gce.save_file(grid, "exemple.gridcal")
        # sys.exit()
        return str(e), pf_converged, run_pf_converged, detect_islands(grid)




def remove_existing_result_file(path='results_parallel.jsonl'):
    """
    Deletes the existing results file if it exists.

    Parameters:
    - path (str): Path to the results file (default: 'results_parallel.jsonl').
    """
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed existing file: {path}")
    else:
        print(f"No existing file found at: {path}")

@task(returns=1)
def dummy(i):
    print("################ ", i+1)
    return i+1


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

    # GRID_FILE = 'stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw'

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
    # --------------------------TEST PYCOMPSS--------------------------------------
    futures = []

    for i in range(3):
        futures.append(dummy(i))

    futures = compss_wait_on(futures)
    print(futures)
    
    print("PYCOMPSS OKKKKK")
    #sys.exit(0)
    # --------------------------TEST PYCOMPSS--------------------------------------




    assign_Generators_to_grid.assign_PVGen(GridCal_grid=grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=True, solved_point=True, d_pf=d_opf)
    assign_PQ_Loads_to_grid.assign_PQ_load(grid, d_raw_data)
    print("Paso por aquí 0")
    for bus in grid.buses:
        bus_num = int(bus.code)
        idx = d_opf['pf_bus'].query('bus == @bus_num').index[0]

        bus.Vm0 = d_opf['pf_bus'].loc[idx, 'Vm']
        bus.Va0 = d_opf['pf_bus'].loc[idx, 'theta'] / 180 * np.pi

    slack_bus_num = d_grid['T_global'].loc[0, 'ref_bus']
    assign_SlackBus_to_grid.assign_slack_bus(grid, slack_bus_num)

    # Calculate Power Flow
    print("Paso por aquí 1")
    pf_results = GridCal_powerflow.run_powerflow(grid,SolverType.NR,Qconrol_mode=False)

    # Remove old file if it exists
    
    #remove_existing_result_file('results_parallel.jsonl')
    print("Paso por aquí 2")
    if pf_results.convergence_reports[0].converged_[0]:
        print("Paso por aquí 2.1")
        d_pf = process_powerflow.update_OP(grid, pf_results, d_raw_data)
        print("Paso por aquí 2.2")
        stability, T_EIG = calculate_small_signal(d_raw_data, d_op, grid, d_grid, d_sg, d_vsc, d_pf)
    else:
        print('Base case power flow does not converge')
    cases = 0
    print("Paso por aquí 3")
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
    futures = []

    print(f"Total simulations to do of contingency cases: {total_cases}")


    # ==============START SIMULATIONS======================================================
    # Probability of failure (100% means any component you deactivate will fail)
    FAILURE_PROBABILITY = 100
    # ======================[ LINES ]======================
    # ------------------ Simulate first-level failures ------------------

    for idx, line in enumerate(grid.lines):
        line.active = False
        cases += 1
        print("First_level_Lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
        #stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)
        
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
            'islands': islands
        }
        futures.append(result)
        print("Deberia pasar por aqui")
        if DEBUG:

            print("abans futures")
            futures = compss_wait_on(futures)
            with open("results_parallel.json", "w") as f:
                json.dump(futures, f, indent=2)
            print("Results saved to results_parallel.jsonl")
            sys.exit()
            
            

        # 1) Second-level failures on lines
        for idx2, line2 in enumerate(grid.lines):
            if idx2 != idx:
                line2.active = False
                cases += 1
                print("Second_level_Lines-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

                stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                    'islands': islands
                }
                futures.append(result)
                line2.active = True
            

        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            cases += 1
            print("Second_level_Lines-transformers:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

            result = {
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
                'islands': islands
            }
            futures.append(result)

            transformer.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            cases += 1
            print("Second_level_Lines-generators:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

            result = {
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
                'islands': islands
            }
            futures.append(result)

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
        stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
            'islands': islands
        }
        futures.append(result)

        # 1) Second-level failures on transformers
        for idx2, transformer2 in enumerate(grid.transformers2w):
            if idx2 != idx:
                transformer2.active = False
                cases += 1
                print("Second_level_Transformers-transformers:", cases, '/', total_cases,
                      f'({cases / total_cases * 100:.2f}%)')
                stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                    'islands': islands
                }
                futures.append(result)

                transformer2.active = True

        # 2) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False
            cases += 1
            print("Second_level_Transformers-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                'islands': islands
            }
            futures.append(result)

            line.active = True

        # 3) Second-level failures on generators
        for idx2, generator in enumerate(grid.generators):
            generator.active = False
            cases += 1
            print("Second_level_Transformers-generators:", cases, '/', total_cases,
                  f'({cases / total_cases * 100:.2f}%)')
            stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                'islands': islands
            }
            futures.append(result)

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
        stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
            'islands': islands
        }
        futures.append(result)

        # 1) Second-level failures on lines
        for idx2, line in enumerate(grid.lines):
            line.active = False
            cases += 1
            print("Second_level_Generators-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
            stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                'islands': islands
            }
            futures.append(result)

            line.active = True
        # 2) Second-level failures on transformers
        for idx2, transformer in enumerate(grid.transformers2w):
            transformer.active = False
            cases += 1
            print("Second_level_Generators-transformers:", cases, '/', total_cases,
                  f'({cases / total_cases * 100:.2f}%)')
            stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                'islands': islands
            }
            futures.append(result)

            transformer.active = True
        # 3) Second-level failures on generators
        for idx2, generator2 in enumerate(grid.generators):
            if idx2 != idx:
                generator2.active = False
                cases += 1
                print("Second_level_Generators-generators:", cases, '/', total_cases,
                      f'({cases / total_cases * 100:.2f}%)')
                stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid, d_grid, d_raw_data)

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
                    'islands': islands
                }
                futures.append(result)

                generator2.active = True
        generator.active = True
    # Ensure all components are active again
    check(grid)
    print('Generators done')

    # TODO: Canviar al fitxer de Nord4
    futures = compss_wait_on(futures)
    with open("results_parallel.json", "w") as f:
        json.dump(futures, f, indent=2)
    print("Results saved to results_parallel.jsonl")
