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
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from stability_analysis.preprocess import parameters
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from small_signal_analysis import *
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, assign_PQ_Loads_to_grid, assign_SlackBus_to_grid
import warnings
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from functools import partial

file_lock = threading.Lock()

warnings.filterwarnings("ignore", category=FutureWarning, message=".*connect\\(\\) is deprecated; use interconnect\\(\\).*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*Series\.__getitem__ treating keys as positions is deprecated.*")

def read_excel_sheets_as_dict(file_path):
    xls = pd.read_excel(file_path, sheet_name=None)
    return xls

def detect_islands(grid):
    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)
    islas_list = nc.split_into_islands()
    return len(islas_list) > 1

def check_line_overloads(results, grid):
    overloaded_lines = []
    for idx, (loading, branch) in enumerate(zip(results.loading, grid.get_branches())):
        if loading > 1:
            overloaded_lines.append(idx)
    return overloaded_lines

def check(grid):
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
    pf_results = GridCal_powerflow.run_powerflow(grid, Qconrol_mode=False)
    try:
        d_pf = process_powerflow.update_OP(grid, pf_results, d_raw_data)
        d_grid, d_pf = fill_d_grid_after_powerflow.fill_d_grid(d_grid, grid, d_pf, d_raw_data, d_op)
        d_grid = parameters.get_params(d_grid, d_sg, d_vsc)
        d_grid = slack_bus.assign_slack(d_grid)
        d_grid, REF_w, num_slk, delta_slk = slack_bus.delta_slk(d_grid)
        connect_fun = 'append_and_connect'
        save_ss_matrices = False
        l_blocks, l_states, d_grid = generate_NET.generate_SS_NET_blocks(d_grid, delta_slk, connect_fun, save_ss_matrices)
        l_blocks, l_states = generate_elements.generate_SS_elements(d_grid, delta_slk, l_blocks, l_states, connect_fun, save_ss_matrices)
        var_in = ['NET_Rld1']
        var_out = ['all']
        inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
        ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs, connect_fun, save_ss_matrices)
        T_EIG = small_signal.FEIG(ss_sys, False)
        if max(T_EIG['real'] >= 0):
            stability = 0
        else:
            stability = 1
        return stability, T_EIG, gce.power_flow(grid).converged, pf_results.convergence_reports[0].converged_[0]
    except Exception as e:
        print(f"Error during stability check: {e}")
        return str(e), None, None, None

def remove_existing_result_file(path='results_secuencial.jsonl'):
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed existing file: {path}")
    else:
        print(f"No existing file found at: {path}")

def save_result(result, path='results_secuencial.jsonl'):
    def to_serializable(obj):
        if isinstance(obj, (np.bool_, np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, BaseException):
            return str(obj)
        return str(obj)
    with file_lock:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, default=to_serializable) + '\n')

def read_results_jsonl(route='results_secuencial.jsonl'):
    with open(route) as f:
        return [json.loads(line) for line in f]

def simular_contingencia(args, GRID_FILE, d_grid, d_raw_data, d_op, d_sg, d_vsc):
    """
    Ejecuta una simulación de contingencia desactivando los elementos indicados.
    Devuelve un diccionario con los resultados.
    """
    case_id, tipo1, idx1, tipo2, idx2 = args
    # Recarga/copias los datos necesarios
    grid_local = gce.open_file(GRID_FILE)
    d_grid_local = copy.deepcopy(d_grid)
    d_raw_data_local = copy.deepcopy(d_raw_data)
    # Desactiva los elementos según el tipo
    if tipo1 == 'line':
        grid_local.lines[idx1].active = False
    elif tipo1 == 'transformer':
        grid_local.transformers2w[idx1].active = False
    elif tipo1 == 'generator':
        grid_local.generators[idx1].active = False
    if tipo2 is not None:
        if tipo2 == 'line':
            grid_local.lines[idx2].active = False
        elif tipo2 == 'transformer':
            grid_local.transformers2w[idx2].active = False
        elif tipo2 == 'generator':
            grid_local.generators[idx2].active = False
    stability, T_EIG, pf_converged, run_pf_converged = check_stability_and_pf(
        grid_local, d_grid_local, d_raw_data_local, d_op, d_sg, d_vsc
    )
    return {
        'case_id': case_id,
        'level': 'double' if tipo2 is not None else 'single',
        'type_combo': (tipo1, tipo2) if tipo2 is not None else tipo1,
        'elements': [
            {'type': tipo1, 'id': idx1},
            {'type': tipo2, 'id': idx2}
        ] if tipo2 is not None else [{'type': tipo1, 'id': idx1}],
        'gce.powerflow_converged': pf_converged,
        'gce.run_powerflow_converged': run_pf_converged,
        'stability': stability,
        'islands': detect_islands(grid_local)
    }

