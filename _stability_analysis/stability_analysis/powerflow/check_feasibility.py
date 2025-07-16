import pandas as pd
import numpy as np

def check_violations(d_pf, d_op, n_pf=0,
                     Bus_voltage_violation=pd.DataFrame(),
                     Gen_Q_Min_limit_violation=pd.DataFrame(),
                     Gen_Q_Max_limit_violation=pd.DataFrame(),
                     Gen_pf_violation=pd.DataFrame(),
                     Gen_pf_above095=pd.DataFrame(),
                     Gen_V_violation=pd.DataFrame()
                     ):
    
    Bus_pf= d_pf['pf_bus']
    Gen_pf=d_pf['pf_gen'].copy(deep=True).sort_values(by='bus').reset_index(drop=True)
    Gen_pf['Qmin']=d_op['Generators']['Qmin']/100
    Gen_pf['Qmax']=d_op['Generators']['Qmax']/100
    Gen_pf['Pmin']=d_op['Generators']['Pmin']/100
    Gen_pf['Pmax']=d_op['Generators']['Pmax']/100

    Bus_voltage_violation=check_min_max_violation(Bus_voltage_violation, Bus_pf['Vm'], Bus_pf['bus'], 0.9, 1.1, n_pf)
    Gen_Q_Min_limit_violation=check_min_violation_Qgen(Gen_Q_Min_limit_violation, Gen_pf['bus'], Gen_pf['Q'],Gen_pf['Qmin'], n_pf)
    Gen_Q_Max_limit_violation=check_max_violation_Qgen(Gen_Q_Max_limit_violation, Gen_pf['bus'], Gen_pf['Q'], Gen_pf['Qmax'], n_pf)
    
    Gen_pf['pf']=np.cos(np.arctan(Gen_pf['Q']/Gen_pf['P']))
    Gen_pf_violation=check_min_max_violation(Gen_pf_violation,Gen_pf['pf'],Gen_pf['bus'], 0.94999, 1, n_pf)
    Gen_pf_above095=check_good_cosphi_gen(Gen_pf_above095,Gen_pf['pf'],Gen_pf['bus'], 0.94999,n_pf)
    try:
        buses=list(Gen_pf_violation['GenBus'])
        Gen_pf_violation['P_p_u']= np.array(Gen_pf.query('bus==@buses')['P'])*100/np.array(d_op['Generators'].query('BusNum == @buses')['Pmax'])
        Gen_V_violation=check_min_max_violation(Gen_V_violation,Gen_pf['Vm'], Gen_pf['bus'],  0.95, 1.05, n_pf)

    except:    
        Gen_V_violation=check_min_max_violation(Gen_V_violation,Gen_pf['Vm'], Gen_pf['bus'],  0.95, 1.05, n_pf)

    
    buses=list(Gen_pf_above095['GenBus'])
    Gen_pf_above095['P_p_u']= np.array(Gen_pf.query('bus==@buses')['P'])*100/np.array(d_op['Generators'].query('BusNum == @buses')['Pmax'])

    return Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095


def check_min_max_violation(df,data,bus,min_val,max_val,n_pf=0):
    
    i=0
    df_row=pd.DataFrame()
    if any(data<min_val) or any(data>max_val):
        violations=list(np.where(data<min_val)[0])+list(np.where(data>max_val)[0])
        df_row.loc[0:len(violations),'GenBus']=list(np.array(bus)[violations])
        
        df_row.loc[i:i+len(violations),'Val']=list(np.array(data)[violations])
        df_row.loc[i:i+len(violations),'PF']=n_pf
        
    df=pd.concat([df,df_row],axis=0)
            
    return df

def check_good_cosphi_gen(df,data,bus,min_val,n_pf=0):
    
    i=0
    df_row=pd.DataFrame()
    if any(data>=min_val):
        violations=list(np.where(data>=min_val)[0])
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


