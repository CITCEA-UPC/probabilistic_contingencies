import pandas as pd
import numpy as np
import re
import control as ct
from control.matlab import ss
from stability_analysis.preprocess import preprocess_data
from stability_analysis.state_space import interconnect

def save_ss_matrices_fun(ss,path,filename):
    pd.DataFrame.to_csv(pd.DataFrame(ss.A),path+filename+'_A.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.B),path+filename+'_B.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.C),path+filename+'_C.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.D),path+filename+'_D.csv',index=False,header=False)
    

def generate_SS_NET_blocks(d_grid, delta_slk, connect_fun='append_and_connect',save_ss_matrices=False):
    """
    Generate State-Space Blocks for the Power Grid Model.

    Parameters:
    - d_grid (dict): Dictionary containing all element's tables.
    - delta_slk (float): Slack bus angle.

    Returns:
    - l_blocks (list): List of State-Space blocks for the power grid subsystems.
    - l_states (list): List of state labels corresponding to the State-Space blocks.
    - d_grid (dict): Updated power grid model.

    This function generates State-Space blocks for various subsystems in the power grid model, including AC grid, RL NET,
    PI NET, transformers, thevenin equivalents (TH), loads, and DC grid. It takes into account connectivity matrices and
    specific tables for each subsystem.

    The generated State-Space blocks and associated state labels are returned along with the updated power grid model.
    """
        
    l_blocks = [] # Create list to store subsystems blocks
    l_states = [] # Create list to store subsystems state labels
    d_grid = xb2lc(d_grid) # Convert X,B columns to R,L

    # AC Grid       
    # Generates the Connectivity Matrix and the Table of nodes for the AC grid:
    connect_mtx, connect_mtx_PI, connect_mtx_rl = generate_general_connect_mtx(d_grid)
    T_nodes = generate_T_nodes(d_grid)      
    
    # RL NET:    
    # Manage transformers:
    connect_mtx_rl, T_NET_wTf, T_trafo_missing = add_trafo(d_grid, connect_mtx_rl, connect_mtx_PI)
    # rl_T_nodes: includes nodes where any RL/trafo is connected + "Additional TH" nodes
    rl_T_nodes = generate_specific_T_nodes_v2(connect_mtx_rl, T_nodes);    
    # Manage TH: 
    connect_mtx_rl, T_NET_wTf_wTh, T_TH_missing, rl_T_nodes = add_TH(d_grid['T_TH'], connect_mtx_rl, connect_mtx_PI, T_NET_wTf, rl_T_nodes)        
    # rl_T_NET: includes RL lines + trafos connected to any RL + "Additional TH" lines       
    rl_T_NET = get_specific_NET(connect_mtx_rl, T_NET_wTf_wTh)    
    # Get PI T_nodes
    PI_T_nodes = generate_specific_T_nodes_v2(connect_mtx_PI, T_nodes);
    # Generate the State-Space of the AC RL grid
    l_blocks, l_states = generate_general_rl_NET_v3(connect_mtx_rl, rl_T_nodes, PI_T_nodes, rl_T_NET, d_grid['T_global'], l_blocks, l_states,
                                                    connect_fun,save_ss_matrices)
       
    # PI NET         
    PI_T_NET = get_specific_NET(connect_mtx_PI, d_grid['T_NET'])
    # Generates the State-Space of the AC PI grid
    l_blocks, l_states = generate_general_PI_NET(connect_mtx_PI, connect_mtx_rl, PI_T_nodes, T_trafo_missing, d_grid, l_blocks, l_states,
                                                 connect_fun,save_ss_matrices)
        
    # Trafos 
    l_blocks, l_states = build_trafo(T_trafo_missing, d_grid['T_global']['fb'][0], l_blocks, l_states)
    
    # TH 
    l_blocks, l_states = build_TH(T_TH_missing, d_grid['T_global']['fb'][0], l_blocks, l_states)   
    
    # Loads
    l_blocks, l_states = build_load(d_grid['T_load'], connect_mtx_PI, connect_mtx_rl, T_nodes, d_grid['T_global']['fb'][0], delta_slk, l_blocks, l_states,
                                    connect_fun,save_ss_matrices)
            
    # DC Grid
    # Generate_DC_connectivity_matrix
    l_blocks, l_states = generate_DC_NET(d_grid['T_DC_NET'], l_blocks, l_states)
        
    return l_blocks, l_states, d_grid


# %% GENERATE NET GENERAL FUNCTIONS

def xb2lc(d_grid):
    """
    Convert Reactance and Susceptance to Inductance and Capacitance in Power Grid Model.

    Parameters:
    - d_grid (dict): Dictionary representing the power grid model.

    Returns:
    - d_grid (dict): Updated power grid model with inductance (L) and capacitance (C) values.

    This function performs the conversion of reactance (X) and susceptance (B) values to inductance (L) and capacitance (C)
    for various elements in the power grid model, including transmission lines, transformers, loads, and synchronous machines.
    The conversion is based on the relationship between these parameters and the base frequency (fb) associated with each area
    in the power grid.

    The input dictionary 'd_grid' is modified in-place, and the updated version is returned.
    """
    
    T_buses = d_grid['T_buses']
#    T_buses['fb'] = d_grid['T_buses']['SyncArea'].map(d_grid['T_global'].set_index('SyncArea')['fb']) 
    for SyncArea, fb in d_grid['T_global'].set_index('SyncArea')[['fb']].iterrows():
        # print(SyncArea)
        # print(fb)

        # TODO: Cambiado fb[0] por fb.iloc[0]. Recambiado
        T_buses.loc[T_buses.query('SyncArea == @SyncArea').index,'fb'] =  fb[0]
        
    d_grid['T_NET']['L'] = d_grid['T_NET']['X'] / (2 * np.pi * d_grid['T_NET']['bus_from'].map(T_buses.set_index('bus')['fb']))
    d_grid['T_NET']['C'] = d_grid['T_NET']['B'] / (2 * np.pi * d_grid['T_NET']['bus_from'].map(T_buses.set_index('bus')['fb'])) / 2

    d_grid['T_trafo']['L'] = d_grid['T_trafo']['X'] / (2 * np.pi * d_grid['T_trafo']['bus_from'].map(T_buses.set_index('bus')['fb']))
    d_grid['T_trafo']['C'] = d_grid['T_trafo']['B'] / (2 * np.pi * d_grid['T_trafo']['bus_from'].map(T_buses.set_index('bus')['fb']))

    d_grid['T_load']['L'] = d_grid['T_load']['X'] / (2 * np.pi * d_grid['T_load']['bus'].map(T_buses.set_index('bus')['fb']))
    
    d_grid['T_TH']['L'] = d_grid['T_TH']['X'] / (2 * np.pi * d_grid['T_TH']['Area'].map(T_buses.set_index('bus')['fb']))
    
    return d_grid



def generate_general_connect_mtx(d_grid):

    T_NET = d_grid['T_NET']
    
    # Connectivity Matrix generation:
    n_nodes = int(max([max(T_NET['bus_from']), max(T_NET['bus_to'])]))
    connect_mtx_rl = np.zeros((n_nodes, n_nodes), dtype=np.int8)
    connect_mtx_PI = np.zeros((n_nodes, n_nodes), dtype=np.int8)
    for i in range(len(T_NET)):
        if T_NET['B'][i] == 0:
            connect_mtx_rl[int(T_NET['bus_from'][i]-1), int(T_NET['bus_to'][i]-1)] = 1
        else:
            connect_mtx_PI[int(T_NET['bus_from'][i]-1), int(T_NET['bus_to'][i]-1)] = 1
    connect_mtx_rl = connect_mtx_rl + connect_mtx_rl.T
    connect_mtx_PI = connect_mtx_PI + connect_mtx_PI.T
    connect_mtx = connect_mtx_PI + connect_mtx_rl
    
    return connect_mtx, connect_mtx_PI, connect_mtx_rl
    

