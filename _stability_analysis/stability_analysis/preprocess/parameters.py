import pandas as pd
import numpy as np


def get_params(d_grid, sg_data, vsc_data):  
    
    d_grid['T_global'] = global_params(d_grid['T_global'])
    d_grid['T_SG'] = SG_params(d_grid, sg_data)
    d_grid['T_VSC'] = VSC_params(d_grid, vsc_data)      
    return d_grid



def global_params(T_global):
    
    T_global['Sb'] = T_global['Sb_MVA']*1e6
    T_global['Vb'] = T_global['Vb_kV']*1e3
    T_global['Zb'] = T_global['Vb']**2/T_global['Sb']
    T_global['Ib'] = T_global['Sb']/T_global['Vb']
    T_global['fb'] = T_global['f_Hz']    
    return T_global



def SG_params(d_grid, sg_data):#excel_sg
           
    T_SG = d_grid['T_SG']
    # sg_data=pd.read_excel(excel_sg, sheet_name='UserCase')
    for i in range(len(T_SG)):
        T_SG.loc[i,list(sg_data['UserCase'].columns)]=list(sg_data['UserCase'].iloc[0])
        
    T_global = d_grid['T_global']    
    
    if not T_SG.empty:
    
        # System pu base is RMS-LL
        Sb_sys = T_SG['Area'].map(T_global.set_index('Area')['Sb']) #Sb system, in VA
        Vb_sys = T_SG['Area'].map(T_global.set_index('Area')['Vb']) #Vb system, in V
        fb_sys = T_SG['Area'].map(T_global.set_index('Area')['fb']) #fb, in Hz
    
        # Compute pu peak-FN base values
        T_SG['Sb'] = T_SG['Sn'] * 1e6
        T_SG['Vn'] = T_SG['Vn'] * 1e3
        T_SG['Vb'] = T_SG['Vn'] * np.sqrt(2/3)
        T_SG['Ib'] = (2/3) * T_SG['Sb'] / T_SG['Vb']
        T_SG['Zb'] = T_SG['Vn']**2 / T_SG['Sb']
        T_SG['wb'] = 2 * np.pi * fb_sys
        T_SG['Lb'] = T_SG['Zb'] / T_SG['wb']
        T_SG['fb'] = fb_sys
        T_SG['Lb'] = T_SG['Zb'] / T_SG['wb']
    
        # pu base conversions to system base
        T_SG['Sbpu_l2g'] = T_SG['Sb'] / Sb_sys
        T_SG['Vbpu_l2g'] = T_SG['Vb'] / Vb_sys
        T_SG['Ibpu_l2g'] = T_SG['Sb'] / Sb_sys * np.sqrt(2/3)
        T_SG['Zbpu_l2g'] = Sb_sys / T_SG['Sb']
    
        # SG electrical parameters
        Xl = T_SG['Xl']
        Xd = T_SG['Xd']
        Xd_tr = T_SG['Xd_tr']
        Xd_subtr = T_SG['Xd_subtr']
        Xq = T_SG['Xq']
        Xq_tr = T_SG['Xq_tr']
        Xq_subtr = T_SG['Xq_subtr']
        Tdo_tr = T_SG['Tdo_tr']
        Tdo_subtr = T_SG['Tdo_subtr']
        Tqo_tr = T_SG['Tqo_tr']
        Tqo_subtr = T_SG['Tqo_subtr']
    
        Xmd = Xd - Xl
        Xmq = Xq - Xl
    
        # d axis
        Td_tr = Tdo_tr * Xd_tr / Xd
        Td_subtr = Tdo_subtr * Xd_subtr / Xd_tr
    
        Ld = Xd * T_SG['Lb']
        Lmd = Xmd * T_SG['Lb']
        Ll = Xl * T_SG['Lb']
    
        A = Lmd**2 / (Ld * (Tdo_tr + Tdo_subtr - Td_tr - Td_subtr))
        a = (Ld * (Td_tr + Td_subtr) - Ll * (Tdo_tr + Tdo_subtr)) / Lmd
        b = (Ld * Td_tr * Td_subtr - Ll * Tdo_tr * Tdo_subtr) / Lmd
        c = (Tdo_tr * Tdo_subtr - Td_tr * Td_subtr) / (Tdo_tr + Tdo_subtr - Td_tr - Td_subtr)
        a=a.astype(float)
        b=b.astype(float)
        c=c.astype(float)
        
        
        ra = (2 * A * np.sqrt(a**2 - 4*b)) / (a - 2*c + np.sqrt(a**2 - 4*b))
        La = ra * (a + np.sqrt(a**2 - 4*b)) / 2
        rb = (2 * A * np.sqrt(a**2 - 4*b)) / (2*c - a + np.sqrt(a**2 - 4*b))
        Lb = rb * (a - np.sqrt(a**2 - 4*b)) / 2
    
        Rf_pu = ra / T_SG['Zb']
        Lfd_pu = La / T_SG['Lb']
        R1d_pu = rb / T_SG['Zb']
        L1d_pu = Lb / T_SG['Lb']
        
        # q axis
        Tq_tr = Tqo_tr * Xq_tr / Xq
        Tq_subtr = Tqo_subtr * Xq_subtr / Xq_tr
        
        Lq = Xq * T_SG['Lb']
        Lmq = Xmq * T_SG['Lb']
        
        A = Lmq ** 2 / (Lq * (Tqo_tr + Tqo_subtr - Tq_tr - Tq_subtr))
        a = (Lq * (Tq_tr + Tq_subtr) - Ll * (Tqo_tr + Tqo_subtr)) / Lmq
        b = (Lq * Tq_tr * Tq_subtr - Ll * Tqo_tr * Tqo_subtr) / Lmq
        c = (Tqo_tr * Tqo_subtr - Tq_tr * Tq_subtr) / (Tqo_tr + Tqo_subtr - Tq_tr - Tq_subtr)
        
        a=a.astype(float)
        b=b.astype(float)
        c=c.astype(float)
      
        ra = (2 * A * np.sqrt(a ** 2 - 4 * b)) / (a - 2 * c + np.sqrt(a ** 2 - 4 * b))
        La = ra * (a + np.sqrt(a ** 2 - 4 * b)) / 2
        rb = (2 * A * np.sqrt(a ** 2 - 4 * b)) / (2 * c - a + np.sqrt(a ** 2 - 4 * b))
        Lb = rb * (a - np.sqrt(a ** 2 - 4 * b)) / 2
        
        R1q_pu = ra / T_SG['Zb']
        L1q_pu = La / T_SG['Lb']
        R2q_pu = rb / T_SG['Zb']
        L2q_pu = Lb / T_SG['Lb']
        
        # Conversion from standard to equivalent circuit parameters
        Ll_pu = Xl
        Lmd_pu = Xd - Xl
        Lmq_pu = Xq - Xl   
        
        # save to T_SG
        T_SG['Ll_pu'] = Ll_pu
        T_SG['Lmd_pu'] = Lmd_pu
        T_SG['Lmq_pu'] = Lmq_pu
        T_SG['Lfd_pu'] = Lfd_pu
        T_SG['L1q_pu'] = L1q_pu
        T_SG['L1d_pu'] = L1d_pu
        T_SG['L2q_pu'] = L2q_pu
        T_SG['Rf_pu'] = Rf_pu
        T_SG['R1d_pu'] = R1d_pu
        T_SG['R1q_pu'] = R1q_pu
        T_SG['R2q_pu'] = R2q_pu
        T_SG['Ltr'] = T_SG['Xtr'] / (2 * np.pi * T_SG['fb'])
        
         
        # types = pd.ExcelFile(excel_sg).sheet_names
        types = [sheet_name for sheet_name in sg_data]
        T_SG['exc'] = np.empty(len(T_SG.index), dtype=object)
        T_SG['PSS'] = np.empty(len(T_SG.index), dtype=object)
        T_SG['mech'] = np.empty(len(T_SG.index), dtype=object)
        
        for index, row in T_SG.iterrows():
    
            # Exciter
            if any(['EXCITER-' + row['exciter'] in types for types in types]):
                T_exciter= sg_data['EXCITER-' + row['exciter']]
                #T_exciter = pd.read_excel(excel_sg, sheet_name='EXCITER-' + row['exciter'])
                ## T_exciter = T_exciter[T_exciter['number'] == row['number']]
                ## T_exciter = T_exciter.drop(['number', 'bus'], axis=1)
            else:
                exc = {'TR': 0}  # no exciter
            T_SG.at[index, 'exc'] = T_exciter
        
            # PSS
            if any(['PSS-' + row['pss'] in types for types in types]):
                T_pss=sg_data['PSS-' + row['pss']]
                # T_pss = pd.read_excel(excel_sg, sheet_name='PSS-' + row['pss'])
                # # T_pss = T_pss[T_pss['number'] == row['number']]
                # # T_pss = T_pss.drop(['number', 'bus'], axis=1)
                T_pss.at[0,'hasPSS'] = 1
            else:
                T_pss = pd.DataFrame({'hasPSS': [0]})
            T_SG.at[index, 'PSS'] = T_pss
        
            # Governor and turbine
            if any(['GOVTURB-' + row['govturb'] in types for types in types]):
                T_govturb = sg_data['GOVTURB-' + row['govturb']]
                # T_govturb = pd.read_excel(excel_sg, sheet_name='GOVTURB-' + row['govturb'])
                # # T_govturb = T_govturb[T_govturb['number'] == row['number']]
                # # T_govturb = T_govturb.drop(['number', 'bus'], axis=1)
            else:
                T_govturb = pd.DataFrame({'R': [0]})  # no governor-turbine
            T_SG.at[index, 'mech'] = T_govturb
            
    return T_SG


