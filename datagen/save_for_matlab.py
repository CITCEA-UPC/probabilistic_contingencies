#%%
# Define the path to the folder
folder_path = './Fecamp Test Case - SSTool/01_data/cases/NREL_seed'+str(seed)

# Create the folder if it doesn't exist
os.makedirs(folder_path, exist_ok=True)

T_PF=d_opf['pf_bus'][['bus','Vm','theta']]
with pd.ExcelWriter(folder_path+'/IEEE118_FULL.xlsx', engine='openpyxl') as writer:
    for key in d_grid:
        if key!='gen_names':
            if key=='T_NET':
                d_grid[key].to_excel(writer, sheet_name='AC-NET', index=False)
            elif key=='T_DC_NET':
                d_grid[key].to_excel(writer, sheet_name='DC-NET', index=False)
            else:
                d_grid[key].to_excel(writer, sheet_name=key.replace('T_',''), index=False)
    T_PF.to_excel(writer, sheet_name='PF', index=False)            
    
    
with pd.ExcelWriter(folder_path+'/IEEE118_FULL_data_vsc.xlsx', engine='openpyxl') as writer:
    for mode in ['GFOR','GFOL']:
        try:
            T_VSC_data=d_grid['T_VSC'].query('mode ==@mode')[['number','bus']+list(set(d_vsc['User'+mode].columns)-set(['Bac', 'tau_s']))]
            T_VSC_data['Bac']=d_vsc['User'+mode].loc[0,'Bac']
            T_VSC_data['tau_s']=d_vsc['User'+mode].loc[0,'tau_s']
        except: 
              T_VSC_data=pd.DataFrame(columns=['number','bus']+list(d_vsc['User'+mode].columns))
        T_VSC_data.to_excel(writer, sheet_name=mode, index=False)         
              