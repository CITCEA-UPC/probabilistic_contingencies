#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import GridCalEngine as gce
import json
import os
import threading
import warnings
import numpy as np
import pandas as pd
import copy
import pickle
import sys
import os
import socket
# from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType

# Small signal imports
from small_signal_analysis import *
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, assign_PQ_Loads_to_grid, \
    assign_SlackBus_to_grid
from stability_analysis.optimal_power_flow import process_optimal_power_flow
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow
from stability_analysis.preprocess import read_data

'''from small_signal_analysis import *
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, assign_PQ_Loads_to_grid, assign_SlackBus_to_grid
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow
from stability_analysis.preprocess import read_data'''

global DEBUG
global LOGS
global DEBUG_PYCOMPSS
global NORD4

DEBUG = False
LOGS = False
DEBUG_PYCOMPSS = False
NORD4 = False
HOME = os.path.expanduser("~")

hostname = socket.gethostname()
if hostname != 'endor':  # Para saber si se ejecuta en local o en NORD4
    NORD4 = True
    HOME = os.path.expanduser("~")

if NORD4:
    stability_analysis_path = os.path.join(
        HOME, "probabilistic_contingencies/stability_analysis")
    sys.path.append(stability_analysis_path)
    print(os.path.abspath("."))
else:
    sys.path.append("rC:\\Users\\alexu\\Desktop\\git\probabilistic_contingencies")
# PyCOMPSs imports
try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
    from pycompss.api.constraint import constraint
except ImportError:
    from datagen.datagen.dummies.task import task
    from datagen.datagen.dummies.api import compss_wait_on
    from datagen.datagen.dummies.constraint import constraint

if LOGS:
    import logging

    logging.basicConfig(level=logging.DEBUG)


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


# def check_stability_and_pf(**kwargs):

@constraint(computing_units=20)
@task(returns=5)
def check_stability_and_pf(path, d_grid, d_raw_data, d_op, d_sg, d_vsc, d_pf):
    grid = gce.open_file(path)

    '''grid = kwargs["grid"]
    d_grid = kwargs["d_grid"]
    d_raw_data = kwargs["d_raw_data"]'''

    pf_results = None
    pf_converged = None
    run_pf_results = None
    run_pf_converged = None
    islands = None
    stability = None
    error = False

    try:
        pf_results = gce.power_flow(grid)
        pf_converged = bool(pf_results.converged)
    except Exception as e:

        print(f"Error during powerflow and run powerflow check: {e}")
        # gce.save_file(grid, "exemple.gridcal")
        # sys.exit()
        error = str(e)

    try:
        run_pf_results = GridCal_powerflow.run_powerflow(grid, Qconrol_mode=False)
        run_pf_converged = bool(run_pf_results.convergence_reports[0].converged_[0])

        # Update PF results and operation point of generator elements
        d_pf = process_powerflow.update_OP(grid, run_pf_results, d_raw_data)
        d_grid, d_pf = fill_d_grid_after_powerflow.fill_d_grid(d_grid, grid, d_pf, d_raw_data, d_op)

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

        l_blocks, l_states, d_grid = generate_NET.generate_SS_NET_blocks(d_grid, delta_slk, connect_fun,
                                                                         save_ss_matrices)

        # Generate generator units State-Space Model
        l_blocks, l_states = generate_elements.generate_SS_elements(d_grid, delta_slk, l_blocks, l_states, connect_fun,
                                                                    save_ss_matrices)

        # %% BUILD FULL SYSTEM STATE-SPACE MODEL

        # Define full system inputs and ouputs
        var_in = ['NET_Rld1']
        var_out = ['all']  # ['all']  # ['GFOR3_w'] #

        # Build full system state-space model

        inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
        # ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs, connect_fun, save_ss_matrices)
        ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs, connect_fun, True)

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

    except Exception as e:
        error = str(e)
        print(f"Error during stability check: {e}")

    return error, stability, pf_converged, run_pf_converged, detect_islands(grid)


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


def create_temp_grids_folder():
    """
    Creates the temp_grids folder if it doesn't exist.
    Takes into account if running on local machine or NORD4.
    """
    if NORD4:
        # On NORD4, use the full path
        temp_grids_path = os.path.join(PATH_NORD4, 'temp_grids')
    else:
        # On local machine, use relative path
        temp_grids_path = 'temp_grids'

    if not os.path.exists(temp_grids_path):
        os.makedirs(temp_grids_path)
        print(f"Created temp_grids folder at: {temp_grids_path}")


