import pandas as pd
import numpy as np
import random

def generated_operating_point(case,d_raw_data, d_op): #GridCal_grid
    
    d_raw_data=assign_loads_to_d_raw_data(d_raw_data, case)
        
    d_raw_data=assign_gens_to_d_raw_data(d_raw_data, case)
        
    d_raw_data, d_op = assign_GFOL_GFOR(d_raw_data, d_op, case)
    
    d_raw_data = alphas_P(d_raw_data)
    
    return d_raw_data, d_op


def assign_loads_to_d_raw_data(d_raw_data,case):
    
    case_lables=case.index
    active_power=[p for p in case_lables if p.startswith('p_load')]
    reactive_power=[q for q in case_lables if q.startswith('q_load')]
    
    d_raw_data['load']['PL']= np.array(case[active_power])
    d_raw_data['load']['QL']= np.array(case[reactive_power])
    
    d_raw_data['load']['P']=d_raw_data['load']['PL']/100
    d_raw_data['load']['Q']=d_raw_data['load']['QL']/100
   
    return d_raw_data

def assign_gens_to_d_raw_data(d_raw_data, case):
   
    case_lables=case.index

    active_power_sg=[p for p in case_lables if p.startswith('p_sg')]
    reactive_power_sg=[q for q in case_lables if q.startswith('q_sg')]
    
    active_power_cig=[p for p in case_lables if p.startswith('p_cig')]
    reactive_power_cig=[q for q in case_lables if q.startswith('q_cig')]
   
    d_raw_data['generator']['PG']=np.array(case[active_power_sg])+np.array(case[active_power_cig])
    d_raw_data['generator']['QG']=np.array(case[reactive_power_sg])+np.array(case[reactive_power_cig])
    
    d_raw_data['generator']['P_CIG']=np.array(case[active_power_cig])
    d_raw_data['generator']['P_SG']=np.array(case[active_power_sg])
        
    return d_raw_data


def assign_GFOL_GFOR(d_raw_data, d_op, case): #GridCal_grid
                    
    # buses=GridCal_grid.get_buses()
    # for bus in buses:
    #     if bus.determine_bus_type()._value_ == 3 :
            
    #         slack_bus_name=bus._name
    #         break
    
    case_lables=case.index

    active_power_gfor=[p for p in case_lables if p.startswith('p_g_for')]
    reactive_power_gfor=[q for q in case_lables if q.startswith('q_g_for')]
    
    active_power_gfol=[p for p in case_lables if p.startswith('p_g_fol')]
    reactive_power_gfol=[q for q in case_lables if q.startswith('q_g_fol')]

    active_power_cig=[p for p in case_lables if p.startswith('p_cig')]

    d_raw_data['generator']['P_GFOR']= np.array(case[active_power_gfor])
    d_op['Generators']['Snom_GFOR']= d_op['Generators']['Snom_CIG']*np.array(case[active_power_gfor])/np.array(case[active_power_cig])
    
    no_gfor=np.where(np.array(case[active_power_gfor])==0)
    d_op['Generators']['Snom_GFOR'].iloc[no_gfor]=0
    
    d_raw_data['generator']['P_GFOL']=np.array(case[active_power_gfol])
    d_op['Generators']['Snom_GFOL']= d_op['Generators']['Snom_CIG']*np.array(case[active_power_gfol])/np.array(case[active_power_cig])
    
    no_gfol=np.where(np.array(case[active_power_gfol])==0)
    d_op['Generators']['Snom_GFOL'].iloc[no_gfol]=0
    
    return d_raw_data, d_op

def alphas_P(d_raw_data):
    for el in ['SG','GFOR','GFOL']:
        
        for i in range(len(d_raw_data['generator'])):
            
            if np.any(d_raw_data['generator'].loc[i,'PG']==0):
                
                d_raw_data['generator'].loc[i,'alpha_P_'+el]=0
            else:
                d_raw_data['generator'].loc[i,'alpha_P_'+el]=d_raw_data['generator'].loc[i,'P_'+el]/d_raw_data['generator'].loc[i,'PG']
            
    return d_raw_data
            


   
    
    
    