"""
Standalone execution of the stability analysis function
(objective_function_ACOPF.py)

Usage: python3 ACOPF_standalone.py [--working_dir=<dir>] [--path_data=<path>]
[--setup=<yaml>]
Options:
  --working_dir=<dir>: Path where results will be stored (default: "")
  --path_data=<path>: Path to input_data (where the grid setup is stored)
        (default: stability_analysis/stability_analysis/data)
  --setup=<yaml>: Yaml or path to a yaml file (refer to the setup directory for
  examples)
        User can specify:
            -n_pf
            -voltage_profile
            -v_min_v_max_delta_v
            -loads_power_factor
            -generators_power_factor
            -n_samples: Number of samples to produce for each cell
            -n_cases: Number of different combinations of cases for each sample
            -rel_tolerance: Indicates the minimum size of a cell as pu (related
            to the initial size of the cell)
            -max_depth: Maximum number of subdivisions
            -seed: Seed
            -grid_name: Grid name
        (default: "setup/default_setup.yaml")
"""

import os
import sys
import random
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from datagen.src.utils import save_dataframes, parse_setup_file, parse_args, concat_df_dict, save_results
from datagen.src.dimensions import Dimension
from datagen.src.objective_function_ACOPF import *
from datagen.src.sampling import gen_samples
from datagen.src.sampling import gen_cases
from datagen.src.sampling import eval_stability

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


def main(working_dir='', path_data='', setup_path=''):
    # %% Parse arguments
    working_dir, path_data, setup_path = parse_args(
       [None, working_dir, path_data, setup_path])
    (generators_power_factor, grid_name, loads_power_factor, n_cases, n_pf,
     n_samples, seed, v_min_v_max_delta_v, voltage_profile, v_set,
     _, _, _) = \
        parse_setup_file(setup_path)
        
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
    print("COMPUTING_UNITS: ", os.environ.get("COMPUTING_UNITS"))
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
    cu = os.environ.get("COMPUTING_UNITS")

    # CASE CONFIGURATION
    # Create unique directory name for results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd_num = random.randint(1000, 9999)
    dir_name = f"ACOPF_standalone_NREL_LF09_seed{seed}_nc{n_cases}_ns{n_samples}" \
               f"_{timestamp}_{rnd_num}"
    path_results = os.path.join(
        working_dir, "results", dir_name)
    # if not os.path.isdir(path_results):
    #     os.makedirs(path_results)


    # %% SET FILE NAMES AND PATHS
    if grid_name == 'IEEE9':
        # IEEE 9
        raw = "ieee9_hypersim"
        excel_headers = "Empty_template_V6"#"IEEE_9_headers"
        excel_data = "IEEE_9"
        excel_op = "OperationData_IEEE_9_hypersim"
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
            line.rate = float(lines_ratings.loc[
                lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
                    0], 'Max Flow (MW)'])
    
        for trafo in gridCal_grid.transformers2w:
            bf = int(trafo.bus_from.code)
            bt = int(trafo.bus_to.code)
            trafo.rate = lines_ratings.loc[
                lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
                    0], 'Max Flow (MW)']
    if grid_name == 'IEEE9':
        gridCal_grid.fBase=60
        for idx_gen,gen in enumerate(gridCal_grid.get_generators()):
            gen.Pf=0.95 

            gen.Pmax=d_op['Generators'].loc[idx_gen,'Pmax']
            gen.Pmin=d_op['Generators'].loc[idx_gen,'Pmin']
            gen.Qmax=d_op['Generators'].loc[idx_gen,'Qmax']
            gen.Qmin=d_op['Generators'].loc[idx_gen,'Qmin']
            
            gridCal_grid.transformers2w[idx_gen].rate=gen.Snom
            
    # %% READ EXCEL FILE
    # Read data of grid elements from Excel file
    d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)
    # TO BE DELETED
    d_grid = read_data.tempTables(d_grid)

    # %% READ EXEC FILES WITH SG AND VSC CONTROLLERS PARAMETERS
    d_sg = read_data.read_data(excel_sg)
    d_vsc = read_data.read_data(excel_vsc)
    # d_vsc['UserGFOL'].loc[0,'ts_pll']=0.1

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

    # %% SAMPLING FOR THE DATA GENERATION
    # Generate samples
    generator = np.random.default_rng(seed)
    samples_df = gen_samples(n_samples, dimensions, generator)
    # Generate cases (n_cases (attribute of the class Dimension) for each dim)
    cases_df, dims_df = gen_cases(samples_df, dimensions, generator)

    # %% RUN OBJECTIVE FUNCTION
    func_params = {"n_pf": n_pf, "d_raw_data": d_raw_data, "d_op": d_op,
                   "gridCal_grid": gridCal_grid, "d_grid": d_grid,
                   "d_sg": d_sg,
                   "d_vsc": d_vsc, "voltage_profile": voltage_profile, 'v_set': v_set,
                   "v_min_v_max_delta_v": v_min_v_max_delta_v}

    stability_array = []
    output_dataframes_array = []
    for _, case in cases_df.iterrows():
        if _ in [13]:#[106, 268, 270, 271]:
            print('stop')
            stability, output_dataframes = eval_stability(
                case=case,
                f=feasible_power_flow_ACOPF,
                func_params=func_params,
                generator=generator)
            stability_array.append(stability)
            output_dataframes_array.append(output_dataframes)
            n_pf = n_pf + 1

    # %% SAVE RESULTS
    stability_array = compss_wait_on(stability_array)
    output_dataframes_array = compss_wait_on(output_dataframes_array)
    
    # Collect each cases dictionary of dataframes into total_dataframes
    total_dataframes=None
    for output_dfs in output_dataframes_array:
        if total_dataframes:
            total_dataframes = concat_df_dict(total_dataframes,
                                              output_dfs)
        else:
            total_dataframes = output_dfs
    # Remove elements of the dict of dataframes that are not a dataframe
    labels_to_remove = []
    if total_dataframes:
        for label, df in total_dataframes.items():
            if df is not None and type(df) is not pd.DataFrame:
                # Keep None values that work as a placeholder
                labels_to_remove.append(label)
        for label in labels_to_remove:
            total_dataframes.pop(label)
    
    total_dataframes['df_op']['Stable']=stability_array
    save_results(cases_df, dims_df, None, total_dataframes, path_results)

            
if __name__ == "__main__":
#    main(setup_path="./setup/test_default_vset.yaml")
    main(setup_path="./setup/test_setup.yaml")
