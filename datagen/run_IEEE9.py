import numpy as np
from matplotlib import pyplot as plt

from datagen.src.dimensions import Dimension
from datagen.src.start_app import start
from datagen.src.objective_function import *

# from datagen.src.objective_function import small_signal_stability

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
except ImportError:
    from datagen.dummies.task import task
    from datagen.dummies.api import compss_wait_on

from os import path, getcwd
from stability_analysis.data import get_data_path
from stability_analysis.preprocess import preprocess_data, read_data, \
    process_raw, parameters, admittance_matrix
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, \
    slack_bus, fill_d_grid_after_powerflow
from stability_analysis.state_space import generate_NET, build_ss, \
    generate_elements
from stability_analysis.opal import process_opal
from stability_analysis.analysis import small_signal
from stability_analysis.preprocess.utils import *
from stability_analysis.random_operating_point import random_OP
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, \
    assign_PQ_Loads_to_grid

# %% SET FILE NAMES AND PATHS

# Paths to data
path_data = get_data_path()
path_raw = path.join(path_data, "raw")
path_results = path.join(path_data, "results")

# File names

# IEEE 9
raw = "ieee9_6"
excel = "IEEE_9_headers"
excel_data = "IEEE_9"
excel_op = "OperationData_IEEE_9"

# IEEE 118
# raw = "IEEE118busREE_Winter Solved_mod_PQ"
# # excel = "IEEE_118bus_TH" # THÉVENIN
# # excel = "IEEE_118_01" # SG
# excel = "IEEE_118_FULL"
# excel_data = "IEEE_118_FULL"
# excel_op = "OperationData_IEEE_118"

# TEXAS 2000 bus
# raw = "ACTIVSg2000_solved_noShunts"
# excel = "texas_2000"


raw_file = path.join(path_raw, raw + ".raw")
# excel_raw = path.join(path_raw, raw + ".xlsx")
excel_sys = path.join(path_data, "cases/" + excel + ".xlsx")  # empty
excel_sg = path.join(path_data, "cases/" + excel_data + "_data_sg.xlsx")
excel_vsc = path.join(path_data, "cases/" + excel_data + "_data_vsc.xlsx")
excel_op = path.join(path_data, "cases/" + excel_op + ".xlsx")
# %% READ RAW FILE

# Read raw file
d_raw_data = process_raw.read_raw(raw_file)

d_raw_data['generator']['Region'] = 1
d_raw_data['load']['Region'] = 1
d_raw_data['branch']['Region'] = 1
d_raw_data['results_bus']['Region'] = 1

# Preprocess input raw data to match excel file format
preprocess_data.preprocess_raw(d_raw_data)

# Write to excel file
# preprocess_data.raw2excel(d_raw_data,excel_raw)

# Create GridCal Model
GridCal_grid = GridCal_powerflow.create_model(path_raw, raw_file)

# %% READ OPERATION EXCEL FILE

d_op = read_data.read_data(excel_op)

# %% READ EXCEL FILE

# Read data of grid elements from Excel file
d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)

# TO BE DELETED
d_grid = read_data.tempTables(d_grid)

# # Read simulation configuration parameters from Excel file
# sim_config = read_data.get_simParam(excel_sys)

# %% READ EXEC FILES WITH SG AND VSC CONTROLLERS PARAMETERS

d_sg = read_data.read_data(excel_sg)

d_vsc = read_data.read_data(excel_vsc)

# %%
# @task()
# def main():
"""
In this method we work with dimensions (main axes), which represent a
list of variable_borders. For example, the value of each variable of a concrete
dimension could represent the power supplied by a generator, while the
value linked to that dimension should be the total sum of energy produced.

For each dimension it must be declared:
    -variable_borders: list of variable_borders represented by tuples containing its
            lower and upper borders.
    -n_cases: number of cases taken for each sample (each sample represents
            the total sum of a dimension). A case is a combination of
            variable_borders where all summed together equals the sample.
    -divs: number of divisions in that dimension. It will be the growth
            order of the number of cells
    -lower: lower bound of the dimension (minimum value of a sample)
    -upper: upper bound of the dimension (maximum value of a sample)
    -label: dimension identifier
    -independent_dimension: indicates whether the dimension is true (sampleable) or not.

Apart from that, it can also be specified the number of samples and
the relative tolerance (indicates the portion of the size of the original
dimension). For example, if we have a dimension of size 10 and relative
tolerance is 0.5, the smallest cell in this dimension will have size 5.
Lastly, user should provide the objective function. As optional parameters,
the user can define:
    -use_sensitivity: a boolean indicating whether sensitivity analysis is
    used or not.
    -ax: plot axes in case it is desired to show stability points and cells
    divisions (dimensions length must be 2). Plots saved in
    "datagen/results/figures".
    -plot_boxplot: a boolean indicating whether boxplots for each variable
    must be obtained or not. Plots saved in "datagen/results/figures".
"""