def generate_T_nodes(d_grid):   
    
    T_NET = d_grid['T_NET']
    T_trafo = d_grid['T_trafo']
    T_load = d_grid['T_load']
    T_TH = d_grid['T_TH']
    T_SG = d_grid['T_SG']
    T_VSC = d_grid['T_VSC']
    T_MMC = d_grid['T_MMC']
    T_user = d_grid['T_user']
     
    # Create empty T_nodes dataframe
    # Size: sz = (tn, nsb+1)
    # Columns: Node (int64), Element_n (str)
    
    # Total node number 
    tn = max(T_NET['bus_from'].max(), T_NET['bus_to'].max(), T_trafo['bus_from'].max(), T_trafo['bus_to'].max())     
    nsb = np.zeros(int(tn))
    for node in range(1, tn+1):
        nsb[node-1] = sum([T_load['bus'].eq(node).sum(), T_TH['bus'].eq(node).sum(), T_SG['bus'].eq(node).sum(), 
                          T_VSC['bus'].eq(node).sum(), T_MMC['NodeAC'].eq(node).sum(),T_user['bus'].eq(node).sum()])
    nsb = int(max(nsb))
         
    init_nodes = np.zeros([tn,1], dtype = int)  # Initialize column Node
    init_elements = np.empty([tn,nsb], dtype = str) # Initialize columns Element_n    
    df_nodes = pd.DataFrame(init_nodes, columns=['Node'])
    df_elements = pd.DataFrame(init_elements, columns=[f'Element_{i}' for i in range(1, nsb+1)])
    T_nodes = pd.concat([df_nodes, df_elements], axis=1)    
        
    # Assign values to the T_nodes dataframe
    T_nodes['Node'] = range(1, tn+1)
        
    for mmc in range(len(T_MMC)):
        emptyCellnotFound = True
        i = 1
        while(emptyCellnotFound):
            if (T_nodes.loc[T_nodes['Node'] == T_MMC['NodeAC'][mmc], f'Element_{i}'] == '').any(): #cell not empty
                emptyCellnotFound = False
            else:
                i = i+1
        # Assign element name
        T_nodes.loc[T_nodes['Node'] == T_MMC['NodeAC'][mmc], f'Element_{i}'] = f"MMC{int(T_MMC['number'][mmc])}"
        
                
    
    xx_list = [T_load, T_TH, T_SG, T_VSC, T_user]
    xx_names = ["load", "TH", "SG", "VSC", "user"]
    
    for idx, T_xx in enumerate(xx_list):
        for xx in range(len(T_xx)):
            emptyCellnotFound = True
            i = 1
            while(emptyCellnotFound):
                if (T_nodes.loc[T_nodes['Node'] == T_xx['bus'][xx], f'Element_{i}'] == '').any(): #cell not empty
                    emptyCellnotFound = False
                else:
                    i = i+1
            # Assign element name
            T_nodes.loc[T_nodes['Node'] == T_xx['bus'][xx], f'Element_{i}'] = f"{xx_names[idx]}{int(T_xx['number'][xx])}"
    
    return T_nodes

# def add_trafo(d_grid, connect_mtx_rl, connect_mtx_PI):
        
#     T_NET = d_grid['T_NET'].copy()
#     T_trafo = d_grid['T_trafo']
#     number = np.max(T_NET['number']) + 1    
#     missing = []
    
#     # 1 -  Check if there are trafos in series
#     buses_series = np.unique(np.concatenate((T_trafo['bus_from'][T_trafo['bus_from'].isin(T_trafo['bus_to'])], T_trafo['bus_to'][T_trafo['bus_to'].isin(T_trafo['bus_from'])])))
#     buses_AC_NET = np.concatenate((T_NET['bus_from'], T_NET['bus_to']))
   
#     if not np.all(np.isin(buses_series, buses_AC_NET)):
#         raise ValueError("There are trafos in series. Put them as RL lines in AC-NET.")
#         # Code could be improved to do this automatically
    
#     # 2 - Expand connect_mtx with zeros in order to match the size defined by the highest bus in T_trafo
#     max_bus_trafo = np.max(np.concatenate((T_trafo['bus_from'], T_trafo['bus_to'])))
#     max_bus_rl_net = connect_mtx_rl.shape[0]
    
#     if max_bus_trafo > max_bus_rl_net:
#         connect_mtx_rl = np.pad(connect_mtx_rl, ((0, max_bus_trafo - max_bus_rl_net), (0, max_bus_trafo - max_bus_rl_net)), mode='constant')
    
#     max_bus_pi_net = connect_mtx_PI.shape[0]
#     if max_bus_trafo > max_bus_pi_net:
#         connect_mtx_PI = np.pad(connect_mtx_PI, ((0, max_bus_trafo - max_bus_pi_net), (0, max_bus_trafo - max_bus_pi_net)), mode='constant')
     
#      # 3 - Add trafos to connectivity matrix  
#     for i in range(len(T_trafo)):
#         if T_trafo['B'][i] == 0:
#             connect_mtx_rl[int(T_trafo['bus_from'][i]-1), int(T_trafo['bus_to'][i]-1)] = 1
#             connect_mtx_rl[int(T_trafo['bus_to'][i]-1), int(T_trafo['bus_from'][i]-1)] = 1
#         else:
#             connect_mtx_PI[int(T_trafo['bus_from'][i]-1), int(T_trafo['bus_to'][i]-1)] = 1
#             connect_mtx_PI[int(T_trafo['bus_to'][i]-1), int(T_trafo['bus_from'][i]-1)] = 1

#         T_NET.loc[len(T_NET)] = [number, T_trafo['bus_from'][i], T_trafo['bus_to'][i], T_trafo['R'][i], T_trafo['X'][i], 0, 1, T_trafo['L'][i], T_trafo['C'][i]]
#         number += 1

#     T_trafo_missing = T_trafo.iloc[missing]
    
#     return connect_mtx_rl, T_NET, T_trafo_missing


def add_trafo(d_grid, connect_mtx_rl, connect_mtx_PI):
        
    T_NET = d_grid['T_NET'].copy()
    T_trafo = d_grid['T_trafo']
    number = np.max(T_NET['number']) + 1    
    missing = []
    
    # 1 -  Check if there are trafos in series
    buses_series = np.unique(np.concatenate((T_trafo['bus_from'][T_trafo['bus_from'].isin(T_trafo['bus_to'])], T_trafo['bus_to'][T_trafo['bus_to'].isin(T_trafo['bus_from'])])))
    buses_AC_NET = np.concatenate((T_NET['bus_from'], T_NET['bus_to']))
   
    if not np.all(np.isin(buses_series, buses_AC_NET)):
        raise ValueError("There are trafos in series. Put them as RL lines in AC-NET.")
        # Code could be improved to do this automatically
    
    # 2 - Expand connect_mtx with zeros in order to match the size defined by the highest bus in T_trafo
    max_bus_trafo = np.max(np.concatenate((T_trafo['bus_from'], T_trafo['bus_to'])))
    max_bus_rl_net = connect_mtx_rl.shape[0]
    
    if max_bus_trafo > max_bus_rl_net:
        connect_mtx_rl = np.pad(connect_mtx_rl, ((0, max_bus_trafo - max_bus_rl_net), (0, max_bus_trafo - max_bus_rl_net)), mode='constant')
    
    max_bus_pi_net = connect_mtx_PI.shape[0]
    if max_bus_trafo > max_bus_pi_net:
        connect_mtx_PI = np.pad(connect_mtx_PI, ((0, max_bus_trafo - max_bus_pi_net), (0, max_bus_trafo - max_bus_pi_net)), mode='constant')
     
     # 3 - Add trafos to connectivity matrix  
    for tf in range(len(T_trafo)):
        # A) Trafos that are connected to an RL line in ANY bus are added to connect_mtx_RL and to T_NET
        if np.sum(connect_mtx_rl[int(T_trafo['bus_from'][tf] - 1), :]) > 0 or np.sum(connect_mtx_rl[int(T_trafo['bus_to'][tf] - 1), :]) > 0:
            connect_mtx_rl[int(T_trafo['bus_from'][tf] - 1), int(T_trafo['bus_to'][tf] - 1)] = 1
            connect_mtx_rl[int(T_trafo['bus_to'][tf] - 1), int(T_trafo['bus_from'][tf] - 1)] = 1
            T_NET.loc[len(T_NET)] = [number, T_trafo['bus_from'][tf], T_trafo['bus_to'][tf], T_trafo['R'][tf], T_trafo['X'][tf], 0, 1, T_trafo['L'][tf], T_trafo['C'][tf]]
            number += 1
        # B) Trafos connected between PI lines in BOTH buses --> "missing"
        # are not added to any connect_mtx because are built as independent elements
        elif np.sum(connect_mtx_PI[int(T_trafo['bus_from'][tf] - 1), :]) > 0 and np.sum(connect_mtx_PI[int(T_trafo['bus_to'][tf] - 1), :]) > 0:
            missing.append(tf)
        # C) The Trafo is connected to a PI line and to a terminal element in one of the buses   
        # the terminal element cannot be a current source !!
        else:
            missing.append(tf)
            # print(f"Ensure that Trafo {T_trafo['number'][tf]} is connected to a voltage source.")
            # print("SGs and VSCs are current sources --> Add a Load to the bus.")
            # print("THs are current sources -->  Add the trafo as an RL in AC-NET.")

    T_trafo_missing = T_trafo.iloc[missing]
    
    return connect_mtx_rl, T_NET, T_trafo_missing


