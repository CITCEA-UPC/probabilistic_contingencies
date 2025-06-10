#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

import GridCalEngine.api as gce
import json
import networkx as nx

import os
import pandas as pd
from stability_analysis.preprocess import preprocess_data, read_data, process_raw
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus, fill_d_grid_after_powerflow
from stability_analysis.preprocess import parameters

from stability_analysis.state_space import build_ss, generate_NET, generate_elements
from stability_analysis.analysis import small_signal
import warnings

warnings.filterwarnings("ignore", category=FutureWarning, message=".*connect\\(\\) is deprecated; use interconnect\\(\\).*")
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=r".*Series\.__getitem__ treating keys as positions is deprecated.*"
)

import copy
from concurrent.futures import ProcessPoolExecutor, as_completed

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

def check_stability_and_pf(grid, d_grid, d_raw_data, d_op, d_sg, d_vsc):
    """
    Ejecuta powerflow y small-signal usando d_op, d_sg, d_vsc según la lógica original.
    Devuelve (stability, T_EIG, pf_converged, run_pf_converged) o (error, None, None, None).
    """
    pf_results = GridCal_powerflow.run_powerflow(grid, Qconrol_mode=False)
    try:
        # Update PF results and operation point of generator elements
        d_pf = process_powerflow.update_OP(grid, pf_results, d_raw_data)

        # fill_d_grid necesita d_op
        d_grid, d_pf = fill_d_grid_after_powerflow.fill_d_grid(
            d_grid, grid, d_pf, d_raw_data, d_op
        )

        # %% READ PARAMETERS
        d_grid = parameters.get_params(d_grid, d_sg, d_vsc)
        d_grid = slack_bus.assign_slack(d_grid)
        d_grid, REF_w, num_slk, delta_slk = slack_bus.delta_slk(d_grid)

        # %% GENERATE STATE-SPACE MODEL
        connect_fun = 'append_and_connect'
        save_ss_matrices = False

        l_blocks, l_states, d_grid = generate_NET.generate_SS_NET_blocks(
            d_grid, delta_slk, connect_fun, save_ss_matrices
        )
        l_blocks, l_states = generate_elements.generate_SS_elements(
            d_grid, delta_slk, l_blocks, l_states, connect_fun, save_ss_matrices
        )

        # %% BUILD FULL SYSTEM STATE-SPACE MODEL
        var_in = ['NET_Rld1']
        var_out = ['all']
        inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
        ss_sys = build_ss.connect(
            l_blocks, l_states, inputs, outputs, connect_fun, save_ss_matrices
        )

        # %% SMALL-SIGNAL ANALYSIS
        T_EIG = small_signal.FEIG(ss_sys, False)

        if max(T_EIG['real'] >= 0):
            stability = 0
        else:
            stability = 1

        return stability, T_EIG, gce.power_flow(grid).converged, pf_results.convergence_reports[0].converged_[0]
    except Exception as e:
        # Mantengo el print para debug en cada proceso
        print(f"Error during stability check: {e}")
        return e, None, None, None

# Función para fallo simple en proceso paralelo
def simulate_single(args):
    """
    args: (element_type, idx, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc)
    Devuelve un dict igual al que añades en results['single'].
    """
    element_type, idx, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc = args
    # Reconstruir grid fresco
    grid = gce.open_file(GRID_FILE)
    # Reconstruir d_grid y d_raw_data y d_op, d_sg, d_vsc
    d_grid = copy.deepcopy(base_d_grid)
    d_raw_data = copy.deepcopy(base_d_raw_data)
    d_op = copy.deepcopy(base_d_op)
    d_sg = copy.deepcopy(base_d_sg)
    d_vsc = copy.deepcopy(base_d_vsc)

    # Desactivar el elemento
    if element_type == 'line':
        grid.lines[idx].active = False
    elif element_type == 'transformer':
        grid.transformers2w[idx].active = False
    elif element_type == 'generator':
        grid.generators[idx].active = False

    stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(
        grid, d_grid, d_raw_data, d_op, d_sg, d_vsc
    )
    islands = detect_islands(grid)

    return {
        'element': {'type': element_type, 'id': idx},
        'gce.powerflow_converged': pf_converged,
        'gce.run_powerflow_converged': run_pf_converged,
        'stability': stability,
        'islands': islands
    }

