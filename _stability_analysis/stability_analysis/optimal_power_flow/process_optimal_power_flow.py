import numpy as np
import pandas as pd

def update_OP(GridCal_grid, d_opf_results, d_raw_data):
    df_opf_bus = pd.DataFrame(
        {'bus': d_raw_data['results_bus']['I'], 'Vm': d_opf_results.Vm, 'theta': d_opf_results.Va*180/np.pi, 'P':d_opf_results.S.real, 'Q': d_opf_results.S.imag})
    
    df_opf_gen_pre = pd.DataFrame(
        {'bus': d_raw_data['generator']['I'], 'P': d_opf_results.Pg, 'Q': d_opf_results.Qg})
    df_opf_gen = pd.merge(df_opf_gen_pre, df_opf_bus[['bus', 'Vm', 'theta']], on='bus', how='left')
    df_opf_gen['cosphi']=np.cos(np.arctan(df_opf_gen['Q']/df_opf_gen['P']))
    df_opf_gen['Region']=d_raw_data['generator']['Region']
    df_opf_gen['convergence']=d_opf_results.converged
    df_opf_gen['N_iter']= d_opf_results.iterations   
    df_opf_gen['Error']= d_opf_results.error   
    
    df_opf_lines= pd.DataFrame(d_opf_results.loading)
    df_opf_lines.columns=['loading']
    
    d_opf_load= pd.DataFrame({
        'bus': d_raw_data['load']['I'], 'P': d_raw_data['load']['P'],'Q': d_raw_data['load']['Q']})
    d_opf_load= pd.merge(d_opf_load, df_opf_bus[['bus', 'Vm', 'theta']], on='bus', how='left')

    d_opf = {'pf_bus': df_opf_bus, 'pf_gen': df_opf_gen,'pf_load': d_opf_load,'pf_lines':df_opf_lines} 
    return d_opf