def generate_grid_filename(case_id, level, type_combo, elements):
    """
    Generates a filename for the grid based on the contingency case information.

    Parameters:
    - case_id (int): Case identifier
    - level (str): 'single' or 'double'
    - type_combo (str or tuple): Type of contingency combination
    - elements (list): List of elements involved in the contingency

    Returns:
    - str: Generated filename (without folder path)
    """
    if level == 'single':
        return f"case_{case_id}_{type_combo}.gridcal"
    else:
        # For double contingencies
        type1, type2 = type_combo
        return f"case_{case_id}_{type1}_{type2}.gridcal"


def save_grid_to_temp_folder(grid, filename):
    """
    Saves the grid to the temp_grids folder with the specified filename.
    Takes into account if running on local machine or NORD4.

    Parameters:
    - grid: The grid object to save
    - filename (str): The filename (without folder path)

    Returns:
    - str: The full path where the grid was saved
    """
    if NORD4:
        # On NORD4, use the full path
        full_path = os.path.join(PATH_NORD4, 'temp_grids', filename)
    else:
        # On local machine, use relative path
        full_path = os.path.join('temp_grids', filename)

    gce.save_file(grid, full_path)
    return full_path


def load_grid_from_temp_folder(filename):
    """
    Loads a grid from the temp_grids folder with the specified filename.
    Takes into account if running on local machine or NORD4.

    Parameters:
    - filename (str): The filename (without folder path)

    Returns:
    - The loaded grid object
    """
    if NORD4:
        # On NORD4, use the full path
        full_path = os.path.join(PATH_NORD4, 'temp_grids', filename)
    else:
        # On local machine, use relative path
        full_path = os.path.join('temp_grids', filename)

    return gce.open_file(full_path)


@task(returns=1)
def dummy(i):
    print("################ ", i + 1)
    return i + 1


