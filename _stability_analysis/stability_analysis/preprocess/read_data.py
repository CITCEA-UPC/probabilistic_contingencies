import pandas as pd
 
def read_sys_data(excel_sys):
    
    
    """
    Reads all the grid data from the main excel file and creates the system components
    
    :param excel_sys: .xlsx file path with multiple sheets
    :return: a separate DataFrame for each grid component
    """        
    T_global = pd.read_excel(excel_sys, sheet_name='global')
    T_global_DC = pd.read_excel(excel_sys, sheet_name='global_DC')
    T_NET = pd.read_excel(excel_sys, sheet_name='AC-NET') 
    T_DC_NET = pd.read_excel(excel_sys, sheet_name='DC-NET') 
    T_trafo = pd.read_excel(excel_sys, sheet_name='trafo')  
    T_load = pd.read_excel(excel_sys, sheet_name='load')  
    T_TH = pd.read_excel(excel_sys, sheet_name='TH')
    T_shunt = pd.read_excel(excel_sys, sheet_name='SHUNT')
    T_SG = pd.read_excel(excel_sys, sheet_name='SG')  
    T_VSC = pd.read_excel(excel_sys, sheet_name='VSC')  
    T_MMC = pd.read_excel(excel_sys, sheet_name='MMC')  
    T_b2b = pd.read_excel(excel_sys, sheet_name='b2b')  
    T_user = pd.read_excel(excel_sys, sheet_name='user') 
    T_case = pd.read_excel(excel_sys, sheet_name='CASE') 
    T_buses = pd.read_excel(excel_sys, sheet_name='PF') 
    try:
        T_gen = pd.read_excel(excel_sys, sheet_name='Gen') 
    except:
        pass
    T_IPC = pd.read_excel(excel_sys, sheet_name='IPC') 
    T_sim = pd.read_excel(excel_sys, sheet_name='sim') 
    
    T_global = T_global.rename(columns=lambda x: x.strip())
    T_global_DC = T_global_DC.rename(columns=lambda x: x.strip())
    T_NET = T_NET.rename(columns=lambda x: x.strip())
    T_DC_NET = T_DC_NET.rename(columns=lambda x: x.strip())
    T_trafo = T_trafo.rename(columns=lambda x: x.strip())  
    T_load = T_load.rename(columns=lambda x: x.strip()) 
    T_TH = T_TH.rename(columns=lambda x: x.strip()) 
    T_shunt = T_shunt.rename(columns=lambda x: x.strip())     
    T_SG = T_SG.rename(columns=lambda x: x.strip())
    T_VSC = T_VSC.rename(columns=lambda x: x.strip()) 
    T_MMC = T_MMC.rename(columns=lambda x: x.strip())  
    T_b2b = T_b2b.rename(columns=lambda x: x.strip())
    T_user = T_user.rename(columns=lambda x: x.strip()) 
    T_case = T_case.rename(columns=lambda x: x.strip()) 
    T_buses = T_buses.rename(columns=lambda x: x.strip()) 
    try:
        T_gen = T_gen.rename(columns=lambda x: x.strip()) 
    except:
        pass
    T_IPC = T_IPC.rename(columns=lambda x: x.strip()) 
    T_sim = T_sim.rename(columns=lambda x: x.strip()) 

    # Create copies of original tables 
    T_NET_0 = T_NET.copy()
    T_DC_NET_0 = T_DC_NET.copy()
    T_trafo_0 = T_trafo.copy()
    T_load_0 = T_load.copy()
    T_TH_0 = T_TH.copy()
    T_SG_0 = T_SG.copy()
    T_VSC_0 = T_VSC.copy()
    T_MMC_0 = T_MMC.copy()
    T_user_0 = T_user.copy()
    T_gen_0 = T_gen.copy()
    
    try:
        grid = {
        'T_global': T_global,
        'T_global_DC': T_global_DC,
        'T_NET': T_NET,
        'T_DC_NET': T_DC_NET,
        'T_trafo': T_trafo,
        'T_load': T_load,
        'T_TH': T_TH,
        'T_shunt': T_shunt,
        'T_SG': T_SG,
        'T_VSC': T_VSC,
        'T_MMC': T_MMC,
        'T_IPC': T_IPC,
        'T_b2b': T_b2b,
        'T_user': T_user,
        'T_gen': T_gen,
        'T_case': T_case,
        'T_buses': T_buses,
        'gen_names': ['TH','SG','VSC','MMC','user'] #list of generator types d_gen = {'SG': T_SG, ...} 
        }
    except:    
    
        grid = {
        'T_global': T_global,
        'T_global_DC': T_global_DC,
        'T_NET': T_NET,
        'T_DC_NET': T_DC_NET,
        'T_trafo': T_trafo,
        'T_load': T_load,
        'T_TH': T_TH,
        'T_shunt': T_shunt,
        'T_SG': T_SG,
        'T_VSC': T_VSC,
        'T_MMC': T_MMC,
        'T_IPC': T_IPC,
        'T_b2b': T_b2b,
        'T_user': T_user,
        'T_gen': T_gen,
        'T_case': T_case,
        'T_buses': T_buses,
        'gen_names': ['TH','SG','VSC','MMC','user'] #list of generator types d_gen = {'SG': T_SG, ...} 
        }
    
    grid_0 = {
    'T_NET_0': T_NET_0,
    'T_DC_NET_0': T_DC_NET_0,
    'T_trafo_0': T_trafo_0,
    'T_load_0': T_load_0,
    'T_TH_0': T_TH_0,
    'T_SG_0': T_SG_0,
    'T_VSC_0': T_VSC_0,
    'T_MMC_0': T_MMC_0,
    'T_user_0': T_user_0,
    'T_gen_0': T_gen_0
    }
        
    return grid, grid_0


