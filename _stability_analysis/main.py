# import numpy as np
# import matplotlib.pyplot as plt
# import control as ct
# import pandas as pd

from os import path, getcwd

from stability_analysis.data import get_data_path
from stability_analysis.preprocess import preprocess_data, read_data, process_raw, parameters,read_op_data_excel, admittance_matrix
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus, fill_d_grid_after_powerflow
from stability_analysis.state_space import generate_NET, build_ss, generate_elements
from stability_analysis.opal import process_opal
from stability_analysis.analysis import small_signal
from stability_analysis.preprocess.utils import *
from stability_analysis.random_operating_point import random_OP
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid,assign_PQ_Loads_to_grid
from GridCalEngine.Core.DataStructures import numerical_circuit

#%%
import numpy as np
# from GridCalEngine.Core.Devices.Injections.generator import Generator
import GridCalEngine.api as gce

def compute_bus_admittance(num_buses, branches, loads, load_Q=True):
    # Initialize an empty bus admittance matrix
    Y_bus = np.zeros((num_buses, num_buses), dtype=complex)

    # Compute the admittance for each branch and update the Y_bus matrix
    for branch in branches:
        bus_from = int(branch.bus_from.code) - 1  # Assuming buses are 1-indexed
        bus_to = int(branch.bus_to.code) - 1    # Assuming buses are 1-indexed
        # print(bus_from)
        # print(bus_to)
        admittance = 1 / complex(branch.R, branch.X)  # Compute branch admittance
        # print(admittance)
        
        # Add admittance to the diagonal elements
        Y_bus[bus_from][bus_from] += admittance
        Y_bus[bus_to][bus_to] += admittance

        # Subtract admittance from off-diagonal elements
        Y_bus[bus_from][bus_to] -= admittance
        Y_bus[bus_to][bus_from] -= admittance
        # print(Y_bus)
        
    for load in loads:
        bus= int(load.bus.code) - 1  # Assuming buses are 1-indexed
        # print(bus_from)
        # print(bus_to)
        R= 1/load.P*100
        if load_Q==True:
            X=1/load.Q*100
        else:
            X=0
        admittance = 1 / complex(R, X)  # Compute branch admittance

        # Add admittance to the diagonal elements
        Y_bus[bus][bus] += admittance

    return Y_bus



def take_only_pf_data(df,n_pf):
    df_pf=df.query('PF == @n_pf')
    return df_pf
 
def check_min_max_violation(df,data,bus,min_val,max_val,n_pf):
    
    i=0
    df_row=pd.DataFrame()
    if any(data<min_val) or any(data>max_val):
        violations=list(np.where(data<min_val)[0])+list(np.where(data>max_val)[0])
        df_row.loc[0:len(violations),'GenBus']=list(np.array(bus)[violations])
        
        df_row.loc[i:i+len(violations),'Val']=list(np.array(data)[violations])
        df_row.loc[i:i+len(violations),'PF']=n_pf
        
    df=pd.concat([df,df_row],axis=0)
            
    return df

def check_min_violation_Qgen(df,bus,data,min_val,n_pf):
    
    i=0#len(df)
    df_row=pd.DataFrame()
    if any(data<min_val):
        violations=np.where(data<min_val)[0]
        df_row.loc[i:i+len(violations),'GenBus']=list(np.array(bus)[violations])
        df_row.loc[i:i+len(violations),'Min']=np.array(data)[violations]
        df_row.loc[i:i+len(violations),'Min_ref']=np.array(min_val)[violations]
        df_row.loc[i:i+len(violations),'PF']=n_pf
        
    df=pd.concat([df,df_row],axis=0)
            
    return df