def generar_casos(num_lines, num_transformers, num_generators):
    casos = []
    case_id = 1
    # Fallos simples
    for idx in range(num_lines):
        casos.append((case_id, 'line', idx, None, None))
        case_id += 1
    for idx in range(num_transformers):
        casos.append((case_id, 'transformer', idx, None, None))
        case_id += 1
    for idx in range(num_generators):
        casos.append((case_id, 'generator', idx, None, None))
        case_id += 1
    # Fallos dobles línea-línea
    for idx1 in range(num_lines):
        for idx2 in range(num_lines):
            if idx2 != idx1:
                casos.append((case_id, 'line', idx1, 'line', idx2))
                case_id += 1
    # Fallos dobles línea-transformador
    for idx1 in range(num_lines):
        for idx2 in range(num_transformers):
            casos.append((case_id, 'line', idx1, 'transformer', idx2))
            case_id += 1
    # Fallos dobles línea-generador
    for idx1 in range(num_lines):
        for idx2 in range(num_generators):
            casos.append((case_id, 'line', idx1, 'generator', idx2))
            case_id += 1
    # Fallos dobles transformador-transformador
    for idx1 in range(num_transformers):
        for idx2 in range(num_transformers):
            if idx2 != idx1:
                casos.append((case_id, 'transformer', idx1, 'transformer', idx2))
                case_id += 1
    # Fallos dobles transformador-línea
    for idx1 in range(num_transformers):
        for idx2 in range(num_lines):
            casos.append((case_id, 'transformer', idx1, 'line', idx2))
            case_id += 1
    # Fallos dobles transformador-generador
    for idx1 in range(num_transformers):
        for idx2 in range(num_generators):
            casos.append((case_id, 'transformer', idx1, 'generator', idx2))
            case_id += 1
    # Fallos dobles generador-generador
    for idx1 in range(num_generators):
        for idx2 in range(num_generators):
            if idx2 != idx1:
                casos.append((case_id, 'generator', idx1, 'generator', idx2))
                case_id += 1
    # Fallos dobles generador-línea
    for idx1 in range(num_generators):
        for idx2 in range(num_lines):
            casos.append((case_id, 'generator', idx1, 'line', idx2))
            case_id += 1
    # Fallos dobles generador-transformador
    for idx1 in range(num_generators):
        for idx2 in range(num_transformers):
            casos.append((case_id, 'generator', idx1, 'transformer', idx2))
            case_id += 1
    return casos

def inicializar_grid_y_datos():
    GRID_FILE = 'stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw'
    grid = gce.open_file(GRID_FILE)
    filename= 'stability_analysis/stability_analysis/data/cases/IEEE118_NREL_stable_'
    d_grid = read_excel_sheets_as_dict(filename+'d_grid.xlsx')
    d_raw_data = read_excel_sheets_as_dict(filename+'d_raw_data.xlsx')
    d_opf = read_excel_sheets_as_dict(filename+'d_opf.xlsx')
    d_op = read_excel_sheets_as_dict(filename+'d_op.xlsx')
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
    d_sg = read_data.read_data(excel_sg)
    d_vsc = read_data.read_data(excel_vsc)
    num_lines = len(grid.lines)
    num_generators = len(grid.generators)
    num_transformers = len(grid.transformers2w)
    print(f"Number of lines: {num_lines}")
    print(f"Number of generators: {num_generators}")
    print(f"Number of transformers: {num_transformers}")
    assign_Generators_to_grid.assign_PVGen(GridCal_grid=grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=True, solved_point=True, d_pf=d_opf)
    assign_PQ_Loads_to_grid.assign_PQ_load(grid, d_raw_data)
    for bus in grid.buses:
        bus_num = int(bus.code)
        idx = d_opf['pf_bus'].query('bus == @bus_num').index[0]
        bus.Vm0 = d_opf['pf_bus'].loc[idx, 'Vm']
        bus.Va0 = d_opf['pf_bus'].loc[idx, 'theta'] / 180 * np.pi
    slack_bus_num = d_grid['T_global'].loc[0, 'ref_bus']
    assign_SlackBus_to_grid.assign_slack_bus(grid, slack_bus_num)
    pf_results = GridCal_powerflow.run_powerflow(grid,SolverType.NR,Qconrol_mode=False)
    remove_existing_result_file('results_secuencial.jsonl')
    if pf_results.convergence_reports[0].converged_[0]:
        d_pf = process_powerflow.update_OP(grid, pf_results, d_raw_data)
        stability, T_EIG = calculate_small_signal(d_raw_data, d_op, grid, d_grid, d_sg, d_vsc, d_pf)
    else:
        print('Base case power flow does not converge')
    return GRID_FILE, grid, d_grid, d_raw_data, d_opf, d_op, d_sg, d_vsc, num_lines, num_generators, num_transformers

if __name__ == "__main__":
    GRID_FILE, grid, d_grid, d_raw_data, d_opf, d_op, d_sg, d_vsc, num_lines, num_generators, num_transformers = inicializar_grid_y_datos()
    # Generar lista de casos de contingencia
    casos = generar_casos(num_lines, num_transformers, num_generators)
    print(f"Total contingency cases to simulate: {len(casos)}")
    # Paralelización de simulaciones
    simular = partial(simular_contingencia, GRID_FILE=GRID_FILE, d_grid=d_grid, d_raw_data=d_raw_data, d_op=d_op, d_sg=d_sg, d_vsc=d_vsc)
    with ProcessPoolExecutor(max_workers=8) as executor:  # Cambia 8 por el número de núcleos que quieras usar
        futuros = [executor.submit(simular, caso) for caso in casos]
        for f in tqdm(as_completed(futuros), total=len(casos)):
            resultado = f.result()
            save_result(resultado, path='results_secuencial.jsonl')
            print(f"Simulación {resultado['case_id']}/{len(casos)} completada")
    print("Resultados guardados en results_secuencial.jsonl")