# p_sg = [(0, 2), (0, 1.5), (0, 1.5)]
# p_cig = [(0, 1), (0, 1.5), (0, 1.5), (0, 2)]
# tau_f_g_for = [(0., 2)]
# tau_v_g_for = [(0., 2)]
# tau_p_g_for = [(0., 2)]
# tau_q_g_for = [(0., 2)]

p_sg = [
    (d_op['Generators']['Pmin_SG'].iloc[i], d_op['Generators']['Pmax_SG'].iloc[i])
    for i in range(len(d_op['Generators']))]
p_cig = [(d_op['Generators']['Pmin_CIG'].iloc[i],
          d_op['Generators']['Pmax_CIG'].iloc[i]) for i in
         range(len(d_op['Generators']))]
p_loads = list(d_op['Loads']['Load_Participation_Factor'])

loads_power_factor = 0.95
generators_power_factor = 0.95

tau_f_g_for = [(0., 2)]
tau_v_g_for = [(0., 2)]
tau_p_g_for = [(0., 2)]
tau_q_g_for = [(0., 2)]

n_samples = 3
n_cases = 3

rel_tolerance = 0.01
max_depth = 3
dimensions = dict()
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
      Dimension(label="perc_g_for", variable_borders=[(0,1)],
                n_cases=n_cases, divs=1, borders=(0, 1),
                independent_dimension=True, cosphi=None),
      Dimension(label="p_load", values=p_loads,
                n_cases=n_cases, divs=1,
                independent_dimension=False,
                cosphi=loads_power_factor)
              ]

for d in list(d_op['Generators']['BusNum']):
    dimensions.append(Dimension(label='tau_droop_f_gfor_'+str(d), n_cases=n_cases,
                                divs=1, borders=(0.1,0.5),
                                independent_dimension=True,
                                cosphi=None))
    
    dimensions.append(Dimension(label='tau_droop_u_gfor_'+str(d), n_cases=n_cases,
                                divs=1, borders=(0.1,0.5),
                                independent_dimension=True,
                                cosphi=None))
    
    dimensions.append(Dimension(label='tau_droop_f_gfol_'+str(d), n_cases=n_cases,
                                divs=1, borders=(0.1,0.5),
                                independent_dimension=True,
                                cosphi=None))
    
    dimensions.append(Dimension(label='tau_droop_u_gfol_'+str(d), n_cases=n_cases,
                                divs=1, borders=(0.1,0.5),
                                independent_dimension=True,
                                cosphi=None))
    

#     Dimension(variable_borders=tau_f_g_for, n_cases=n_cases, divs=1,
#               borders=(0, 2), independent_dimension="tau_f_g_for"),
#     Dimension(variable_borders=tau_v_g_for, n_cases=n_cases, divs=1,
#               borders=(0, 2), independent_dimension="tau_v_g_for"),
#     Dimension(variable_borders=tau_p_g_for, n_cases=n_cases, divs=1,
#               borders=(0, 2), independent_dimension="tau_p_g_for"),
#     Dimension(variable_borders=tau_q_g_for, n_cases=n_cases, divs=1,
#               borders=(0, 2), independent_dimension="tau_q_g_for")
# ]

fig, ax = plt.subplots()
use_sensitivity = True
# %%

cases_df, dims_df, execution_logs, output_dataframes = \
    start(dimensions=dimensions, n_samples=n_samples,
          rel_tolerance=rel_tolerance, func=small_signal_stability,
          max_depth=max_depth, use_sensitivity=use_sensitivity, ax=ax, 
          divs_per_cell=2, seed=5, d_raw_data=d_raw_data, d_op=d_op, 
          GridCal_grid=GridCal_grid, d_grid=d_grid, d_sg=d_sg, d_vsc=d_vsc
          )

# if __name__ == "__main__":
#     main()