def check_max_violation_Qgen(df,bus,data,max_val,n_pf):
    
    i=0#len(df)
    df_row=pd.DataFrame()
    if any(data>max_val):
        violations=np.where(data>max_val)[0]
        
        df_row.loc[i:i+len(violations),'GenBus']=list(np.array(bus)[violations])
        df_row.loc[i:i+len(violations),'Max']=np.array(data)[violations]
        df_row.loc[i:i+len(violations),'Max_ref']=np.array(max_val)[violations]
        df_row.loc[i:i+len(violations),'PF']=n_pf

    df=pd.concat([df,df_row],axis=0)
            
    return df

def check_violations(Bus_pf, Gen_pf, n_pf,
                     Bus_voltage_violation=pd.DataFrame(),
                     Gen_Q_Min_limit_violation=pd.DataFrame(),
                     Gen_Q_Max_limit_violation=pd.DataFrame(),
                     Gen_pf_violation=pd.DataFrame(),
                     Gen_V_violation=pd.DataFrame()
                     ):
    
    Bus_voltage_violation=check_min_max_violation(Bus_voltage_violation, Bus_pf['Vm'], Bus_pf['bus'], 0.9, 1.1, n_pf)
    Gen_Q_Min_limit_violation=check_min_violation_Qgen(Gen_Q_Min_limit_violation, Gen_pf['bus'], Gen_pf['Q'],Gen_pf['Qmin'], n_pf)
    Gen_Q_Max_limit_violation=check_max_violation_Qgen(Gen_Q_Max_limit_violation, Gen_pf['bus'], Gen_pf['Q'], Gen_pf['Qmax'], n_pf)
    
    Gen_pf['pf']=np.cos(np.arctan(Gen_pf['Q']/Gen_pf['P']))
    Gen_pf_violation=check_min_max_violation(Gen_pf_violation,Gen_pf['pf'],Gen_pf['bus'], 0.8, 1, n_pf)

    Gen_V_violation=check_min_max_violation(Gen_V_violation,Gen_pf['Vm'], Gen_pf['bus'],  0.95, 1.05, n_pf)

    return Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation

def add_shunt(n_bus, d_pf, GridCalgrid):
        i_bus=d_pf['pf_bus'].query('bus==@n_bus').index[0]
        bus=GridCal_grid.get_buses()[i_bus]
        Pg=d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus==@n_bus').index[0],'P']*100
        sign_Qg=np.sign(d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus==@n_bus').index[0],'Q'])
        cos_phi=d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus==@n_bus').index[0],'cosphi']
        B=sign_Qg*Pg*(np.tan(np.arccos(cos_phi)-np.arccos(0.95)))
        if GridCal_grid.get_buses()[i_bus].shunts==[]:
            GridCal_grid.add_shunt(bus,
                               shunt.Shunt(name='Shunt_'+str(n_bus),B=B))
        else:
            GridCal_grid.get_buses()[i_bus].shunts[0].B=B

# %% SET FILE NAMES AND PATHS

# Paths to data

path_data = get_data_path()
path_raw = path.join(path_data, "raw")
path_results = path.join(path_data, "results")

# File names

gridname='IEEE118'#'IEEE9'#

if gridname == 'IEEE9':
# # # IEEE 9
    raw = "ieee9_6"
    excel = "IEEE_9_headers" 
    excel_data = "IEEE_9" 
    excel_op = "OperationData_IEEE_9" 

elif gridname=='IEEE118':
    # IEEE 118 
    raw = "IEEE118busREE_Winter Solved_mod_PQ_91Loads"
    # excel = "IEEE_118bus_TH" # THÉVENIN
    # excel = "IEEE_118_01" # SG
    excel = "IEEE_118_FULL_headers" 
    excel_data = "IEEE_118_FULL" 
    excel_op = "OperationData_IEEE_118" 

# TEXAS 2000 bus
# raw = "ACTIVSg2000_solved_noShunts"
# excel = "texas_2000"


raw_file = path.join(path_raw, raw + ".raw")
# excel_raw = path.join(path_raw, raw + ".xlsx")
excel_sys = path.join(path_data, "cases/" + excel + ".xlsx") #empty 
excel_sg = path.join(path_data, "cases/" + excel_data + "_data_sg.xlsx") 
excel_vsc = path.join(path_data, "cases/" + excel_data + "_data_vsc.xlsx") 
excel_op = path.join(path_data, "cases/" + excel_op + ".xlsx") 

#%% READ OPERATION EXCEL FILE

d_op = read_op_data_excel.read_operation_data_excel(excel_op)

# %% READ RAW FILE

# Read raw file
d_raw_data = process_raw.read_raw(raw_file)

if gridname == 'IEEE9':
    # For the IEEE 9-bus system
    d_raw_data['generator']['Region']=1
    d_raw_data['load']['Region']=1
    d_raw_data['branch']['Region']=1
    d_raw_data['results_bus']['Region']=1

elif gridname == 'IEEE118':
    # FOR the 118-bus system
    d_raw_data['generator']['Region']=d_op['Generators']['Region']
    d_raw_data['load']['Region']=d_op['Loads']['Region']
    # d_raw_data['branch']['Region']=1
    d_raw_data['results_bus']['Region']=d_op['Buses']['Region']
    d_raw_data['generator']['MBASE']=d_op['Generators']['Snom']


# Preprocess input raw data to match excel file format
preprocess_data.preprocess_raw(d_raw_data)

# Write to excel file
# preprocess_data.raw2excel(d_raw_data,excel_raw)

# Create GridCal Model
GridCal_grid = GridCal_powerflow.create_model(path_raw, raw_file)
   


#%% GENERATE RANDOM OPERATING POINT

d_raw_data, d_op= random_OP.random_operating_point(d_op, d_raw_data, GridCal_grid,
                                             n_reg=3, loads_power_factor=0.98,
                                             generators_power_factor=0.98,
                                             all_gfor=False,fix_seed=True)
              
#%% MODIFY GRIDCAL_GRID

#assign_Generators_to_grid.assign_StaticGen(GridCal_grid, d_raw_data, d_op)
assign_Generators_to_grid.assign_PVGen(GridCal_grid, d_raw_data, d_op)
# assign_Generators_to_grid.assign_V_to_PVGen(GridCal_grid,d_raw_data)
assign_PQ_Loads_to_grid.assign_PQ_load(GridCal_grid, d_raw_data)


# %% READ EXCEL FILE

# Read data of grid elements from Excel file
d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)

# TO BE DELETED
d_grid = read_data.tempTables(d_grid) 

# # Read simulation configuration parameters from Excel file
# sim_config = read_data.get_simParam(excel_sys)

#%% READ EXCEL FILES WITH SG AND VSC CONTROLLERS PARAMETERS

d_sg = read_data.read_data(excel_sg)

d_vsc = read_data.read_data(excel_vsc)


# %% POWER-FLOW

# Receive system status from OPAL
#d_grid, GridCal_grid, data_old = process_opal.update_OP_from_RT(d_grid, GridCal_grid, data_old)
    
# Get Power-Flow results with GridCal
pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)

print('Converged:',pf_results.convergence_reports[0].converged_[0])

# Update PF results and operation point of generator elements
d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)


#%% 

Y_bus=compute_bus_admittance(118, GridCal_grid.get_branches(),GridCal_grid.get_loads(),False)

G_bus=pd.DataFrame(np.diag(np.real(Y_bus)),columns=['G'])#.sort_values(by='G',ascending=False) #index starts at 0
B_bus=pd.DataFrame(abs(np.diag(np.imag(Y_bus))),columns=['B'])#.sort_values(by='B',ascending=False)

G_gen_bus=G_bus.loc[np.array(d_raw_data['generator']['I'])-1].sort_values(by='G',ascending=False) # bus= index+1
B_gen_bus=B_bus.loc[np.array(d_raw_data['generator']['I'])-1].sort_values(by='B',ascending=False)

# abs_gen_bus=pd.DataFrame(abs(np.diag(Y_bus),columns=['Y'])).sort_values(by='Y',ascending=False)