def generate_specific_T_nodes_v2(connect_mtx_rl, T_nodes):
    
    lines = np.sum(connect_mtx_rl, axis=0)
    for idx,val in enumerate(lines):
        if val == 0:
            T_nodes = T_nodes.drop(idx)
    T_nodes_specific = T_nodes.copy()
    return T_nodes_specific


def add_TH(T_TH, connect_mtx_rl, connect_mtx_PI, T_NET_wTf, rl_T_nodes): 
    
    nodeACmax = connect_mtx_rl.shape[0] + 1
    number = np.max(T_NET_wTf['number']) + 1
    missing = []

    for th in range(T_TH.shape[0]):
        if np.sum(connect_mtx_rl[T_TH['bus'][th]-1, :]) > 0 and np.sum(connect_mtx_PI[T_TH['bus'][th]-1, :]) == 0:
            
            # Create new RL node            
            newCol = np.zeros((connect_mtx_rl.shape[0],1))
            newCol[T_TH['bus'][th]-1,0] = 1
            connect_mtx_rl = np.append(connect_mtx_rl,newCol,axis = 1)
            
            newRow = np.zeros((1,connect_mtx_rl.shape[1]))
            newRow[0,T_TH['bus'][th]-1] = 1
            connect_mtx_rl = np.append(connect_mtx_rl,newRow,axis = 0)
            
            # Add row to T_NET
            T_NET_wTf.loc[len(T_NET_wTf)] = [number, T_TH['bus'][th], nodeACmax, T_TH['R'][th], T_TH['X'][th], 0, 1, T_TH['L'][th], 0]
            
            # Add row to rl_T_nodes
            nsb = len(rl_T_nodes.columns)-1
            init_nodes = np.zeros([1,1], dtype = int)  # Initialize column Node
            init_elements = np.empty([1,nsb], dtype = str) # Initialize columns Element_n    
            df_nodes = pd.DataFrame(init_nodes, columns=['Node'])
            df_elements = pd.DataFrame(init_elements, columns=[f'Element_{i}' for i in range(1, nsb+1)])
            T_nodes = pd.concat([df_nodes, df_elements], axis=1)    
            
            T_nodes.loc[0, 'Node'] = nodeACmax            
            T_nodes.loc[0, 'Element_1':] = ['Additional TH' + str(T_TH['number'][th])]+['']*(nsb-1)
            rl_T_nodes = pd.concat([rl_T_nodes, T_nodes], axis=0)  
                    
            nodeACmax += 1            
            number += 1
            
        else:
            missing.append(th)

    T_TH_missing = T_TH.iloc[missing, :]

    return connect_mtx_rl, T_NET_wTf, T_TH_missing, rl_T_nodes    
    
    
def get_specific_NET(connect_mtx, T_NET):
    index = []
    
    for i in range(connect_mtx.shape[0]):
        for j in range(connect_mtx.shape[1]):
            if connect_mtx[i, j] == 1:
                found_rows = T_NET[(T_NET['bus_from'] == i+1) & (T_NET['bus_to'] == j+1)]
                if not found_rows.empty:
                    index.append(found_rows.index[0])
    
    NET = T_NET.loc[index, :]    
    return NET    

# %% GENERATE RL NET