def VSC_params(d_grid, vsc_data): #excel_vsc
    
    T_VSC = d_grid['T_VSC']
    T_global = d_grid['T_global']    
    
    if not T_VSC.empty:
    
        # System pu base is RMS-LL
        Sb_sys = T_VSC['Area'].map(T_global.set_index('Area')['Sb']) #Sb system, in VA
        Vb_sys = T_VSC['Area'].map(T_global.set_index('Area')['Vb']) #Vb system, in V
        fb_sys = T_VSC['Area'].map(T_global.set_index('Area')['fb']) #fb, in Hz  
        Ib_sys = Sb_sys/Vb_sys
        Zb_sys = Vb_sys/Ib_sys
        
        # Compute pu RMS-LL base values
        T_VSC['Sb'] = T_VSC['Sn'] * 1e6 #Sb machine, in VA
        T_VSC['Vn'] = T_VSC['Vn'] * 1e3 #rated RMS-LL, in V
        T_VSC['Vb'] = T_VSC['Vn'] #voltage base (RMS, LL), in V 
        T_VSC['Ib'] = T_VSC['Sb'] / T_VSC['Vb'] #current base (RMS, phase current), in A
        T_VSC['Zb'] = T_VSC['Vn']**2 / T_VSC['Sb'] #impedance base, in ohm
        T_VSC['wb'] = 2 * np.pi * fb_sys
        T_VSC['Lb'] = T_VSC['Zb'] / T_VSC['wb'] #impedance base, in ohm
        T_VSC['fb'] = fb_sys
        T_VSC['Lb'] = T_VSC['Zb'] / T_VSC['wb']
        
        # pu base conversions to system base
        # l2g: from local 2 global: SG --> system
        T_VSC['Sbpu_l2g'] = T_VSC['Sb'] / Sb_sys
        T_VSC['Vbpu_l2g'] = T_VSC['Vb'] / Vb_sys
        T_VSC['Ibpu_l2g'] = T_VSC['Ib'] / Ib_sys 
        T_VSC['Zbpu_l2g'] = T_VSC['Zb'] / Zb_sys
        
        # VSC parameters
                                
        for idx, row in T_VSC.iterrows():
            mode = row['mode']
            T_data = vsc_data['User'+mode]
            #T_data = pd.read_excel(excel_vsc, sheet_name='User'+mode)
            
            ## T_data = T_data[T_data['number'] == row['number']]
            ## T_data = T_data.drop(['number', 'bus'], axis=1)
            
            T_data = T_data.to_dict(orient="records")[0]
            
            # Transformer
            T_VSC.at[idx,'Rtr'] = T_data['Rtr']
            T_VSC.at[idx,'Xtr'] = T_data['Xtr']
            T_VSC.at[idx,'Ltr'] = T_VSC.at[idx,'Xtr']/T_VSC.at[idx,'wb']       
            
            # RLC filter
            T_VSC.at[idx,'Rc'] = T_data['Rc']
            T_VSC.at[idx,'Xc'] = T_data['Xc']
            T_VSC.at[idx,'Lc'] = T_VSC.at[idx,'Xc'] / T_VSC.at[idx,'wb']
            T_VSC.at[idx,'Cac'] = T_data['Bac'] / T_VSC.at[idx,'wb'] # Converter grid coupling filter capacitance
            if T_VSC.at[idx,'Cac'] != 0:
                T_VSC.at[idx,'Rac'] = 1 / (3 * 10 * T_VSC.at[idx,'wb'] * T_VSC.at[idx,'Cac']) # passive damping
            else:
                T_VSC.at[idx,'Rac'] = np.inf
            
            # Current control
            T_VSC.at[idx,'taus'] = T_data['tau_s']
            T_VSC.at[idx,'kp_s'] = T_VSC.at[idx,'Lc'] / T_VSC.at[idx,'taus']
            T_VSC.at[idx,'ki_s'] = T_VSC.at[idx,'Rc'] / T_VSC.at[idx,'taus']
            
            match mode:
                
                case 'GFOL':
                    
                    # PLL
                    T_VSC.at[idx,'ts_pll'] = T_data['ts_pll']
                    T_VSC.at[idx,'xi_pll'] = T_data['xi_pll']
                    T_VSC.at[idx,'omega_pll'] = 4 / (T_VSC.at[idx,'ts_pll'] * T_VSC.at[idx,'xi_pll'])
                    T_VSC.at[idx,'tau_pll'] = 2 * T_VSC.at[idx,'xi_pll'] / T_VSC.at[idx,'omega_pll']
                    T_VSC.at[idx,'kp_pll'] = 2 * T_VSC.at[idx,'omega_pll'] * T_VSC.at[idx,'xi_pll']
                    T_VSC.at[idx,'ki_pll'] = T_VSC.at[idx,'kp_pll'] / T_VSC.at[idx,'tau_pll']
                    
                    # Power loops
                    T_VSC.at[idx,'tau_p'] = T_data['tau_p']
                    T_VSC.at[idx,'kp_P'] = T_VSC.at[idx,'taus'] / T_VSC.at[idx,'tau_p'] * (T_VSC.at[idx,'Sb'] / T_VSC.at[idx,'Ib'] / 1000)
                    T_VSC.at[idx,'ki_P'] = 1 / T_VSC.at[idx,'tau_p'] * (T_VSC.at[idx,'Sb'] / T_VSC.at[idx,'Ib'] / 1000)
                    T_VSC.at[idx,'tau_q'] = T_data['tau_q']
                    T_VSC.at[idx,'kp_Q'] = T_VSC.at[idx,'taus'] / T_VSC.at[idx,'tau_q'] * (T_VSC.at[idx,'Sb'] / T_VSC.at[idx,'Ib'] / 1000)
                    T_VSC.at[idx,'ki_Q'] = 1 / T_VSC.at[idx,'tau_q'] * (T_VSC.at[idx,'Sb'] / T_VSC.at[idx,'Ib'] / 1000)
                    T_VSC.at[idx,'tau_droop_f'] = T_data['tau_droop_f']
                    T_VSC.at[idx,'k_droop_f'] = T_data['k_droop_f']
                    T_VSC.at[idx,'tau_droop_u'] = T_data['tau_droop_u']
                    T_VSC.at[idx,'k_droop_u'] = T_data['k_droop_u']
                    
                case 'GFOR':
                     # AC voltage control
                    T_VSC.at[idx,'set_time_v'] = T_data['set_time_v'] # in s
                    T_VSC.at[idx,'xi_v'] = T_data['xi_v']
                    T_VSC.at[idx,'wn_v'] = 4 / (T_VSC.at[idx,'set_time_v'] * T_VSC.at[idx,'xi_v'])
                    T_VSC.at[idx,'kp_vac'] = 2 * T_VSC.at[idx,'xi_v'] * T_VSC.at[idx,'wn_v'] * T_VSC.at[idx,'Cac'] * 100
                    T_VSC.at[idx,'ki_vac'] = T_VSC.at[idx,'wn_v']**2 * T_VSC.at[idx,'Cac']
                    
                    # Feedforward filters
                    T_VSC.at[idx,'tau_u'] = T_data['tau_u']
                    T_VSC.at[idx,'tau_ig'] = T_data['tau_ig']
                    
                    # Droop parameters
                    T_VSC.at[idx,'tau_droop_f'] = T_data['tau_droop_f']
                    T_VSC.at[idx,'k_droop_f'] = T_data['k_droop_f']
                    T_VSC.at[idx,'tau_droop_u'] = T_data['tau_droop_u']
                    T_VSC.at[idx,'k_droop_u'] = T_data['k_droop_u']
               
    return T_VSC