#%%
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
import GridCalEngine as gc
from GridCalEngine.Core.Devices.Injections import shunt

solver_type=SolverType.IWAMOTO
    
options = PowerFlowOptions(solver_type,
                           verbose=False,
                           initialize_with_existing_solution=False,
                           multi_core=False,
                           dispatch_storage=True,
                           control_q=ReactivePowerControlMode.Direct,
                           control_p=True,
                           retry_with_other_methods=False)

#%%
d_raw_data= change_Q_per_region(d_raw_data, 0.97,1)

#%%

d_raw_data['generator']['Static']=1
d_raw_data['generator'].loc[d_raw_data['generator'].query('I == 65').index,'Static']=-1 # slack

for bus in list(B_gen_bus.index +1):
    if bus != 65:
        d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus').index,'Static']=0
        
        # GridCal_grid = GridCal_powerflow.create_model(path_raw, raw_file)

        assign_Generators_to_grid.assign_PV_or_StaticGen(GridCal_grid,d_raw_data,d_op)
        
        # assign_PQ_Loads_to_grid.assign_PQ_load(GridCal_grid, d_raw_data)
        
        # Get Power-Flow results with GridCal
        pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)

        print('Converged:',pf_results.convergence_reports[0].converged_[0])
        
        if pf_results.convergence_reports[0].converged_[0] == True:
            # Update PF results and operation point of generator elements
            d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
            
            # Sbuses=pd.DataFrame(pf_results.results.Sbus)
            # Sbuses.columns=['S']
            # Sbuses['P']=np.real(Sbuses['S'])
            # Sbuses['Q']=np.imag(Sbuses['S'])
            # Sbuses['cosphi']=np.cos(np.arctan(Sbuses['Q']/Sbuses['P']))
            
            # Sbuses['BusNum']=bus_list
            # # Sbuses['Region']=list(T_Buses.query('Num == @bus_list')['Region'])
            # Sbuses['V']=abs(pf_results.results.voltage)

            break

#%%
Gen_res=d_pf['pf_gen'].copy(deep=True).sort_values(by='bus').reset_index(drop=True)
Gen_res['Qmin']=d_op['Generators']['Qmin']/100
Gen_res['Qmax']=d_op['Generators']['Qmax']/100
Gen_res['Pmin']=d_op['Generators']['Pmin']/100
Gen_res['Pmax']=d_op['Generators']['Pmax']/100

Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation = check_violations(d_pf['pf_bus'], Gen_res, 0)
#                      Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation)
        

#%% FILL d_grid

d_grid, d_pf = fill_d_grid_after_powerflow.fill_d_grid(d_grid, GridCal_grid, d_pf, d_raw_data, d_op)

# d_grid['T_user']=d_grid['T_user'][0:]

# %% READ PARAMETERS

# Get parameters of generator units from excel files & compute pu base
d_grid = parameters.get_params(d_grid, d_sg, d_vsc)

# Assign slack bus and slack element
d_grid = slack_bus.assign_slack(d_grid)

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
var_out = ['GFOR3_w'] #['all']

# Build full system state-space model
inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs)

# %% SMALL-SIGNAL ANALYSIS

# Eigenvalues

T_EIG = small_signal.FEIG(ss_sys, plot=True)
T_EIG.head
#T_EIG.to_excel(path.join(path_results, "EIG_" + excel + ".xlsx")) # Write T_EIG to excel

# Participation factors

# Obtain all participation factors
df_PF = small_signal.FMODAL(ss_sys, plot=False)
# Obtain the participation factors for the selected modes
T_modal, df_PF = small_signal.FMODAL_REDUCED(ss_sys, plot=True, modeID = [1,3,11])
# Obtain the participation factors >= tol, for the selected modes
T_modal, df_PF = small_signal.FMODAL_REDUCED_tol(ss_sys, plot=True, modeID = [1,3,11], tol = 0.3)
