# import numpy as np
# import matplotlib.pyplot as plt
# import control as ct
# import pandas as pd
from os import path, getcwd
from stability_analysis.preprocess import preprocess_data, read_data, process_raw, parameters
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus
from stability_analysis.state_space import generate_NET, build_ss, generate_elements
from stability_analysis.opal import process_opal
from stability_analysis.analysis import small_signal

# %% SET FILE NAMES AND PATHS

# Paths to data

# path_data = path.abspath(getcwd()) + "\\tool\\data" 
# path_raw = path.abspath(getcwd()) + "\\tool\\data\\raw"
# path_results = path.abspath(getcwd()) + "\\tool\\data\\results"

path_data = 'C:/Users/Francesca/Documents/SS_pyTOOL' + "\\tool\\data" 
path_raw = 'C:/Users/Francesca/Documents/SS_pyTOOL' + "\\tool\\data\\raw"
path_results = 'C:/Users/Francesca/Documents/SS_pyTOOL' + "\\tool\\data\\results"

# File names

# # IEEE 118 
# raw = "ieee9_6"
# excel = "IEEE_9" 

#IEEE 118 
raw = "IEEE118busREE_Winter Solved_mod_PQ"
# excel = "IEEE_118bus_TH" # THÉVENIN
# excel = "IEEE_118_01" # SG
excel = "IEEE_118_FULL" 

# TEXAS 2000 bus
# raw = "ACTIVSg2000_solved_noShunts"
# excel = "texas_2000"


raw_file = path.join(path_raw, raw + ".raw")
excel_raw = path.join(path_raw, raw + ".xlsx")
excel_sys = path.join(path_data, "cases/" + excel + ".xlsx")  
excel_sg = path.join(path_data, "cases/" + excel + "_data_sg.xlsx") 
excel_vsc = path.join(path_data, "cases/" + excel + "_data_vsc.xlsx") 

# %% READ RAW FILE

# Read raw file
d_raw_data = process_raw.read_raw(raw_file)

# Preprocess input raw data to match excel file format
preprocess_data.preprocess_raw(d_raw_data)

# Write to excel file
preprocess_data.raw2excel(d_raw_data,excel_raw)

# Create GridCal Model
GridCal_grid = GridCal_powerflow.create_model(path_raw, raw_file)
              
# %% READ EXCEL FILE

# Read data of grid elements from Excel file
d_grid = read_data.read_data(excel_sys)

# # TO BE DELETED
# d_grid = read_data.tempTables(d_grid) 

# # Read simulation configuration parameters from Excel file
# sim_config = read_data.get_simParam(excel_sys)

# %% POWER-FLOW

# Receive system status from OPAL
#d_grid, GridCal_grid, data_old = process_opal.update_OP_from_RT(d_grid, GridCal_grid, data_old)
    
# Get Power-Flow results with GridCal
pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)

# Update PF results and operation point of generator elements
d_grid, d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)

# %% READ PARAMETERS

# Get parameters of generator units from excel files & compute pu base
d_grid = parameters.get_params(d_grid, excel_sg, excel_vsc)

# Compute reference angle (delta_slk)
d_grid, REF_w, num_slk, delta_slk = slack_bus.delta_slk(d_grid)

# %% GENERATE STATE-SPACE MODEL

# Generate AC & DC NET State-Space Model
l_blocks, l_states, d_grid = generate_NET.generate_SS_NET_blocks(d_grid, delta_slk)

# Generate generator units State-Space Model
l_blocks, l_states = generate_elements.generate_SS_elements(d_grid, delta_slk, l_blocks, l_states)


# %% BUILD FULL SYSTEM STATE-SPACE MODEL

# Define full system inputs and ouputs
var_in = ['NET_Rld1']
var_out = ['GFOR1_w'] #['all']

# Build full system state-space model
inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs)

# %% SMALL-SIGNAL ANALYSIS

T_EIG = small_signal.FEIG(ss_sys, True)
T_EIG.head

# write to excel
T_EIG.to_excel(path.join(path_results, "EIG_" + excel + ".xlsx"))