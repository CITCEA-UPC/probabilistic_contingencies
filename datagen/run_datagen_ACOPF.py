import random
import os
import yaml
from datetime import datetime

from datagen import parse_args, parse_setup_file
from datagen.src.dimensions import Dimension
from datagen.src.start_app import start
from datagen.src.objective_function_ACOPF import feasible_power_flow_ACOPF

from stability_analysis.preprocess import preprocess_data, read_data, \
    process_raw
from stability_analysis.powerflow import GridCal_powerflow
from stability_analysis.preprocess.utils import *

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
except ImportError:
    from datagen.dummies.task import task
    from datagen.dummies.api import compss_wait_on

import warnings
warnings.filterwarnings("ignore")

@task()
def main(working_dir='', path_data='', setup_path=''):
    # %% Parse arguments (emulate sys.argv list as input)
    working_dir, path_data, setup_path = parse_args(
        [None, working_dir, path_data, setup_path])
    (generators_power_factor, grid_name, loads_power_factor, n_cases, n_pf,
     n_samples, seed, v_min_v_max_delta_v, voltage_profile, rel_tolerance,
     max_depth, setup_dict) = \
        parse_setup_file(setup_path)

    # Slurm configuration
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
    # Get computing units assigned to the objective function
    cu = os.environ.get("COMPUTING_UNITS", default=None)
    cu_str = ""
    if cu:
        cu_str = f"_cu{cu}"
    print("COMPUTING_UNITS: ", cu)
    # Get slurm job id
    slurm_job_id = os.getenv("SLURM_JOB_ID", default=None)
    slurm_str = ""
    if slurm_job_id:
        slurm_str = f"_slurm{slurm_job_id}"
    # Get slurm n_nodes
    slurm_num_nodes = os.environ.get('SLURM_JOB_NUM_NODES', default=None)
    slurm_nodes_str = ""
    if slurm_num_nodes:
        slurm_nodes_str = f"_nodes{slurm_num_nodes}"
    print("NUMBER OF NODES: ", slurm_num_nodes)
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)

    # CASE CONFIGURATION
    # Create unique directory name for results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd_num = random.randint(1000, 9999)
    dir_name = f"datagen_ACOPF{slurm_str}{cu_str}{slurm_nodes_str}_LF09_seed{seed}_nc{n_cases}" \
               f"_ns{n_samples}_d{max_depth}_{timestamp}_{rnd_num}"
    path_results = os.path.join(
        working_dir, "results", dir_name)
    if not os.path.isdir(path_results):
        os.makedirs(path_results)

    # Save yaml setup in the results directory
    with open(os.path.join(path_results, 'case_setup.yaml'), 'w') as f:
        yaml.dump(setup_dict, f)

    # %% SET FILE NAMES AND PATHS
    if grid_name == 'IEEE9':
        # IEEE 9
        raw = "ieee9_hypersim"
        excel_headers = "IEEE_9_headers"
        excel_data = "IEEE_9"
        excel_op = "OperationData_IEEE_9"
    elif grid_name == 'IEEE118':
        # IEEE 118
        raw = "IEEE118busNREL"
        # excel_headers = "IEEE_118bus_TH"  # THÉVENIN
        # excel_headers = "IEEE_118_01"  # SG
        excel_headers = "IEEE_118_FULL_headers"
        excel_data = "IEEE_118_FULL"
        excel_op = "OperationData_IEEE_118_NREL"
        excel_lines_ratings = "IEEE_118_Lines"
    else:
        raise ValueError(f"Grid {grid_name} not implemented")

    raw_file = os.path.join(path_data, "raw", raw + ".raw")
    excel_sys = os.path.join(path_data, "cases", excel_headers + ".xlsx")
    excel_sg = os.path.join(path_data, "cases", excel_data + "_data_sg.xlsx")
    excel_vsc = os.path.join(path_data, "cases", excel_data + "_data_vsc.xlsx")
    excel_op = os.path.join(path_data, "cases", excel_op + ".xlsx")
    if grid_name == 'IEEE118':
        excel_lines_ratings = os.path.join(
            path_data, "cases", excel_lines_ratings + ".csv")

    # %% READ OPERATION EXCEL FILE
    d_op = read_data.read_data(excel_op)

    # %% READ RAW FILE
    d_raw_data = process_raw.read_raw(raw_file)

    if grid_name == 'IEEE9':
        # For the IEEE 9-bus system
        d_raw_data['generator']['Region'] = 1
        d_raw_data['load']['Region'] = 1
        d_raw_data['branch']['Region'] = 1
        d_raw_data['results_bus']['Region'] = 1
    elif grid_name == 'IEEE118':
        # FOR the 118-bus system
        d_raw_data['generator']['Region'] = d_op['Generators']['Region']
        d_raw_data['load']['Region'] = d_op['Loads']['Region']
        # d_raw_data['branch']['Region']=1
        d_raw_data['results_bus']['Region'] = d_op['Buses']['Region']
        d_raw_data['generator']['MBASE'] = d_op['Generators']['Snom']
        lines_ratings = pd.read_csv(excel_lines_ratings)

    # Preprocess input raw data to match Excel file format
    preprocess_data.preprocess_raw(d_raw_data)

    # %% Create GridCal Model
    gridCal_grid = GridCal_powerflow.create_model(raw_file)

    if grid_name == 'IEEE118':
        for line in gridCal_grid.lines:
            bf = int(line.bus_from.code)
            bt = int(line.bus_to.code)
            line.rate = lines_ratings.loc[
                lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
                    0], 'Max Flow (MW)']
    
        for trafo in gridCal_grid.transformers2w:
            bf = int(trafo.bus_from.code)
            bt = int(trafo.bus_to.code)
            trafo.rate = lines_ratings.loc[
                lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
                    0], 'Max Flow (MW)']

    # %% READ EXCEL FILE
    # Read data of grid elements from Excel file
    d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)
    # TO BE DELETED
    d_grid = read_data.tempTables(d_grid)

    # %% READ EXEC FILES WITH SG AND VSC CONTROLLERS PARAMETERS
    d_sg = read_data.read_data(excel_sg)
    d_vsc = read_data.read_data(excel_vsc)

    # %% CONFIGURATION OF DIMENSIONS FOR THE DATA GENERATOR
    # Set up dimensions for generators, converters and loads
    p_sg = []
    p_cig = []
    for i in range(len(d_op['Generators'])):
        p_sg.append((d_op['Generators']['Pmin_SG'].iloc[i],
                     d_op['Generators']['Pmax_SG'].iloc[i]))
        p_cig.append((d_op['Generators']['Pmin_CIG'].iloc[i],
                      d_op['Generators']['Pmax_CIG'].iloc[i]))

    p_loads = list(d_op['Loads']['Load_Participation_Factor'])

    dimensions = [
        Dimension(label="p_sg", variable_borders=p_sg,
                  n_cases=n_cases, divs=2,
                  borders=(d_op['Generators']['Pmin_SG'].sum(),
                           d_op['Generators']['Pmax_SG'].sum()),
                  independent_dimension=True, cosphi=generators_power_factor),
        Dimension(label="p_cig", variable_borders=p_cig,
                  n_cases=n_cases, divs=1,
                  borders=(d_op['Generators']['Pmin_CIG'].sum(),
                           d_op['Generators']['Pmax_CIG'].sum()),
                  independent_dimension=True,
                  cosphi=generators_power_factor),
        Dimension(label="perc_g_for", variable_borders=[(0, 1)],
                  n_cases=n_cases, divs=1, borders=(0, 1),
                  independent_dimension=True, cosphi=None),
        Dimension(label="p_load", values=p_loads,
                  n_cases=n_cases, divs=1,
                  independent_dimension=False,
                  cosphi=loads_power_factor)
    ]

    # Set up independent dimensions (controllers)
    for d in list(d_op['Generators']['BusNum']):
        dimensions.append(
            Dimension(label='tau_droop_f_gfor_' + str(d), n_cases=n_cases,
                      divs=1, borders=(0.01, 0.2),
                      independent_dimension=True,
                      cosphi=None))
        dimensions.append(
            Dimension(label='tau_droop_u_gfor_' + str(d), n_cases=n_cases,
                      divs=1, borders=(0.01, 0.2),
                      independent_dimension=True,
                      cosphi=None))
        dimensions.append(
            Dimension(label='tau_droop_f_gfol_' + str(d), n_cases=n_cases,
                      divs=1, borders=(0.01, 0.2),
                      independent_dimension=True,
                      cosphi=None))
        dimensions.append(
            Dimension(label='tau_droop_u_gfol_' + str(d), n_cases=n_cases,
                      divs=1, borders=(0.01, 0.2),
                      independent_dimension=True,
                      cosphi=None))

    # %% RUN OBJECTIVE FUNCTION
    func_params = {"n_pf": n_pf, "d_raw_data": d_raw_data, "d_op": d_op,
                   "gridCal_grid": gridCal_grid, "d_grid": d_grid,
                   "d_sg": d_sg,
                   "d_vsc": d_vsc, "voltage_profile": voltage_profile,
                   "v_min_v_max_delta_v": v_min_v_max_delta_v}

    stability_array = []
    output_dataframes_array = []
    cases_df, dims_df, execution_logs, output_dataframes = start(
        dimensions=dimensions, n_samples=n_samples,
        rel_tolerance=rel_tolerance, func=feasible_power_flow_ACOPF,
        max_depth=max_depth, seed=seed, func_params=func_params,
        dst_dir=path_results
    )

    stability_array = compss_wait_on(stability_array)
    output_dataframes_array = compss_wait_on(output_dataframes_array)


if __name__ == "__main__":
    main(setup_path="./setup/default_setup.yaml")
