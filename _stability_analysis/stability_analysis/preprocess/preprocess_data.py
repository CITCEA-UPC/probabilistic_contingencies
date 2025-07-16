# =============================================================================
# ARRANGE INPUT DATA TO APPROPRIATE FORMAT

# Write the necessary code to adapt input raw data to SS_TOOL excel format
# ...

# Ensure bus_from < bus_to
# Ensure only one line between two buses
# Compute values of loads
# =============================================================================

import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
import numpy as np

def preprocess_raw(d_raw_data):
    
    # Assign new values of AREA  
    # Get the unique values of 'BASKV'
    unique_baskv = d_raw_data['results_bus']['BASKV'].unique()
    # Create a dictionary to map 'BASKV' to 'AREA'
    baskv_to_area = {baskv: i + 1 for i, baskv in enumerate(unique_baskv)}
    # Update the 'AREA' column based on the mapping
    d_raw_data['results_bus']['AREA'] = d_raw_data['results_bus']['BASKV'].map(baskv_to_area)
    
    for name, df in d_raw_data.items():
        
        match name:
            
            case "data_global":
            # Ensure each area defines a voltage zone   
                # Define default values for the columns
                default_values = {
                    'BASKV': df['BASKV'][0],
                    'Sb_MVA': df['Sb_MVA'][0],
                    'SyncArea': df['SyncArea'][0],
                    'f_Hz': df['f_Hz'][0],
                    'ref_bus': df['ref_bus'][0],
                    'ref_element': 'UNDEFINED'}        
                       
                unique_area_baskv = d_raw_data['results_bus'][['AREA', 'BASKV']].drop_duplicates()
                                
                # Merge the two DataFrames based on 'AREA' column to match 'BASKV' values
                df = df.merge(unique_area_baskv, on='AREA', how = 'right')                
                # Drop the redundant 'BASKV_y' column and rename 'BASKV_x' to 'BASKV'
                df['BASKV_x'] = df['BASKV_y']
                df = df.drop(columns=['BASKV_y']).rename(columns={'BASKV_x': 'BASKV'})             
                
                
                df.reset_index(drop=True, inplace=True)               
                df.fillna(default_values, inplace=True)  # Assign default values to the NaN cells
                df['ref_bus'] = df['ref_bus'].astype(int)
                d_raw_data[name] = df
                                
            case "results_bus":
                pass
            
            case "branch":
                # Ensure bus_from < bus_to               
                df = reorder_buses_lines_raw(df)                
                # Ensure only one line between two buses
                d_raw_data[name] = remove_parallel_lines_raw(df)
                
            case "load":          
                # Merge the two tables based on the 'I' column
                merged_table = df.merge(d_raw_data['results_bus'][['I', 'AREA']], on='I', how='left')              
                # Update the 'AREA' column in the 'generators' table
                df['AREA'] = merged_table['AREA_y']        
                
                # Power in pu                                
                df_expanded = df.merge(d_raw_data['data_global'][['AREA','Sb_MVA']], on='AREA', how='left')                
                #df['P'] = df_expanded[['PL', 'IP', 'YP']].loc[:,(df_expanded != 0).all()]
                #df['Q'] = df_expanded[['QL', 'IQ', 'YQ']].loc[:,(df_expanded != 0).all()]
                df['P'] = np.where(df_expanded['PL'] != 0, df_expanded['PL'],
                                   np.where(df_expanded['IP'] != 0, df_expanded['IP'],
                                            df_expanded['YP']))
                df['Q'] = np.where(df_expanded['QL'] != 0, df_expanded['QL'],
                                   np.where(df_expanded['IQ'] != 0, df_expanded['IQ'],
                                            df_expanded['YQ']))
                
                df['P'] = df['P']/df_expanded['Sb_MVA']
                df['Q'] = df['Q']/df_expanded['Sb_MVA']
                    
                conditions_P = [
                    (df['PL'] != 0),
                    (df['IP'] != 0),
                    (df['YP'] != 0)]
                conditions_Q = [
                    (df['QL'] != 0),
                    (df['IQ'] != 0),
                    (df['YQ'] != 0)]
                
                choices_P = ['P','I','Z']
                choices_Q = ['Q','I','Z']
                
                R = pd.Series(np.select(conditions_P, choices_P, default='ZZ'), dtype='string')
                X = pd.Series(np.select(conditions_Q, choices_Q, default='ZZ'), dtype='string')
                
                df['type'] = R+X                
                d_raw_data[name] = df
                
            case "generator":
                # Merge the two tables based on the 'I' column
                merged_table = df.merge(d_raw_data['results_bus'][['I', 'AREA','BASKV']], on='I', how='left')              
                # Update the 'AREA' column in the 'generators' table
                df['AREA'] = merged_table['AREA_y']
                df['BASKV'] = merged_table['BASKV']
                d_raw_data[name] = df
                
            case "trafo":
                # Ensure bus_from < bus_to               
                df = reorder_buses_lines_raw(df)                
                # Ensure only one line between two buses
                d_raw_data[name] = remove_parallel_trafos_raw(df)
                
            case _ :
                print("DataFrame name not recognised")
                
    # Check for parallel lines and trafos
    d_raw_data = remove_parallel_lines_and_trafos_raw(d_raw_data)
            

    