def get_simParam(excel_sys):
    """
    Reads all the simulation configuration parameters from the main excel file 
    
    :param excel_sys: .xlsx file path with multiple sheets
    :return: a dictionary of the simulation configuration parameters
    """
    sheets = pd.ExcelFile(excel_sys).sheet_names
    sim_config = {}
    if 'sim' in sheets:
        T_sim = pd.read_excel(excel_sys, sheet_name='sim')    
        sim_config['Type'] = T_sim.loc[0, 'Type']
        sim_config['Ts'] = T_sim.loc[0, 'Ts_s']
        sim_config['Tsim'] = T_sim.loc[0, 'Tsim_s']
        sim_config['solver'] = T_sim.loc[0, 'solver']
        sim_config['tstep'] = T_sim.loc[0, 'tstep_s']
        sim_config['Tsample'] = T_sim.loc[0, 'Tsample_s']
        sim_config['DR'] = T_sim.loc[0, 'step_factor']
    return sim_config

# =============================================================================
# THIS TO BE DELETED ONCE OLD T_MMC NAMES & T_STATCOM HAVE BEEN REPLACED IN OLD SCRIPTS 
# =============================================================================
def tempTables(grid):
    grid['T_MMC_Pac_GFll'] = grid['T_MMC'].copy()
    grid['T_MMC_Vdc_GFll'] = grid['T_MMC'].copy()
    grid['T_STATCOM'] = grid['T_VSC'].copy()        
    return grid

#%%

def read_data(file_path):
    # Create an empty dictionary to store DataFrames
    d_op = {}

    # Read the Excel file with multiple sheets
    xl = pd.ExcelFile(file_path)

    # Loop through each sheet in the Excel file
    for sheet_name in xl.sheet_names:
        # Read each sheet as a DataFrame
        df = xl.parse(sheet_name)
        
        # Store the DataFrame in the dictionary with sheet name as key
        d_op[sheet_name] = df

    return d_op