if __name__ == "__main__":
    # Path to the grid file
    '''
    TODO: UPDATE
    Number of lines: 170
    Number of generators: 54
    Number of transformers: 9
    '''

    PATH_NORD4 = os.path.join(HOME, 'probabilistic_contingencies/')
    GRID_FILE = 'stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw'
    filename = 'stability_analysis/stability_analysis/data/cases/IEEE118_NREL_stable_'
    path_data = 'stability_analysis/stability_analysis/data/'
    excel_data = "IEEE_118_FULL"
    excel_lines_ratings = "IEEE_118_Lines"

    if NORD4:
        GRID_FILE = PATH_NORD4 + GRID_FILE
        filename = PATH_NORD4 + filename
        path_data = PATH_NORD4 + path_data

    # Open the grid and info
    grid = gce.open_file(GRID_FILE)
    d_grid = read_excel_sheets_as_dict(filename + 'd_grid.xlsx')
    d_raw_data = read_excel_sheets_as_dict(filename + 'd_raw_data.xlsx')
    d_opf = read_excel_sheets_as_dict(filename + 'd_opf.xlsx')
    d_op = read_excel_sheets_as_dict(filename + 'd_op.xlsx')

    # check d_grid Vn it has to be in [kV] !!
    d_grid['T_SG']['Vn'] = d_grid['T_SG']['Vn'] / 1e3
    d_grid['T_VSC']['Vn'] = d_grid['T_VSC']['Vn'] / 1e3

    # Create temp_grids folder if it doesn't exist
    create_temp_grids_folder()

    assign_Generators_to_grid.assign_PVGen(GridCal_grid=grid, d_raw_data=d_raw_data, d_op=d_op,
                                           voltage_profile_list=True, solved_point=True, d_pf=d_opf)
    # assign_PQ_Loads_to_grid.assign_PQ_load(grid, d_raw_data)

    for bus in grid.buses:
        bus_num = int(bus.code)
        idx = d_opf['pf_bus'].query('bus == @bus_num').index[0]

        bus.Vm0 = d_opf['pf_bus'].loc[idx, 'Vm']
        bus.Va0 = d_opf['pf_bus'].loc[idx, 'theta'] / 180 * np.pi

    slack_bus_num = d_grid['T_global'].loc[0, 'ref_bus']
    assign_SlackBus_to_grid.assign_slack_bus(grid, slack_bus_num)

    excel_sg = os.path.join(path_data, "cases", excel_data + "_data_sg.xlsx")
    excel_vsc = os.path.join(path_data, "cases", excel_data + "_data_vsc.xlsx")
    excel_lines_ratings = os.path.join(path_data, "cases", excel_lines_ratings + ".csv")
    lines_ratings = pd.read_csv(excel_lines_ratings)

    for line in grid.lines:
        bf = int(line.bus_from.code)
        bt = int(line.bus_to.code)
        line.rate = float(lines_ratings.loc[
                              lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[0], 'Max Flow (MW)'])

    for trafo in grid.transformers2w:
        bf = int(trafo.bus_from.code)
        bt = int(trafo.bus_to.code)
        trafo.rate = float(lines_ratings.loc[
                               lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[0], 'Max Flow (MW)'])

    # Read Excel files with system data, generator data, and VSC data
    d_sg = read_data.read_data(excel_sg)
    d_vsc = read_data.read_data(excel_vsc)

    # ----------------------------------------------------------------
    # Print the total counts of each component type
    num_lines = len(grid.lines)
    num_generators = len(grid.generators)
    num_transformers = len(grid.transformers2w)
    from scipy import linalg

    linalg.eig(np.ones([1000, 1000]), left=False, right=False)
    print("OKKKKK, LINALG")

    print(f"Number of lines: {num_lines}")
    print(f"Number of generators: {num_generators}")
    print(f"Number of transformers: {num_transformers}")
    # ----------------------------------------------------------------
    # --------------------------TEST PYCOMPSS--------------------------------------
    if DEBUG_PYCOMPSS:
        print("TESTING PYCOMPSS")
        futures = []
        for i in range(3):
            print(i)
            futures.append(dummy(i))

        futures = compss_wait_on(futures)
        print(futures)

        print("PYCOMPSS OKKKKK")

    # --------------------------TEST PYCOMPSS--------------------------------------

    print("Paso por aquí 0")
    P = list(d_raw_data['load']['PL'])
    Q = list(d_raw_data['load']['QL'])
    for i in range(81):  # Olen(P)):
        grid.loads[i].P = float(P[i])
        grid.loads[i].Q = float(Q[i])
    nc = gce.compile_numerical_circuit_at(grid)
    nc.generator_data.cost_0[:] = 0
    nc.generator_data.cost_1[:] = 0
    nc.generator_data.cost_2[:] = 0

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, tolerance=1e-8,
                                      control_q='Direct')  # , max_iter=100)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NR, verbose=0, ips_tolerance=1e-4,
                                              ips_iterations=50)

    pf_results = multi_island_pf_nc(nc=nc, options=pf_options)

    # Calculate Power Flow
    print("Paso por aquí 1")
    d_opf_results = ac_optimal_power_flow(nc=nc,
                                          pf_options=pf_options,
                                          opf_options=opf_options,
                                          # debug: bool = False,
                                          # use_autodiff = True,
                                          pf_init=False,
                                          Sbus_pf=pf_results.Sbus,
                                          voltage_pf=pf_results.voltage,
                                          plot_error=False)

    # Remove old file if it exists

    # remove_existing_result_file('results_parallel.jsonl')

    print("Paso por aquí 2")
    if d_opf_results.converged:
        d_pf = process_optimal_power_flow.update_OP(grid, d_opf_results, d_raw_data)
        print("Paso por aquí 2.2")
        stability, T_EIG = calculate_small_signal(d_raw_data, d_op, grid, d_grid, d_sg, d_vsc, d_pf)
    else:
        print('Base case power flow does not converge')
    cases = 0
    print(stability, T_EIG)
    #sys.exit()

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

    # Save grid for base case
    base_filename = "base_case.gridcal"
    base_path = save_grid_to_temp_folder(grid, base_filename)
    error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(base_path, d_grid, d_raw_data,
                                                                                       d_op, d_sg, d_vsc, d_pf)
    result = {
        'errors': error,
        'case_id': cases,
        'level': 'single',
        'type_combo': 'line',
        'elements': [
            {'type': 'line', 'id': 1}
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
        print(futures)
        temp_path = "results_partial.json"
        if NORD4:
            temp_path = PATH_NORD4 + temp_path
        with open(temp_path, "w") as f:
            json.dump(futures, f, indent=2)
        print("Results saved to results_partial.json")
        sys.exit()

    for idx, line in enumerate(grid.lines):
        line.active = False
        cases += 1
        print("First_level_Lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')

        # Generate filename and save grid
        filename = generate_grid_filename(cases, 'single', 'line', [{'type': 'line', 'id': idx}])
        grid_path = save_grid_to_temp_folder(grid, filename)
        error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                           d_raw_data, d_op, d_sg,
                                                                                           d_vsc, d_pf)

        result = {
            'errors': error,
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
            print(futures)
            temp_path = "results_temporal.json"
            if NORD4:
                temp_path = PATH_NORD4 + temp_path
            with open(temp_path, "w") as f:
                json.dump(futures, f, indent=2)
            print("Results saved to results_parallel.json")
            sys.exit()

        # 1) Second-level failures on lines
        for idx2, line2 in enumerate(grid.lines):
            if idx2 != idx:
                line2.active = False
                cases += 1
                print("Second_level_Lines-lines:", cases, '/', total_cases, f'({cases / total_cases * 100:.2f}%)')
                # Generate filename and save grid
                filename = generate_grid_filename(cases, 'double', ('line', 'line'),
                                                  [{'type': 'line', 'id': idx}, {'type': 'line', 'id': idx2}])
                grid_path = save_grid_to_temp_folder(grid, filename)
                error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                                   d_raw_data, d_op,
                                                                                                   d_sg, d_vsc, d_pf)

                result = {
                    'errors': error,
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
            # Generate filename and save grid
            filename = generate_grid_filename(cases, 'double', ('line', 'transformer'),
                                              [{'type': 'line', 'id': idx}, {'type': 'transformer', 'id': idx2}])
            grid_path = save_grid_to_temp_folder(grid, filename)
            error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                               d_raw_data, d_op, d_sg,
                                                                                               d_vsc, d_pf)
            result = {
                'errors': error,
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
            # Generate filename and save grid
            filename = generate_grid_filename(cases, 'double', ('line', 'generator'),
                                              [{'type': 'line', 'id': idx}, {'type': 'generator', 'id': idx2}])
            grid_path = save_grid_to_temp_folder(grid, filename)
            error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                               d_raw_data, d_op, d_sg,
                                                                                               d_vsc, d_pf)

            result = {
                'errors': error,
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
        # Generate filename and save grid
        filename = generate_grid_filename(cases, 'single', 'transformer', [{'type': 'transformer', 'id': idx}])
        grid_path = save_grid_to_temp_folder(grid, filename)
        error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                           d_raw_data, d_op, d_sg,
                                                                                           d_vsc, d_pf)

        result = {
            'errors': error,
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
                # Generate filename and save grid
                filename = generate_grid_filename(cases, 'double', ('transformer', 'transformer'),
                                                  [{'type': 'transformer', 'id': idx},
                                                   {'type': 'transformer', 'id': idx2}])
                grid_path = save_grid_to_temp_folder(grid, filename)
                error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                                   d_raw_data, d_op,
                                                                                                   d_sg, d_vsc, d_pf)

                result = {
                    'errors': error,
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
            # Generate filename and save grid
            filename = generate_grid_filename(cases, 'double', ('transformer', 'line'),
                                              [{'type': 'transformer', 'id': idx}, {'type': 'line', 'id': idx2}])
            grid_path = save_grid_to_temp_folder(grid, filename)
            error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                               d_raw_data, d_op, d_sg,
                                                                                               d_vsc, d_pf)

            result = {
                'errors': error,
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
            # Generate filename and save grid
            filename = generate_grid_filename(cases, 'double', ('transformer', 'generator'),
                                              [{'type': 'transformer', 'id': idx}, {'type': 'generator', 'id': idx2}])
            grid_path = save_grid_to_temp_folder(grid, filename)
            error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                               d_raw_data, d_op, d_sg,
                                                                                               d_vsc, d_pf)

            result = {
                'errors': error,
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
        # Generate filename and save grid
        filename = generate_grid_filename(cases, 'single', 'generator', [{'type': 'generator', 'id': idx}])
        grid_path = save_grid_to_temp_folder(grid, filename)
        error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                           d_raw_data, d_op, d_sg,
                                                                                           d_vsc, d_pf)

        result = {
            'errors': error,
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
            # Generate filename and save grid
            filename = generate_grid_filename(cases, 'double', ('generator', 'line'),
                                              [{'type': 'generator', 'id': idx}, {'type': 'line', 'id': idx2}])
            grid_path = save_grid_to_temp_folder(grid, filename)
            error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                               d_raw_data, d_op, d_sg,
                                                                                               d_vsc, d_pf)

            result = {
                'errors': error,
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
            # Generate filename and save grid
            filename = generate_grid_filename(cases, 'double', ('generator', 'transformer'),
                                              [{'type': 'generator', 'id': idx}, {'type': 'transformer', 'id': idx2}])
            grid_path = save_grid_to_temp_folder(grid, filename)
            error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                               d_raw_data, d_op, d_sg,
                                                                                               d_vsc, d_pf)

            result = {
                'errors': error,
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
                # Generate filename and save grid
                filename = generate_grid_filename(cases, 'double', ('generator', 'generator'),
                                                  [{'type': 'generator', 'id': idx}, {'type': 'generator', 'id': idx2}])
                grid_path = save_grid_to_temp_folder(grid, filename)
                error, stability, pf_converged, run_pf_converged, islands = check_stability_and_pf(grid_path, d_grid,
                                                                                                   d_raw_data, d_op,
                                                                                                   d_sg, d_vsc, d_pf)

                result = {
                    'errors': error,
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

    futures = compss_wait_on(futures)
    path_json = results_parallel.json
    if NORD4:
        path_json = PATH_NORD4 + path_json
    with open(path_json, "w") as f:
        json.dump(futures, f, indent=2)
    print("Results saved to results_parallel.jsonl")