def reorder_buses_lines_raw(df):
    # Create a boolean mask for the condition 'I' > 'J'               
    mask = df['I'] > df['J']                    
    # Swap the values in 'I' and 'J' columns where the condition is True
    temp = df.loc[mask, 'I'].copy()
    df.loc[mask, 'I'] = df.loc[mask, 'J']
    df.loc[mask, 'J'] = temp     
    return df

def reorder_buses_lines(df):
    # Create a boolean mask for the condition 'I' > 'J'               
    mask = df['bus_from'] > df['bus_to']                    
    # Swap the values in 'I' and 'J' columns where the condition is True
    temp = df.loc[mask, 'bus_from'].copy()
    df.loc[mask, 'bus_from'] = df.loc[mask, 'bus_to']
    df.loc[mask, 'bus_to'] = temp     
    return df


def remove_parallel_lines_raw(df):
    # Find rows with duplicate 'I' and 'J' values
    duplicate_groups = df[df.duplicated(['I', 'J'], keep=False)].groupby(['I', 'J'])
    
    # Iterate over the duplicate groups
    for group, group_df in duplicate_groups:
        i, j = group
        
        # Calculate the equivalent values for 'R', 'X', and 'B'
        r_values = group_df['R'].values
        x_values = group_df['X'].values
        b_values = group_df['B'].values
        
        # Calculate the equivalent values using the parallel combination formula
        z_values = r_values + 1j * x_values
        equivalent_z = 1 / np.sum(1 / z_values)
        equivalent_r = np.real(equivalent_z)
        equivalent_x = np.imag(equivalent_z)
        equivalent_b = sum(b_values)
        
        # Update the original rows of the group with the new values
        df.loc[(df['I'] == i) & (df['J'] == j), ['R', 'X', 'B']] = equivalent_r, equivalent_x, equivalent_b
    
    # Drop duplicate rows based on 'I' and 'J' columns, keeping the first occurrence
    df = df.drop_duplicates(subset=['I', 'J'], keep='first')
    # Reset the indices
    df.reset_index(drop=True, inplace=True)
    return df


def remove_parallel_trafos_raw(df):
    # Find rows with duplicate 'I' and 'J' values
    duplicate_groups = df[df.duplicated(['I', 'J'], keep=False)].groupby(['I', 'J'])
    
    # Iterate over the duplicate groups
    for group, group_df in duplicate_groups:
        i, j = group
        
        # Calculate the equivalent values for 'R', 'X'
        r_values = group_df['R12'].values
        x_values = group_df['X12'].values
        
        # Calculate the equivalent values using the parallel combination formula
        z_values = r_values + 1j * x_values
        equivalent_z = 1 / np.sum(1 / z_values)
        equivalent_r = np.real(equivalent_z)
        equivalent_x = np.imag(equivalent_z)
        
        # Update the original rows of the group with the new values
        df.loc[(df['I'] == i) & (df['J'] == j), ['R12', 'X12']] = equivalent_r, equivalent_x
    
    # Drop duplicate rows based on 'I' and 'J' columns, keeping the first occurrence
    df = df.drop_duplicates(subset=['I', 'J'], keep='first')
    # Reset the indices
    df.reset_index(drop=True, inplace=True)
    return df


def remove_parallel_lines(df):
    # Find rows with duplicate 'I' and 'J' values
    duplicate_groups = df[df.duplicated(['bus_from', 'bus_to'], keep=False)].groupby(['bus_from', 'bus_to'])
    
    # Iterate over the duplicate groups
    for group, group_df in duplicate_groups:
        i, j = group
        
        # Calculate the equivalent values for 'R', 'X', and 'B'
        r_values = group_df['R'].values
        x_values = group_df['X'].values
        b_values = group_df['B'].values
        
        # Calculate the equivalent values using the parallel combination formula
        z_values = r_values + 1j * x_values
        equivalent_z = 1 / np.sum(1 / z_values)
        equivalent_r = np.real(equivalent_z)
        equivalent_x = np.imag(equivalent_z)
        equivalent_b = sum(b_values)
        
        # Update the original rows of the group with the new values
        df.loc[(df['bus_from'] == i) & (df['bus_to'] == j), ['R', 'X', 'B']] = equivalent_r, equivalent_x, equivalent_b
    
    # Drop duplicate rows based on 'I' and 'J' columns, keeping the first occurrence
    df = df.drop_duplicates(subset=['bus_from', 'bus_to'], keep='first')
    # Reset the indices
    df.reset_index(drop=True, inplace=True)
    return df


