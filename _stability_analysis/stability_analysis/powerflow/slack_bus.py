import numpy as np
import pandas as pd

def delta_slk(d_grid):
    
    T_global = d_grid['T_global']

    # Variable name for w_slack (ref)
    REF_w = 'REF_w'
    
    # Find slack bus
    for idx, row in T_global.iterrows():
       
        element_slk = row.ref_element
        bus_slk = row.ref_bus
        
        if element_slk == 'TH':
            num_slk = 0
            delta_slk = 0
            
        elif element_slk == 'SG':
            T_SG = d_grid['T_SG']
            num_slk = T_SG.loc[T_SG['bus'] == bus_slk, 'number'].values[0]
            T_XX = T_SG.loc[T_SG['bus'] == bus_slk, :]
            delta_slk = sg_slack(T_XX, row.Sb)
            
        elif element_slk == 'GFOR':
            T_VSC = d_grid['T_VSC']
            num_slk = T_VSC.loc[(T_VSC['bus'] == bus_slk) & (T_VSC['mode'] == 'GFOR'), 'number'].values[0]
            T_XX = T_VSC.loc[T_VSC['bus'] == bus_slk,:]
            delta_slk = gfor_slack(T_XX, row.Sb)
                 
        elif element_slk == 'user':
            T_user = d_grid['T_user']
            num_slk = T_user.loc[T_user['bus'] == bus_slk, 'number'].values[0]
            T_XX = T_user.loc[T_user['bus'] == bus_slk,:]
            elementName = T_XX['element']
            # delta_slk =  WRITE YOUR OWN CODE
            
        else:
            print('Could not find reference bus')
            
        T_global.at[idx,'num_slk'] = int(num_slk)
        T_global.at[idx,'delta_slk'] = delta_slk   
        d_grid['T_global'] = T_global
       
    return d_grid, REF_w, T_global.at[0,'num_slk'] , T_global.at[0,'delta_slk'] # Only one slack bus 



def sg_slack(T_XX, Sb):
    
    Ssg = T_XX['Sb'].values[0]  # SG rated power, SG power base

    # Data from the power-flow
    Psg0 = T_XX['P'].values[0] * (Sb / Ssg)
    Qsg0 = T_XX['Q'].values[0] * (Sb / Ssg)
    V = T_XX['V'].values[0]

    # SG parameters
    Rs_pu = T_XX['Rs'].values[0]
    Rtr = T_XX['Rtr'].values[0]
    Xtr = T_XX['Xtr'].values[0]
    Rsnb = T_XX['Rsnb'].values[0]
    Xq = T_XX['Xq'].values[0]

    # SG terminals voltage
    Itr = np.conj((Psg0 + 1j * Qsg0) / V)
    Vin = V + Itr * (Rtr + 1j * Xtr)
    theta_in = np.arctan(np.imag(Vin) / np.real(Vin))

    # Snubber current
    Isnb = Vin / Rsnb

    # SG current
    Isg = Isnb + Itr
    I = np.abs(Isg)

    # Apparent power (inside the transformer)
    Sin = Vin * np.conj(Isg)
    Pin = np.real(Sin)
    Qin = np.imag(Sin)
    phi = -np.arccos(Pin / (np.sqrt(Pin ** 2 + Qin ** 2))) * np.sign(Qin / Pin)

    # Internal voltage
    E = np.abs(Vin) + (Rs_pu + 1j * Xq) * (I * np.cos(phi) + 1j * I * np.sin(phi))
    Eq = np.real(E)
    Ed = np.imag(E)

    delta = np.arctan(Ed / Eq)  # rotor angle
    delta_slk = delta + theta_in  # rotor angle + trafo angle

    return delta_slk

def gfor_slack(T_XX, Sb):
    
    Svsc = T_XX['Sb'].values[0]  # GFOR rated power, GFOR power base

    # Data from the power-flow
    Pvsc0 = T_XX['P'].values[0] * (Sb / Svsc)
    Qvsc0 = T_XX['Q'].values[0] * (Sb / Svsc)
    V = T_XX['V'].values[0]/np.sqrt(3)/T_XX['Vbpu_l2g'].values[0] # PCC line-line voltage RMS

    # VSC parameters
    Rtr = T_XX['Rtr'].values[0]
    Xtr = T_XX['Xtr'].values[0]

    # Calculation of voltages and currents (REF: NET-POC)
    Ig = np.conj((Pvsc0 + 1j*Qvsc0) / (3*V))        # Transformer current
    U = V + Ig * (Rtr + 1j*Xtr)                     # Voltage at capacitor bus
    theta_in = np.arctan2(np.imag(U), np.real(U))   # angle between POC and capacitor bus

    delta_slk = theta_in  # trafo angle

    return delta_slk    

    
def assign_slack(d_grid):
    slack_bus=d_grid['T_gen'].query('type==0')['bus'].unique()[0]
    if len(d_grid['T_gen'].query('type==0')['bus'].unique())>1:
        raise RuntimeError('Error: more than 1 bus is type=slack')
    slack_bus_gen=list(d_grid['T_gen'].query('type==0')['element'])
    
    d_grid['T_global']['ref_bus']=slack_bus
    if 'SG' in slack_bus_gen:
        d_grid['T_global']['ref_element']='SG'
    elif 'GFOR' in slack_bus_gen:
        d_grid['T_global']['ref_element']='GFOR'
    else:
        raise RuntimeError('Error: missing generator at slack bus')
        
    return d_grid