def generate_general_rl_NET_v3(connect_mtx_rl, rl_T_nodes, PI_T_nodes, rl_T_NET, T_global, l_blocks, l_states, connect_fun='append_and_connect',save_ss_matrices=False):
    
            
    def generate_ss_rl(R1, L1, bus_from, bus_to, f):
        """
        Generate State-Space of RL lines.
        """
        
        bus_from = int(bus_from)
        bus_to = int(bus_to)
        
        # Generate SS of RL line
        w = 2*np.pi*f # grid frequency
        
        Arl = np.array([[-R1/L1, -w], [w, -R1/L1]])        
        Brl = np.array([[1/L1, 0, -1/L1, 0], [0, 1/L1, 0, -1/L1]])        
        Crl = np.array([[1, 0], [0, 1]])        
        Drl = np.zeros((2, 4))
        
        if bus_from > bus_to:
            input_name = ['NET_vn' + str(bus_to) + 'q','NET_vn' + str(bus_to) + 'd','NET_vn' + str(bus_from) + 'q','NET_vn' + str(bus_from) + 'd']
            output_name = ['NET_iq_' + str(bus_to) + '_' + str(bus_from), 'NET_id_' + str(bus_to) + '_' + str(bus_from)]
        else:
            input_name = ['NET_vn' + str(bus_from) + 'q','NET_vn' + str(bus_from) + 'd','NET_vn' + str(bus_to) + 'q','NET_vn' + str(bus_to) + 'd']
            output_name = ['NET_iq_' + str(bus_from) + '_' + str(bus_to), 'NET_id_' + str(bus_from) + '_' + str(bus_to)]
    
        rl_x = ['NET_iq_' + str(bus_from) + '_' + str(bus_to), 'NET_id_' + str(bus_from) + '_' + str(bus_to)]        
        rl = ss(Arl, Brl, Crl, Drl, inputs = input_name, outputs = output_name, states = rl_x)            
        return rl, rl_x
    
    
    def crea_union(rl_T_NET, rows_out, rows_in, BUS):
        """
        Generate State-Space of BUS Voltage Calculation (Internal Bus).
    
        Parameters:
        - rl_T_NET (DataFrame): DataFrame containing RL network information.
        - rows_out (array): Boolean array indicating RL lines with current flowing out of the internal bus.
        - rows_in (array): Boolean array indicating RL lines with current flowing into the internal bus.
        - BUS (int): Node ID of the internal bus.
    
        Returns:
        - ss_union_q (StateSpace): State-Space model for q-component of BUS voltage.
        - ss_union_d (StateSpace): State-Space model for d-component of BUS voltage.
    
        This function calculates the State-Space models for the q and d components of the BUS voltage for an internal bus
        connected to RL lines. It considers RL lines with currents flowing in and out of the bus, generating matrices
        (D_q and D_d) based on the resistance (R) and inductance (L) parameters of these lines. The matrices are then used to
        create State-Space models for the q and d components.
        """
    
        # Get RL values of RL lines connected to the BUS
        R_out = rl_T_NET[rows_out]['R']
        L_out = rl_T_NET[rows_out]['L']
        R_in = rl_T_NET[rows_in]['R']
        L_in = rl_T_NET[rows_in]['L']
    
        # Get buses of RL lines connected to the BUS
        nodes_out = rl_T_NET[rows_out]['bus_to'].astype(int)
        nodes_in = rl_T_NET[rows_in]['bus_from'].astype(int)
    
        # 1) q component -------------------------------------------------------
    
        # Set output variable: BUS voltage
        outputnames_q = 'NET_vn' + str(int(BUS)) + 'q'
    
        # Set input variables:
        # - currents of RL lines connected to the BUS
        # - voltages of buses of RL lines connected to the BUS
        inputnames_q = ['NET_iq_' + str(int(nodes_in.iloc[j])) + '_' + str(int(BUS)) for j in range(len(nodes_in))]
        inputnames_q += ['NET_iq_' + str(int(BUS)) + '_' + str(int(nodes_out.iloc[j])) for j in range(len(nodes_out))]
        inputnames_q += ['NET_vn' + str(int(nodes_in.iloc[j])) + 'q' for j in range(len(nodes_in))]
        inputnames_q += ['NET_vn' + str(int(nodes_out.iloc[j])) + 'q' for j in range(len(nodes_out))]
    
        # Generate D_q matrix == calculation of BUS q-voltage
        sum_L = 0
        D_q = np.zeros((1, len(inputnames_q)))
    
        # Is
        for j in range(len(nodes_in)):
            D_q[0, j] = R_in.iloc[j] / L_in.iloc[j]
            sum_L -= 1 / L_in.iloc[j]
    
        jj = 0
        for j in range(len(nodes_in), len(nodes_in) + len(nodes_out)):
            D_q[0, j] = -R_out.iloc[jj] / L_out.iloc[jj]
            sum_L -= 1 / L_out.iloc[jj]
            jj += 1
    
        # Vs
        jj = 0
        for j in range(len(nodes_in) + len(nodes_out), 2 * len(nodes_in) + len(nodes_out)):
            D_q[0, j] = -1 / L_in.iloc[jj]
            jj += 1
    
        jj = 0
        for j in range(2 * len(nodes_in) + len(nodes_out), 2 * len(nodes_in) + 2 * len(nodes_out)):
            D_q[0, j] = -1 / L_out.iloc[jj]
            jj += 1
    
        D_q = (1 / sum_L) * D_q
    
        # 2) d component --------------------------------------------------
    
        # Set output variable: BUS voltage
        outputnames_d = 'NET_vn' + str(int(BUS)) + 'd'
    
        # Set input variables:
        # - currents of RL lines connected to the BUS
        # - voltages of buses of RL lines connected to the BUS
        inputnames_d = ['NET_id_' + str(int(nodes_in.iloc[j])) + '_' + str(int(BUS)) for j in range(len(nodes_in))]
        inputnames_d += ['NET_id_' + str(int(BUS)) + '_' + str(int(nodes_out.iloc[j])) for j in range(len(nodes_out))]
        inputnames_d += ['NET_vn' + str(int(nodes_in.iloc[j])) + 'd' for j in range(len(nodes_in))]
        inputnames_d += ['NET_vn' + str(int(nodes_out.iloc[j])) + 'd' for j in range(len(nodes_out))]
  
    
        # Generate D_d matrix == calculation of BUS d-voltage
        sum_L = 0
        D_d = np.zeros((1, len(inputnames_d)))
    
        # Is
        for j in range(len(nodes_in)):
            D_d[0, j] = R_in.iloc[j] / L_in.iloc[j]
            sum_L -= 1 / L_in.iloc[j]
    
        jj = 0
        for j in range(len(nodes_in), len(nodes_in) + len(nodes_out)):
            D_d[0, j] = -R_out.iloc[jj] / L_out.iloc[jj]
            sum_L -= 1 / L_out.iloc[jj]
            jj += 1
    
        # Vs
        jj = 0
        for j in range(len(nodes_in) + len(nodes_out), 2 * len(nodes_in) + len(nodes_out)):
            D_d[0, j] = -1 / L_in.iloc[jj]
            jj += 1
    
        jj = 0
        for j in range(2 * len(nodes_in) + len(nodes_out), 2 * len(nodes_in) + 2 * len(nodes_out)):
            D_d[0, j] = -1 / L_out.iloc[jj]
            jj += 1
    
        D_d = (1 / sum_L) * D_d
    
        # 3) Generate State-Space calculation of qd BUS voltage -----------
    
        A = np.empty(0)
        B =np.empty((0, len(D_q[0])))
        C = np.empty((0, 1))
    
        ss_union_q = ss(A, B, C, D_q, inputs=inputnames_q, outputs=outputnames_q)
        ss_union_d = ss(A, B, C, D_d, inputs=inputnames_d, outputs=outputnames_d)
    
        return ss_union_q, ss_union_d
            
    
    if connect_mtx_rl.any():
        
        # Order the buses of the rl lines (bus_from < bus_to):
        rl_T_NET = preprocess_data.reorder_buses_lines(rl_T_NET)    
        
        # List of states and state-space blocks of the RL NET  
        list_x_rl = []
        list_ss_rl = []
        list_ss_union = []
        
        # Generate the global inputs/outputs of the RL NET        
        inputs = []
        outputs = [] 
        
        # Bus voltages
           # Voltage is OUTPUT if:
           # - It is an empty bus between RL lines
           # - There is a TH connected + only RL lines   
           # Voltage is INPUT if:
           # - It is an Additional TH bus (V_TH == vn[ADD_BUS]qd is an input)
           # - There is a PI line connected to the bus
           # - There is a voltage source element connected to the bus       
        
        for i in range(rl_T_nodes.shape[0]):
            row = rl_T_nodes.iloc[i, 1:]
            strings = row[row!=""].dropna().tolist()
            
            if ((not strings and rl_T_nodes.iloc[i]['Node'] not in PI_T_nodes['Node'].values) or 
                (any("TH" in s for s in strings) and not any("Additional" in s for s in strings) and rl_T_nodes.iloc[i]['Node'] not in PI_T_nodes['Node'].values)):
                outputs.append('NET_vn' + str(int(rl_T_nodes.iloc[i]['Node'])) + 'q') 
                outputs.append('NET_vn' + str(int(rl_T_nodes.iloc[i]['Node'])) + 'd')
            else:
                inputs.append('NET_vn' + str(int(rl_T_nodes.iloc[i]['Node'])) + 'q') 
                inputs.append('NET_vn' + str(int(rl_T_nodes.iloc[i]['Node'])) + 'd')               

        # Line currents
            # Positive current: bus_from --> bus_to
            # Negative current: bus_to --> bus_from

        for i in range(len(rl_T_NET)):
            if rl_T_NET.iloc[i]['B'] == 0:
                if rl_T_NET.iloc[i]['bus_from'] > rl_T_NET.iloc[i]['bus_to']:
                    outputs.append('NET_iq_' + str(int(rl_T_NET.iloc[i]['bus_to'])) + '_' +  str(int(rl_T_NET.iloc[i]['bus_from']))) 
                    outputs.append('NET_id_' + str(int(rl_T_NET.iloc[i]['bus_to'])) + '_' +  str(int(rl_T_NET.iloc[i]['bus_from']))) 
                else:
                    outputs.append('NET_iq_' + str(int(rl_T_NET.iloc[i]['bus_from'])) + '_' +  str(int(rl_T_NET.iloc[i]['bus_to']))) 
                    outputs.append('NET_id_' + str(int(rl_T_NET.iloc[i]['bus_from'])) + '_' +  str(int(rl_T_NET.iloc[i]['bus_to']))) 


        # Generate RL NET State-Space
        
        # Flag to check if there is an internal node:
        # A) Empty bus with only RL lines connected to it
        # B) TH bus with only RL lines connected to it
        internal_node = False
        
        # Generate the State-Space of each RL line in rl_T_NET
        for i in range(len(rl_T_NET)):
            # Generate SS of RL line
            rl, rl_x = generate_ss_rl(rl_T_NET.iloc[i]['R'], rl_T_NET.iloc[i]['L'], rl_T_NET.iloc[i]['bus_from'], rl_T_NET.iloc[i]['bus_to'], T_global.iloc[0]['f_Hz'])
            list_ss_rl.append(rl)
            list_x_rl.extend(rl_x)
        
            # Check what is connected in "bus_to" of the line
            row = rl_T_nodes.loc[rl_T_nodes['Node'] == rl_T_NET.iloc[i]['bus_to'], 'Element_1':]
            strings = row.loc[:, row.iloc[0] != ""].values[0].tolist()
        
            # Check if the "bus_to" is internal
            if ((not strings and rl_T_NET.iloc[i]['bus_to'] not in PI_T_nodes['Node']) or
               (any("TH" in s for s in strings) and not any("Additional" in s for s in strings) and rl_T_NET.iloc[i]['bus_to'] not in PI_T_nodes['Node'].values)):                
        
                # Raise internal_node flag
                internal_node = True
        
                # Identify direction of currents of the RL lines connected to the internal bus
                rows_in = rl_T_NET['bus_to'] == rl_T_NET.iloc[i]['bus_to']
                rows_out = rl_T_NET['bus_from'] == rl_T_NET.iloc[i]['bus_to']
        
                # Generate SS of BUS voltage calculation (internal bus)
                ss_union_q, ss_union_d = crea_union(rl_T_NET, rows_out, rows_in, rl_T_NET.iloc[i]['bus_to'])
                list_ss_union.append(ss_union_q)
                list_ss_union.append(ss_union_d)
        
                # In order to not repeat an isolated node
                rl_T_nodes.loc[rl_T_nodes['Node'] == rl_T_NET.iloc[i]['bus_to'], 'Element_1':] = '-'
        
        
        if internal_node:
            if connect_fun=='interconnect':
                SS_RL = ct.interconnect(list_ss_rl+list_ss_union, states = list_x_rl, inputs = inputs, outputs = outputs, check_unused = False)
                if save_ss_matrices==True:
                    save_ss_matrices_fun(SS_RL,'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/'+connect_fun+'_test/',
                                            f'{SS_RL=}'.split('=')[0])
            elif connect_fun=='append_and_connect':
                SS_RL = interconnect.interconnect(list_ss_rl+list_ss_union, states = list_x_rl, inputs = inputs, outputs = outputs, check_unused = False)
                if save_ss_matrices == True:
                    save_ss_matrices_fun(SS_RL,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun+'_test/',
                                          f'{SS_RL=}'.split('=')[0])
        else:
            if connect_fun == 'interconnect':
                SS_RL = ct.interconnect(list_ss_rl, inputs = inputs, outputs = outputs, check_unused = False)
                if save_ss_matrices == True:
                    save_ss_matrices_fun(SS_RL,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{SS_RL=}'.split('=')[0])
            elif connect_fun == 'append_and_connect':
                SS_RL = interconnect.interconnect(list_ss_rl, inputs = inputs, outputs = outputs, check_unused = False)

                if save_ss_matrices == True:
                    save_ss_matrices_fun(SS_RL,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{SS_RL=}'.split('=')[0])
        # Append SS to l_blocks
        l_blocks.append(SS_RL)
        l_states.extend(list_x_rl)
        
    return l_blocks, l_states
  
# %% GENERATE PI NET      
    
def generate_general_PI_NET(connect_mtx_PI, connect_mtx_rl, PI_T_nodes, T_trafo_missing, d_grid, l_blocks, l_states,
                            connect_fun='append_and_connect',save_ss_matrices=False):
    
    def construccio_SS_Cn( Cn , c_x , c_u , c_y ,f):
        
        # Generate SS of capacitor bus
        w = 2*np.pi*f # grid frequency  
        
        Ac = np.array([[0, -w], [w, 0]])        
        Bc = np.array([[1 / Cn, 0], [0, 1 / Cn]])        
        Cc = np.array([[1, 0], [0, 1]])        
        Dc = np.zeros((2, 2))

        c = ss(Ac, Bc, Cc, Dc, inputs = c_u, outputs = c_y, states = c_x)    
        return c
           

    def construccio_SS_rl( Rxy , Lxy , rl_x , rl_u, rl_y,f):
        
        # Generate SS of RL line
        w = 2*np.pi*f # grid frequency
        
        Arl = np.array([[-Rxy/Lxy, -w], [w, -Rxy/Lxy]])        
        Brl = np.array([[1/Lxy, -1/Lxy, 0, 0], [0, 0, 1/Lxy, -1/Lxy]])        
        Crl = np.array([[1, 0], [0, 1]])        
        Drl = np.zeros((2, 4))

        rl = ss(Arl, Brl, Crl, Drl, inputs = rl_u, outputs = rl_y, states = rl_x)    
        return rl


    def construccio_SS_nus( Din , llista_u_nus , llista_y_nus):
     
        # State-space sum of currents in node
        Ain = np.empty(0)
        columns_Bin = Din.shape[1]
        Bin = np.empty((0, columns_Bin))
        Cin = np.empty((0, 2))
        in_ss = ss(Ain, Bin, Cin, Din, inputs = llista_u_nus, outputs = llista_y_nus)  
        return in_ss
    
       
    
    if connect_mtx_PI.any():
        T_NET = d_grid['T_NET']
        f = d_grid['T_global']['f_Hz'][0]
        
        # List of all the SS-blocks
        llista_SS_rl = []
        llista_SS_C = []
        llista_SS_nus = []
        
        # List of states and I/O names for the complete SS
        llista_x_AC = []
        llista_u_AC = []
        llista_y_AC = []
                
        # Iterate over the buses in Connectivity_Matrix_PI
        
        for ii in range(connect_mtx_PI.shape[0]):
            if sum(connect_mtx_PI[ii,:]) > 0:
                Cn = 0
                position = np.where(connect_mtx_PI[ii,:]==1)[0]
                for Node in position:
                    C1 = T_NET.loc[ (T_NET['bus_from'] == ii+1) & (T_NET['bus_to'] == Node+1), 'C']
                    C2 = T_NET.loc[ (T_NET['bus_from'] == Node+1) & (T_NET['bus_to'] == ii+1), 'C']  
                    
                    if C1.empty:
                        C1 = T_NET.loc[(T_NET['bus_from'] == Node+1) & (T_NET['bus_to'] == ii+1), 'C'].values[0] / 2
                    else:
                        C1 = C1.values[0] / 2
                    if C2.empty:
                        C2 = T_NET.loc[(T_NET['bus_from'] == ii+1) & (T_NET['bus_to'] == Node+1), 'C'].values[0] / 2
                    else:
                        C2 = C2.values[0] / 2
                        
                    Cn += C1 + C2
                    
                c_x = ['vc_q'+str(ii+1), 'vc_d'+str(ii+1)]
                c_u = ['ic_q'+str(ii+1), 'ic_d'+str(ii+1)]
                c_y = ['NET_vn'+str(ii+1)+'q', 'NET_vn'+str(ii+1)+'d']                                
                # Build SS of the condenser
                SS_C_i = construccio_SS_Cn(Cn , c_x , c_u , c_y, f);                 
                # Append SS of the condenser to the list
                llista_SS_C.append(SS_C_i)
                # Add outputs to global AC system:
                llista_y_AC.append('NET_vn'+str(ii+1)+'q')
                llista_y_AC.append('NET_vn'+str(ii+1)+'d')
                llista_x_AC.append('vc_q'+str(ii+1))
                llista_x_AC.append('vc_d'+str(ii+1))
                
                # Build D-matrix of the bus
                Din = []                
                # Create list for the bus-inputs
                llista_u_nus = []                
                # Create list for the bus-outputs
                llista_y_nus = ['ic_q'+str(ii+1), 'ic_d'+str(ii+1)]  
                
                # Find elements connected to bus
                
                for idx,row in T_trafo_missing.iterrows():
                    if row['bus_from'] == ii+1:
                        # Define bus inputs
                        llista_u_nus.append('Trafo' + str(int(row['number'])) + '_iq' + str(int(row['bus_from'])))
                        llista_u_nus.append('Trafo' + str(int(row['number'])) + '_id' + str(int(row['bus_from'])))
                        # Update Din
                        Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                        # Define global input of the system
                        llista_u_AC.append('Trafo' + str(int(row['number'])) + '_iq' + str(int(row['bus_from'])))
                        llista_u_AC.append('Trafo' + str(int(row['number'])) + '_id' + str(int(row['bus_from'])))
                    if row['bus_to'] == ii+1:
                        # Define bus inputs
                        llista_u_nus.append('Trafo' + str(int(row['number']))+ '_iq' + str(int(row['bus_to'])))
                        llista_u_nus.append('Trafo' + str(int(row['number']))+ '_id' + str(int(row['bus_to'])))
                        # Update Din
                        Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                        # Define global input of the system
                        llista_u_AC.append('Trafo' + str(int(row['number'])) + '_iq' + str(int(row['bus_to'])))   
                        llista_u_AC.append('Trafo' + str(int(row['number'])) + '_id' + str(int(row['bus_to'])))  
                        
                        
                PI_T_nodes_row = PI_T_nodes.loc[PI_T_nodes['Node'] == ii+1]
                for column in PI_T_nodes_row.columns[1:]:
                    value = PI_T_nodes_row[column]
                    if not (value.values[0] == ''):
                        match = re.match(r'([A-Za-z]+)(\d+)', value.values[0])
                        element = match.group(1)
                        number = match.group(2)
                                                
                        if element == 'load': 
                            # Define bus inputs
                            llista_u_nus.append('Load' + number + '_iq')
                            llista_u_nus.append('Load' + number + '_id')
                            # Update Din
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            # Define global input of the system
                            llista_u_AC.append('Load' + number + '_iq')   
                            llista_u_AC.append('Load' + number + '_id')  
                        
                        elif element == 'TH':
                            # Define bus inputs
                            llista_u_nus.append('TH' + number + '_iq')
                            llista_u_nus.append('TH' + number + '_id')
                            # Update Din
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            # Define global input of the system
                            llista_u_AC.append('TH' + number + '_iq')   
                            llista_u_AC.append('TH' + number + '_id')  
                            
                        elif element == 'SG':
                            # Define bus inputs
                            llista_u_nus.append('SG' + number + '_iq')
                            llista_u_nus.append('SG' + number + '_id')
                            # Update Din
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            # Define global input of the system
                            llista_u_AC.append('SG' + number + '_iq')   
                            llista_u_AC.append('SG' + number +'_id')  
                            
                        elif element == 'VSC':
                            mode = d_grid['T_VSC'].loc[(d_grid['T_VSC']['bus'] == ii+1) & (d_grid['T_VSC']['number'] == int(number)), "mode"].values[0]
                            # Define bus inputs
                            llista_u_nus.append(mode + number + '_iq')
                            llista_u_nus.append(mode + number + '_id')
                            # Update Din
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            # Define global input of the system
                            llista_u_AC.append(mode + number +'_iq')   
                            llista_u_AC.append(mode + number + '_id')                                 
                                
                        elif element == 'MMC':
                            # Define bus inputs
                            llista_u_nus.append('MMC' + number + '_idiffq')
                            llista_u_nus.append('MMC' + number + '_idiffd')
                            # Update Din
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            # Define global input of the system
                            llista_u_AC.append('MMC' + number + '_idiffq')   
                            llista_u_AC.append('MMC' + number +'_idiffd') 
                            
                        elif element == 'user':
                            # Define bus inputs
                            llista_u_nus.append('USER' + number + '_iq')
                            llista_u_nus.append('USER' + number + '_id')
                            # Update Din
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            # Define global input of the system
                            llista_u_AC.append('USER' + number + '_iq')   
                            llista_u_AC.append('USER' + number + '_id') 
                            
                        
                for jj in range(connect_mtx_PI.shape[1]):
                    if connect_mtx_PI[ii,jj] == 1:
                        if jj < ii:
                            # Build D-matrix of the bus
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            llista_u_nus.append('NET_iq_' + str(jj+1) + '_' + str(ii+1))
                            llista_u_nus.append('NET_id_' + str(jj+1) + '_' + str(ii+1))
                        elif jj > ii:
                            # Build D-matrix of the bus
                            Din.append(np.array([[-1, 0], [0, -1]])) #negative because it leaves the bus
                            llista_u_nus.append('NET_iq_' + str(ii+1) + '_' + str(jj+1))
                            llista_u_nus.append('NET_id_' + str(ii+1) + '_' + str(jj+1))     
                            # Set names of RL variables
                            rl_x = ['iq'+'_'+str(ii+1)+'_'+str(jj+1), 'id'+'_'+str(ii+1)+'_'+str(jj+1)]
                            rl_u = ['NET_vn'+str(ii+1)+'q', 'NET_vn'+str(jj+1)+'q', 'NET_vn'+str(ii+1)+'d', 'NET_vn'+str(jj+1)+'d'] 
                            rl_y = ['NET_iq_'+str(ii+1)+'_'+str(jj+1), 'NET_id_'+str(ii+1)+'_'+str(jj+1)]                    
                            # Build SS matrices of RL
                            SS_rl = construccio_SS_rl(T_NET.loc[(T_NET['bus_from']==ii+1) & (T_NET['bus_to']==jj+1),"R"].values[0] , T_NET.loc[(T_NET['bus_from']==ii+1) & (T_NET['bus_to']==jj+1),"L"].values[0] , rl_x , rl_u, rl_y,f);
                            # Append SS of the RL to the list
                            llista_SS_rl.append(SS_rl)                   
                            # Add outputs to global AC system:
                            llista_y_AC.append('NET_iq_'+str(ii+1)+'_'+str(jj+1))
                            llista_y_AC.append('NET_id_'+str(ii+1)+'_'+str(jj+1))         
                            llista_x_AC.append('iq'+'_'+str(ii+1)+'_'+str(jj+1))
                            llista_x_AC.append('id'+'_'+str(ii+1)+'_'+str(jj+1))
            
                
                for jj in range(connect_mtx_rl.shape[1]):
                    if connect_mtx_rl[ii,jj] == 1:
                        if jj < ii:
                            # Build D-matrix of the bus
                            Din.append(np.array([[1, 0], [0, 1]])) #positive because it enters the bus
                            llista_u_nus.append('NET_iq_' + str(jj+1) + '_' + str(ii+1))
                            llista_u_nus.append('NET_id_' + str(jj+1) + '_' + str(ii+1))
                            if not 'NET_iq_' + str(jj+1) + '_' + str(ii+1) in llista_u_AC:
                                llista_u_AC.append('NET_iq_' + str(jj+1) + '_' + str(ii+1))  
                                llista_u_AC.append('NET_id_' + str(jj+1) + '_' + str(ii+1))
                            
                        elif jj > ii: 
                            # Build D-matrix of the bus
                            Din.append(np.array([[-1, 0], [0, -1]])) #negative because it leaves the bus
                            llista_u_nus.append('NET_iq_' + str(ii+1) + '_' + str(jj+1))
                            llista_u_nus.append('NET_id_' + str(ii+1) + '_' + str(jj+1))
                            if not 'NET_iq_' + str(ii+1) + '_' + str(jj+1) in llista_u_AC:
                                llista_u_AC.append('NET_iq_' + str(ii+1) + '_' + str(jj+1)) 
                                llista_u_AC.append('NET_id_' + str(ii+1) + '_' + str(jj+1)) 
            
                # Build SS of the bus sum of currents
                Din = np.hstack(Din)
                SS_nus = construccio_SS_nus( Din , llista_u_nus , llista_y_nus)
                # Append SS of the bus sum of currents to the list
                llista_SS_nus.append(SS_nus)              
                       
        
        # Generate PI NET State-Space
        if connect_fun=='interconnect':
            PI_NET = ct.interconnect(llista_SS_rl + llista_SS_C + llista_SS_nus, states=llista_x_AC, inputs=llista_u_AC,
                                     outputs=llista_y_AC, check_unused=False)

            if save_ss_matrices == True:
                save_ss_matrices_fun(PI_NET,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{PI_NET=}'.split('=')[0])
        elif connect_fun == 'append_and_connect':
            PI_NET = interconnect.interconnect(llista_SS_rl + llista_SS_C + llista_SS_nus, states=llista_x_AC, inputs=llista_u_AC,
                                     outputs=llista_y_AC, check_unused=False)
            if save_ss_matrices == True:
                save_ss_matrices_fun(PI_NET,
                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                     f'{PI_NET=}'.split('=')[0])
        #Append SS to l_blocks 
        l_blocks.append(PI_NET)
        l_states.extend(llista_x_AC)
              
    return l_blocks, l_states
        


def build_trafo(T_trafo_missing, fb, l_blocks, l_states):
        
    for _,row in T_trafo_missing.iterrows():
        L = row['L']
        w_n = 2*np.pi*fb
        number = int(row['number'])
        nodeA = int(row['bus_from'])
        nodeB = int(row['bus_to'])
        R = row['R']
        
        A = np.array([[-R / L, -w_n],
                      [w_n, -R / L]])

        B = np.array([[1 / L, 0, -1 / L, 0],
                      [0, 1 / L, 0, -1 / L]])
        
        C = np.array([[-1, 0],
                      [0, -1],
                      [1, 0],
                      [0, 1]])
        
        D = np.zeros((4, 4))
        
        x = ['Trafo'+str(number)+'_iq', 'Trafo'+str(number)+'_id']
        u = ['NET_vn'+str(nodeA)+'q', 'NET_vn'+str(nodeA)+'d', 'NET_vn'+str(nodeB)+'q', 'NET_vn'+str(nodeB)+'d']
        y = ['Trafo'+str(number)+'_iq'+str(nodeA), 'Trafo'+str(number)+'_id'+str(nodeA),'Trafo'+str(number)+'_iq'+str(nodeB), 'Trafo'+str(number)+'_id'+str(nodeB)]
        
        trafo = ss(A, B, C, D, inputs = u, outputs = y, states = x)
        l_blocks.append(trafo)
        l_states.extend(x)        
    return l_blocks, l_states


def build_TH(T_TH_missing, fb, l_blocks, l_states):
        
    for _,row in T_TH_missing.iterrows():
        w_n = 2*np.pi*fb
        number = int(row['number'])
        nodeA = int(row['bus'])
        R = row['R']
        L = row['L']
        
        if L == 0:             
            A = np.empty(0)    
            B = np.empty((0,4))            
            C = np.empty((0, 2))            
            D = np.array([[1, 0, -1, 0], [0, 1, 0, -1]])*(1/R)
            
            u = ['TH'+str(number)+'_vnq', 'TH'+str(number)+'_vnd','NET_vn'+str(nodeA)+'q', 'NET_vn'+str(nodeA)+'d']
            y = ['TH'+str(number)+'_iq', 'TH'+str(number)+'_id']
            
            th = ss(A, B, C, D, inputs = u, outputs = y)
            l_blocks.append(th)
            
        else:     
            A = np.array([[-R / L, -w_n], [w_n, -R / L]])    
            B = np.array([[1 / L, 0, -1 / L, 0], [0, 1 / L, 0, -1 / L]])            
            C = np.array([[1, 0],[0, 1]])            
            D = np.zeros((2, 4))
            
            x = ['TH'+str(number)+'_iq_'+str(nodeA), 'TH'+str(number)+'_id_'+str(nodeA)]
            u = ['TH'+str(number)+'_vnq', 'TH'+str(number)+'_vnd','NET_vn'+str(nodeA)+'q', 'NET_vn'+str(nodeA)+'d']
            y = ['TH'+str(number)+'_iq', 'TH'+str(number)+'_id']

            th = ss(A, B, C, D, inputs = u, outputs = y, states = x)
            l_blocks.append(th)
            l_states.extend(x)
        
    return l_blocks, l_states

# %% LOADS

def build_load(T_load, connect_mtx_PI, connect_mtx_rl, T_nodes, f, delta_slk, l_blocks, l_states, connect_fun='append_and_connect', save_ss_matrices=False):
    """        
    Generates the State-Space for each load based on their connection to either ANY PI-line or ALL RL-lines
    
    For loads in PI-lines:
      - RL or R load: R can be either be a CONSTANT or an INPUT variable
    For loads in RL-lines:
      - R load: R can be either be a CONSTANT or an INPUT variable
      - RL load: R can only be a CONSTANT. R as INPUT is not implemented yet
    """
    
    def build_Load_in_PI_R_addR(row,delta_slk):
        
        R = row['R']
        number = int(row['number'])
        nodeAC = int(row['bus'])
        
        # Calculate vq0 vd0
        theta0 = row['theta'] * np.pi / 180 - delta_slk
        vq0 = row['V'] * np.cos(theta0) * np.sqrt(2 / 3)
        vd0 = -row['V'] * np.sin(theta0) * np.sqrt(2 / 3)
        
        Ar = np.empty(0)
        Br = np.empty((0,3))
        Cr = np.empty((0,2))
        Dr = np.array([[1/R, 0, -vq0/(R**2)],[0, 1/R, -vd0/(R**2)]]) * -1
        
        ur = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd', 'NET_Rld' + str(number)]
        yr = ['Load' + str(number) + '_irq', 'Load' + str(number) + '_ird']
        
        load = ss(Ar, Br, Cr, Dr, inputs = ur, outputs = yr)        
        
        return load
    
    
    def build_Load_in_PI_addR(row,f,delta_slk, connect_fun='append_and_connect',save_ss_matrices=False, n_load=None):
    
        R = row['R']
        L = row['L']
        number = int(row['number'])
        nodeAC = int(row['bus'])     
        w = 2*np.pi*f
        
        # Calculate vq0 vd0
        theta0 = row['theta'] * np.pi / 180 - delta_slk
        vq0 = row['V'] * np.cos(theta0) * np.sqrt(2 / 3)
        vd0 = -row['V'] * np.sin(theta0) * np.sqrt(2 / 3)   
        
        Al = np.array([[0, -w],[w, 0]])    
        Bl = np.array([[1/L, 0],[0, 1/L]])    
        Cl = np.array([[1, 0],[0, 1]])    
        Dl = np.array([[0, 0],[0, 0]])
    
        xl = ['Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']
        ul = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']
        yl = ['Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']
        
        SS_l = ss(Al, Bl, Cl, Dl, inputs = ul, outputs = yl, states = xl)
        
        # Ar = np.empty(0)   
        # Br = np.empty((0,3))
        # Cr = np.empty((0,2))  
        Ar = np.zeros(0)   
        Br = np.empty((0,3))
        Cr = np.empty((0,2))  
        Dr = np.array([[1/R, 0, -vq0/(R**2)],[0, 1/R, -vd0/(R**2)]])
    
        ur = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd', 'NET_Rld' + str(number)]    
        yr = ['Load' + str(number) + '_irq', 'Load' + str(number) + '_ird']
        
        SS_r = ss(Ar, Br, Cr, Dr, inputs = ur, outputs = yr)
        
        Anus = np.empty(0)
        Bnus = np.empty((0, 4))
        Cnus = np.empty((0, 2))        
        Dnus = np.array([[-1, -1, 0, 0],[0, 0, -1, -1]])
    
        unus = ['Load' + str(number) + '_irq','Load' + str(number) + '_ilq', 
                'Load' + str(number) + '_ird','Load' + str(number) + '_ild']    
        ynus = ['Load' + str(number) + '_iq','Load' + str(number) + '_id']
        
        SS_nus = ss(Anus, Bnus, Cnus, Dnus, inputs = unus, outputs = ynus)       
        
        uLoad = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd', 'NET_Rld' + str(number)]
        
        if connect_fun=='interconnect':
            load = ct.interconnect([SS_l, SS_r, SS_nus], states=xl, inputs=uLoad, outputs=ynus, check_unused=False)

            if save_ss_matrices == True:
                save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0]+str(n_load))
        elif connect_fun == 'append_and_connect':
            load = interconnect.interconnect([SS_l, SS_r, SS_nus], states=xl, inputs=uLoad, outputs=ynus, check_unused=False)

            
            if save_ss_matrices == True:
                save_ss_matrices_fun(load,
                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                     f'{load=}'.split('=')[0]+str(n_load))

        return load, xl, n_load
    
    def build_Load_in_PI_R(row):
        
        R = row['R']
        number = int(row['number'])
        nodeAC = int(row['bus'])     
        
        Ar = np.empty(0)   
        Br = np.empty((0,2))
        Cr = np.empty((0,2))  
        Dr = np.array([[-1/R, 0],[0, -1/R]])
    
        ur = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']    
        yr = ['Load' + str(number) + '_irq', 'Load' + str(number) + '_ird']
        
        load = ss(Ar, Br, Cr, Dr, inputs = ur, outputs = yr)   
        
        return load
    
    
    def build_Load_in_PI(row,f, connect_fun='append_and_connect',save_ss_matrices=False):
        
        R = row['R']
        L = row['L']
        number = int(row['number'])
        nodeAC = int(row['bus'])     
        w = 2*np.pi*f
               
        Al = np.array([[0, -w],[w, 0]])    
        Bl = np.array([[1/L, 0],[0, 1/L]])    
        Cl = np.array([[1, 0],[0, 1]])    
        Dl = np.array([[0, 0],[0, 0]])
    
        xl = ['Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']
        ul = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']
        yl = ['Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']
        
        SS_l = ss(Al, Bl, Cl, Dl, inputs = ul, outputs = yl, states = xl)
        
        Ar = np.empty(0)   
        Br = np.empty((0,2))
        Cr = np.empty((0,2))  
        Dr = np.array([[1/R, 0],[0, 1/R]])
    
        ur = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']    
        yr = ['Load' + str(number) + '_irq', 'Load' + str(number) + '_ird']
        
        SS_r = ss(Ar, Br, Cr, Dr, inputs = ur, outputs = yr)   
        
        Anus = np.empty(0)
        Bnus = np.empty((0, 4))
        Cnus = np.empty((0, 2))        
        Dnus = np.array([[-1, -1, 0, 0],[0, 0, -1, -1]])
    
        unus = ['Load' + str(number) + '_irq','Load' + str(number) + '_ilq', 
                'Load' + str(number) + '_ird','Load' + str(number) + '_ild']    
        ynus = ['Load' + str(number) + '_iq','Load' + str(number) + '_id']
        
        SS_nus = ss(Anus, Bnus, Cnus, Dnus, inputs = unus, outputs = ynus)       
        
        uLoad = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']

        if connect_fun=='interconnect':
            load = ct.interconnect([SS_l, SS_r, SS_nus], states=xl, inputs=uLoad, outputs=ynus, check_unused=False)

            if save_ss_matrices == True:
                save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0])
        elif connect_fun == 'append_and_connect':
            load = interconnect.interconnect([SS_l, SS_r, SS_nus], states=xl, inputs=uLoad, outputs=ynus, check_unused=False)


            if save_ss_matrices == True:
                save_ss_matrices_fun(load,
                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                     f'{load=}'.split('=')[0])
        return load, xl
    
    
    def build_Load_in_rl_R_addR(row, Connectivity_Matrix, T_nodes, f, delta_slk, connect_fun='append_and_connect',save_ss_matrices=False):

        nodeAC = int(row['bus'])
        number = int(row['number'])
        R = row['R']
        theta0 = row['theta'] * np.pi / 180 - delta_slk
    
        Iload = row['V'] * np.sqrt(2 / 3) / R
        irq0 = Iload * np.cos(theta0)
        ird0 = -Iload * np.sin(theta0)
    
        currents = Connectivity_Matrix[nodeAC-1, :] #idx starts at 0
        unus = []
    
        for i in range(currents.size):
            bus = i+1
            if currents[i] == 1 and bus < nodeAC:
                unus.append('NET_iq_' + str(bus) + '_' + str(nodeAC))
                unus.append('NET_id_' + str(bus) + '_' + str(nodeAC))
                Dnus = np.array([[1, 0], [0, 1]])
            elif currents[i] == 1 and bus > nodeAC:
                unus.append('NET_iq_' + str(nodeAC) + '_' + str(bus))
                unus.append('NET_id_' + str(nodeAC) + '_' + str(bus))
                Dnus = np.array([[-1, 0], [0, -1]])
 
        T_nodes_row = T_nodes.loc[T_nodes['Node'] == nodeAC]
        for column in T_nodes_row.columns[1:]:
            value = T_nodes_row[column]
            if not (value.values[0] == ''):   
                match = re.match(r'([A-Za-z]+)(\d+)', value.values[0])
                element = match.group(1)
                numberb = match.group(2)
                if element == "SG":
                    unus.append('SG' + numberb + '_iq')
                    unus.append('SG' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                elif element == "TH":
                    unus.append('TH' + numberb + '_iq')
                    unus.append('TH' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))                                      
                elif element == "MMC":
                    unus.append('MMC' + numberb + '_idiffq')
                    unus.append('MMC' + numberb + '_idiffd')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                elif element == "VSC":
                    unus.append('VSC' + numberb + '_iq')
                    unus.append('VSC' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                elif element == "user":
                    unus.append('USER' + numberb + '_iq')
                    unus.append('USER' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                    
        Anus = np.empty(0)
        columns_Bin = Dnus.shape[1]
        Bnus = np.empty((0, columns_Bin))
        Cnus = np.empty((0, 2))
        ynus = ['Load'+str(number)+'_iq', 'Load'+str(number)+'_id']
        SS_nus = ss(Anus, Bnus, Cnus, Dnus, inputs=unus, outputs=ynus)
    
        Ar = np.empty(0)   
        Br = np.empty((0,3))
        Cr = np.empty((0,2))  
        Dr = np.array([[R, 0, irq0], [0, R, ird0]])
        ur = ['Load'+str(number)+'_iq', 'Load'+str(number)+'_id', 'NET_Rld'+str(number)]
        yr = ['NET_vn'+str(nodeAC)+'q', 'NET_vn'+str(nodeAC)+'d']
        SS_r = ss(Ar, Br, Cr, Dr, inputs=ur, outputs=yr)
    
        uLoad = unus + ['NET_Rld'+str(number)]
        yLoad = yr

        if connect_fun=='interconnect':
            load = ct.interconnect([SS_r, SS_nus], inputs=uLoad, outputs=yLoad, check_unused=False)

            if save_ss_matrices == True:
                save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0])
        elif connect_fun == 'append_and_connect':
            load = interconnect.interconnect([SS_r, SS_nus], inputs=uLoad, outputs=yLoad, check_unused=False)

            if save_ss_matrices == True:
                save_ss_matrices_fun(load,
                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                     f'{load=}'.split('=')[0])
        return load
        
    
    def build_Load_in_rl(row, Connectivity_Matrix, T_nodes, f, connect_fun='append_and_connect',save_ss_matrices=False):
        
        nodeAC = int(row['bus'])
        number = int(row['number'])
        R = row['R']
        L = row['L']
        w = 2*np.pi*f
        
        currents = Connectivity_Matrix[nodeAC-1, :] #idx starts at 0
        unus = []
    
        for i in range(currents.size):
            bus = i+1
            if currents[i] == 1 and bus < nodeAC:
                unus.append('NET_iq_' + str(bus) + '_' + str(nodeAC))
                unus.append('NET_id_' + str(bus) + '_' + str(nodeAC))
                Dnus = np.array([[1, 0], [0, 1]])
            elif currents[i] == 1 and bus > nodeAC:
                unus.append('NET_iq_' + str(nodeAC) + '_' + str(bus))
                unus.append('NET_id_' + str(nodeAC) + '_' + str(bus))
                Dnus = np.array([[-1, 0], [0, -1]])
 
        T_nodes_row = T_nodes.loc[T_nodes['Node'] == nodeAC]
        for column in T_nodes_row.columns[1:]:
            value = T_nodes_row[column]
            if not (value.values[0] == ''):   
                match = re.match(r'([A-Za-z]+)(\d+)', value.values[0])
                element = match.group(1)
                numberb = match.group(2)
                if element == "SG":
                    unus.append('SG' + numberb + '_iq')
                    unus.append('SG' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                elif element == "TH":
                    unus.append('TH' + numberb + '_iq')
                    unus.append('TH' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))                                    
                elif element == "MMC":
                    unus.append('MMC' + numberb + '_idiffq')
                    unus.append('MMC' + numberb + '_idiffd')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                elif element == "VSC":
                    unus.append('VSC' + numberb + '_iq')
                    unus.append('VSC' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                elif element == "user":
                    unus.append('USER' + numberb + '_iq')
                    unus.append('USER' + numberb + '_id')
                    Dnus = np.hstack((Dnus, np.array([[1, 0], [0, 1]])))
                    
        Anus = np.empty(0)
        columns_Bin = Dnus.shape[1]
        Bnus = np.empty((0, columns_Bin))
        Cnus = np.empty((0, 2))
        ynus = ['Load'+str(number)+'_iq', 'Load'+str(number)+'_id']
        SS_nus = ss(Anus, Bnus, Cnus, Dnus, inputs=unus, outputs=ynus)
        
        if L:
            Al = np.array([[0, -w],[w, 0]])    
            Bl = np.array([[1/L, 0],[0, 1/L]])    
            Cl = np.array([[1, 0],[0, 1]])    
            Dl = np.array([[0, 0],[0, 0]])
            xl = ['Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']
            ul = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']
            yl = ['Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']            
            SS_l = ss(Al, Bl, Cl, Dl, inputs = ul, outputs = yl, states = xl)
    
            Anus_rl = np.empty(0) 
            Bnus_rl = np.empty((0,4))
            Cnus_rl = np.empty((0,2))
            Dnus_rl = np.array([[1, 0, -1, 0], [0, 1, 0, -1]])
            unus_rl = ['Load'+str(number)+'_iq', 'Load'+str(number)+'_id', 'Load' + str(number) + '_ilq', 'Load' + str(number) + '_ild']
            ynus_rl = ['Load' + str(number) + '_irq', 'Load' + str(number) + '_ird']
            SS_nus_rl = ss(Anus_rl, Bnus_rl, Cnus_rl, Dnus_rl, inputs=unus_rl, outputs=ynus_rl)
    
            Ar = np.empty(0)   
            Br = np.empty((0,2))
            Cr = np.empty((0,2)) 
            Dr = R * np.array([[1, 0], [0, 1]])
            ur = ['Load' + str(number) + '_irq', 'Load' + str(number) + '_ird']              
            yr = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']
            SS_r = ss(Ar, Br, Cr, Dr, inputs=ur, outputs=yr)
    
            uLoad = unus
            yLoad = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']
            if connect_fun == 'interconnect':
                load = ct.interconnect([SS_r, SS_nus_rl, SS_l, SS_nus], states=xl, inputs=uLoad, outputs=yLoad)

                if save_ss_matrices == True:
                    save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0])
            elif connect_fun == 'append_and_connect':
                load = interconnect.interconnect([SS_r, SS_nus_rl, SS_l, SS_nus], states=xl, inputs=uLoad, outputs=yLoad)

                if save_ss_matrices == True:
                    save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0])


        else:
            Ar = np.empty(0)   
            Br = np.empty((0,2))
            Cr = np.empty((0,2))  
            Dr = R * np.array([[1, 0], [0, 1]])
            ur = ['Load'+str(number)+'_iq', 'Load'+str(number)+'_id']   
            yr = ['NET_vn' + str(nodeAC) + 'q', 'NET_vn' + str(nodeAC) + 'd']
            SS_r = ss(Ar, Br, Cr, Dr, inputs=ur, outputs=yr)
    
            xl = []
            uLoad = unus
            yLoad = yr

            if connect_fun == 'interconnect':
                load = ct.interconnect([SS_r, SS_nus], inputs=uLoad, outputs=yLoad)

                if save_ss_matrices == True:
                    save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0])
            elif connect_fun == 'append_and_connect':
                load = interconnect.interconnect([SS_r, SS_nus], inputs=uLoad, outputs=yLoad)

                if save_ss_matrices == True:
                    save_ss_matrices_fun(load,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{load=}'.split('=')[0])


        return load, xl
    
    
    # Call the appropiate function according to the load type
    n_load=0
    for _,row in T_load.iterrows():
        
        bus = row['bus']
        L = row['L']
        
        if bus <= connect_mtx_PI.shape[0] and connect_mtx_PI[bus-1, :].sum() > 0:  # Load is connected to any PI-line
            if L == 0: # R Load
                #load = build_Load_in_PI_R(row) # R is CONSTANT 
                load = build_Load_in_PI_R_addR(row,delta_slk) # R is INPUT 
                l_blocks.append(load)
            else: # RL load
                #load, states = build_Load_in_PI(row,f) # R is CONSTANT
                load, states, n_load= build_Load_in_PI_addR(row,f,delta_slk, connect_fun, save_ss_matrices, n_load) # R is INPUT
                l_blocks.append(load)
                l_states.extend(states)
                
        else: # Load is connected to all RL-lines
            if L == 0: # R Load
                load = build_Load_in_rl_R_addR(row, connect_mtx_rl, T_nodes, f, delta_slk, connect_fun,save_ss_matrices) # R is INPUT
                l_blocks.append(load)
            else:  # R or RL Load
                load, states = build_Load_in_rl(row, connect_mtx_rl, T_nodes, f, connect_fun,save_ss_matrices) # R is CONSTANT
                l_blocks.append(load)
                if states:
                    l_states.extend(states)
   
        n_load=n_load+1

    return l_blocks, l_states

# %% DC NET

def generate_DC_NET(T_DC_NET, l_blocks, l_states):
    
    if not T_DC_NET.empty:
        raise RuntimeError("DC grid SS not implemented yet")        
    
    return l_blocks, l_states
