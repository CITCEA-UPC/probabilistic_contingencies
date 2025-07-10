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
# from stability_analysis.random_operating_point import random_OP
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid, \
    assign_PQ_Loads_to_grid
from GridCalEngine.Core.DataStructures import numerical_circuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at

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
    raw = "IEEE118busREE_Winter_Solved_mod_PQ_91Loads"
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

# %% READ OPERATION EXCEL FILE

d_op = read_data.read_data(excel_op)

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

#%% Create GridCal Model
GridCal_grid = GridCal_powerflow.create_model(path_raw, raw_file)
   
# %% READ EXCEL FILE

# Read data of grid elements from Excel file
d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)

# TO BE DELETED
d_grid = read_data.tempTables(d_grid)

# # Read simulation configuration parameters from Excel file
# sim_config = read_data.get_simParam(excel_sys)
# %% Preprare to iterate
import random
vmin=0.95
vmax=1.05
# Initialize voltage column
d_raw_data['generator']['V']=np.zeros([len(d_raw_data['generator']),1])

# Find I of slack bus
slack_bus=65
i_slack_bus= d_raw_data['results_bus'].query('I==@slack_bus').index[0]

# Assign random voltage to slack bus
V=random.uniform(vmin, vmax)
# d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @slack_bus').index[0],'V']=V

# Initialize voltage matrix
# adj_matrix=GridCal_grid.get_adjacent_matrix()
main_circuit=compile_numerical_circuit_at(GridCal_grid)
C=main_circuit.Cf+main_circuit.Ct
adj_matrix=C.T.dot(C)

# Find buses adjacents to slack_bus
idx_adj_buses=list(GridCal_grid.get_adjacent_buses(adj_matrix, int(i_slack_bus)))
adj_buses= d_raw_data['results_bus'].loc[idx_adj_buses,'I']

# Relation table between index and ID for all the nodes
indx_id=np.zeros([len(d_raw_data['results_bus']),2])
indx_id[:,0]=d_raw_data['results_bus'].index
indx_id[:,1]=d_raw_data['results_bus']['I']


# initialize generators_id and generators_index
generators_id = d_raw_data['generator']['I'].tolist()
generators_index_list = []
for row in indx_id:
    if row[1] in generators_id:
        generators_index_list.append(row[0])


# Choose start parameters
start_node = i_slack_bus
pending = [start_node]
# node: distancia, num_modificacions 
distances = {start_node:[0,1]}
# Initialize a row to store de voltages calculated, with a length equal to the number of nodes
voltages = [0]*len(indx_id)
voltages[start_node]=V

#%% Define calculate_voltage function

def calculate_voltage(adjacent_node, current_node):
    # Aumento en una unitat el nombre de modificacions
    distances[adjacent_node][1]+=1
    num_modifications = distances[adjacent_node][1]
    # Miro si el node contigu es generador
    if adjacent_node in generators_index_list:
        V=random.uniform(-0.02,0.02)+voltages[current_node]
        if num_modifications == 1:
            V_adjacent_node = V
        elif num_modifications > 1:
            V_adjacent_node = (num_modifications-1)*(voltages[adjacent_node]/num_modifications) + V/num_modifications
        if V_adjacent_node < vmin:
            voltages[adjacent_node]=vmin
        elif V_adjacent_node > vmax:
            voltages[adjacent_node]=vmax
        else:
            voltages[adjacent_node]=V_adjacent_node
    else:
        voltages[adjacent_node]=voltages[current_node]

#%% Iterate        
        
while len(pending)>0:
    to_calculate = []
    current_node = pending[0]
    current_node_distance = distances[current_node][0]
    adjacent_nodes_list = list(GridCal_grid.get_adjacent_buses(adj_matrix, int(current_node)))
    for adjacent_node in adjacent_nodes_list:
        if adjacent_node != current_node:
    # for adjacent_node, num in enumerate(adj_matrix[current_node]):
        # if num == 1:
            adjacent_node_distance = distances.get(adjacent_node, None)
            if adjacent_node_distance is None :
                to_calculate.append(adjacent_node)
                pending.append(adjacent_node)
                distances[adjacent_node]=[current_node_distance+1,0]
            elif adjacent_node_distance[0] > current_node_distance:
                to_calculate.append(adjacent_node)            
    for adjacent_node in to_calculate:
        calculate_voltage(adjacent_node, current_node)
#    print(f"El node {current_node} donara a {to_calculate}")
    current_bus=d_raw_data['results_bus'].loc[current_node,'I']
    to_calculate_bus=list(d_raw_data['results_bus'].loc[to_calculate,'I'])
    print(f"El bus {current_bus} donara a {to_calculate_bus}")
    pending.pop(0)
    # print(voltages)
# print(distances)

#%% Add the values to de dataframe
for i in range(len(voltages)):
    if i in generators_index_list:
        Identifier = indx_id[i][1]
        d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @Identifier').index[0],'V']=voltages[i]

        


# for path in distinct_paths:
#     for node in path:
#         if voltage_dict.get(node)==None:
#             voltage_dict[node]=[]
#             if parent == None:
#                 voltage_dict[node]=random.uniform(vmin, vmax)
#             else:
#                 v=random.uniform(-0.02, 0.02)+voltage_dict.get(parent)
#                 if v <vmin:
#                     voltage_dict[node]=vmin
#                 elif v>vmax:
#                     voltage_dict[node]=vmax
#                 else:
#                     voltage_dict[node]=v

#         parent=node