def remove_parallel_lines_and_trafos_raw(df):
    
    # Find parallel lines and trafos
    df_lines = pd.concat([df['branch'][['I','J','R','X']], df['trafo'][['I','J','R12','X12']]], ignore_index = True)
    duplicate_groups = df_lines[df_lines.duplicated(['I', 'J'], keep=False)].groupby(['I', 'J'])
    
    # Iterate over the duplicate groups
    for group, group_df in duplicate_groups:
        
        if len(group) > 2:
            print(f"Warning: There are {len(group)} lines and trafos in parallel:")
            print(group_df)
            
        else:            
            i, j = group   
            
            # We'll keep the line and remove the trafo
            
            # Calculate the equivalent values for 'R', 'X'
            r_values = group_df['R12'].values
            mask = ~np.isnan(r_values)
            r_values = r_values[mask]                    
            
            x_values = group_df['X12'].values  
            mask = ~np.isnan(x_values)
            x_values = x_values[mask] 
            
            # Calculate the equivalent values using the parallel combination formula
            z_values = r_values + 1j * x_values
            equivalent_z = 1 / np.sum(1 / z_values)
            equivalent_r = np.real(equivalent_z)
            equivalent_x = np.imag(equivalent_z)  
            
            # Update the original rows of the group with the new values
            df["branch"].loc[(df["branch"]['I'] == i) & (df["branch"]['J'] == j), ['R', 'X']] = equivalent_r, equivalent_x
    
            # Drop the parallel trafo
            df["trafo"].drop(df["trafo"].loc[(df["trafo"]['I'] == i) & (df["trafo"]['J'] == j)].index, inplace = True)
            # Reset the indices
            df["trafo"].reset_index(drop=True, inplace=True)
    
    return df            
            

def rename_nodes():
    """
    Re-name nodes to have consecutive numbers (not implemented yet)
    It is not necessary for the code to work, but optimizes the size of the connectivity-matrix
    """
    pass

def raw2excel(d_raw_data,excel_raw):
    
    with pd.ExcelWriter(excel_raw) as writer: 
        for name, df in d_raw_data.items():        
            df.to_excel(writer, sheet_name=name, header=True, index=False)       

    print("WARNING: You should now create the MAIN excel file from RAW excel file")
    print(f"RAW excel file is found in: {excel_raw}") 
    print("MAIN excel file should be created in: /tool/data/cases/")              
         
    
def buses_as_int(d_grid):
    
    d_grid['T_NET']['bus_from'] = d_grid['T_NET']['bus_from'].astype(int)
    d_grid['T_NET']['bus_to'] = d_grid['T_NET']['bus_to'].astype(int)
    
    d_grid['T_DC_NET']['bus_from'] = d_grid['T_DC_NET']['bus_from'].astype(int)
    d_grid['T_DC_NET']['bus_to'] = d_grid['T_DC_NET']['bus_to'].astype(int)
    
    d_grid['T_trafo']['bus_from'] = d_grid['T_trafo']['bus_from'].astype(int)
    d_grid['T_trafo']['bus_to'] = d_grid['T_trafo']['bus_to'].astype(int)
    
    d_grid['T_load']['bus'] = d_grid['T_load']['bus'].astype(int)
    
    d_grid['T_TH']['bus'] = d_grid['T_TH']['bus'].astype(int)
    
    d_grid['T_SG']['bus'] = d_grid['T_SG']['bus'].astype(int)
    
    d_grid['T_VSC']['bus'] = d_grid['T_VSC']['bus'].astype(int)
    
    d_grid['T_MMC']['bus'] = d_grid['T_MMC']['bus'].astype(int)
    d_grid['T_MMC']['NodeAC'] = d_grid['T_MMC']['NodeAC'].astype(int)
    d_grid['T_MMC']['NodeDC'] = d_grid['T_MMC']['NodeDC'].astype(int)
    
    d_grid['T_b2b']['bus1'] = d_grid['T_b2b']['bus1'].astype(int)
    d_grid['T_b2b']['bus2'] = d_grid['T_b2b']['bus2'].astype(int)
    
    d_grid['T_user']['bus'] = d_grid['T_user']['bus'].astype(int)

    d_grid['T_buses']['bus'] = d_grid['T_buses']['bus'].astype(int)
    
    d_grid['T_case']['bus'] = d_grid['T_case']['bus'].astype(int)
    
    return d_grid
    