# Función para doble fallo en proceso paralelo
def simulate_double(args):
    """
    args: (el1, idx1, el2, idx2, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc)
    Devuelve un dict igual al que añades en results['double'].
    """
    el1, idx1, el2, idx2, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc = args
    grid = gce.open_file(GRID_FILE)
    d_grid = copy.deepcopy(base_d_grid)
    d_raw_data = copy.deepcopy(base_d_raw_data)
    d_op = copy.deepcopy(base_d_op)
    d_sg = copy.deepcopy(base_d_sg)
    d_vsc = copy.deepcopy(base_d_vsc)

    # Desactivar ambos
    if el1 == 'line':
        grid.lines[idx1].active = False
    elif el1 == 'transformer':
        grid.transformers2w[idx1].active = False
    elif el1 == 'generator':
        grid.generators[idx1].active = False

    if el2 == 'line':
        grid.lines[idx2].active = False
    elif el2 == 'transformer':
        grid.transformers2w[idx2].active = False
    elif el2 == 'generator':
        grid.generators[idx2].active = False

    stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(
        grid, d_grid, d_raw_data, d_op, d_sg, d_vsc
    )
    islands = detect_islands(grid)

    return {
        'elements': [
            {'type': el1, 'id': idx1},
            {'type': el2, 'id': idx2}
        ],
        'gce.powerflow_converged': pf_converged,
        'gce.run_powerflow_converged': run_pf_converged,
        'stability': stability,
        'islands': islands
    }

if __name__ == "__main__":
    # Path to the grid file
    GRID_FILE = 'stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw'

    # Open the grid una vez para contar componentes
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
    excel_lines_ratings = os.path.join(path_data, "cases", excel_lines_ratings + ".csv")

    d_raw_data = process_raw.read_raw(GRID_FILE)
    d_op = read_data.read_data(excel_op)

    # FOR the 118-bus system
    d_raw_data['generator']['Region'] = d_op['Generators']['Region']
    d_raw_data['load']['Region'] = d_op['Loads']['Region']
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
    # Print the total counts de cada componente
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

    # Preparar estructura results igual que antes
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

    # Crear copias base para pasar a los procesos
    base_d_grid = copy.deepcopy(d_grid)
    base_d_raw_data = copy.deepcopy(d_raw_data)
    base_d_op = copy.deepcopy(d_op)
    base_d_sg = copy.deepcopy(d_sg)
    base_d_vsc = copy.deepcopy(d_vsc)

    num_workers = os.cpu_count() or 1
    executor = ProcessPoolExecutor(max_workers=num_workers)

    # --------------------
    # 1) FALLAS SIMPLES
    single_tasks = []
    for idx in range(num_lines):
        single_tasks.append(('line', idx, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    for idx in range(num_transformers):
        single_tasks.append(('transformer', idx, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    for idx in range(num_generators):
        single_tasks.append(('generator', idx, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))

    print("Starting parallel single contingencies...")
    futures_single = {executor.submit(simulate_single, args): args for args in single_tasks}
    cases_done = 0
    for fut in as_completed(futures_single):
        res = fut.result()
        etype = res['element']['type']
        results['single'][etype].append(res)
        cases_done += 1
        if cases_done % 10 == 0 or cases_done == len(single_tasks):
            print(f"Single cases done: {cases_done}/{len(single_tasks)} ({cases_done/total_cases*100:.2f}% of total approx)")

    # --------------------
    # 2) FALLAS DOBLES
    double_tasks = []
    # LINE-LINE
    for i in range(num_lines):
        for j in range(num_lines):
            if j != i:
                double_tasks.append(('line', i, 'line', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # LINE-TRANSFORMER
    for i in range(num_lines):
        for j in range(num_transformers):
            double_tasks.append(('line', i, 'transformer', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # LINE-GENERATOR
    for i in range(num_lines):
        for j in range(num_generators):
            double_tasks.append(('line', i, 'generator', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # TRANSFORMER-TRANSFORMER
    for i in range(num_transformers):
        for j in range(num_transformers):
            if j != i:
                double_tasks.append(('transformer', i, 'transformer', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # TRANSFORMER-LINE
    for i in range(num_transformers):
        for j in range(num_lines):
            double_tasks.append(('transformer', i, 'line', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # TRANSFORMER-GENERATOR
    for i in range(num_transformers):
        for j in range(num_generators):
            double_tasks.append(('transformer', i, 'generator', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # GENERATOR-GENERATOR
    for i in range(num_generators):
        for j in range(num_generators):
            if j != i:
                double_tasks.append(('generator', i, 'generator', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # GENERATOR-LINE
    for i in range(num_generators):
        for j in range(num_lines):
            double_tasks.append(('generator', i, 'line', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))
    # GENERATOR-TRANSFORMER
    for i in range(num_generators):
        for j in range(num_transformers):
            double_tasks.append(('generator', i, 'transformer', j, GRID_FILE, base_d_grid, base_d_raw_data, base_d_op, base_d_sg, base_d_vsc))

    print("Starting parallel double contingencies...")
    futures_double = {executor.submit(simulate_double, args): args for args in double_tasks}
    cases_done = 0
    for fut in as_completed(futures_double):
        res = fut.result()
        el1 = res['elements'][0]['type']
        el2 = res['elements'][1]['type']
        results['double'][el1][el2].append(res)
        cases_done += 1
        if cases_done % 50 == 0 or cases_done == len(double_tasks):
            print(f"Double cases done: {cases_done}/{len(double_tasks)} ({(cases_done+len(single_tasks))/total_cases*100:.2f}% of total approx)")

    executor.shutdown()

    # Asegurar restauración final
    check(grid)
    print('All done, writing results.json...')

    with open('results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print("Results saved to results.json")
