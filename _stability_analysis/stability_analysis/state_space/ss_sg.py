import numpy as np
import pandas as pd
import control as ct
from control.matlab import ss
from stability_analysis.state_space import ss_functions as ssf
from stability_analysis.state_space import interconnect

def save_ss_matrices_fun(ss,path,filename):
    pd.DataFrame.to_csv(pd.DataFrame(ss.A),path+filename+'_A.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.B),path+filename+'_B.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.C),path+filename+'_C.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.D),path+filename+'_D.csv',index=False,header=False)
 


def generate_linearization_point_SG(d_grid):
    
    T_SG = d_grid['T_SG']
    T_global = d_grid['T_global']    
    lp_SG = T_SG[['number','bus']].copy()
    
    for idx,row in T_SG.iterrows():
 
        Ssg = row['Sb']  # SG rated power, SG power base
        Sb = T_global[T_global['Area'] == row['Area']]['Sb'].iloc[0]  # System power base
        delta_slk = T_global[T_global['Area'] == row['Area']]['delta_slk'].iloc[0]
               
        # SG parameters
        Rs_pu = row['Rs']
        Rtr = row['Rtr']
        Xtr = row['Xtr']
        Rsnb = row['Rsnb']
        Xq = row['Xq']
        Xd = row['Xd']
        Xd_tr = row['Xd_tr']
        Lmd_pu = row['Lmd_pu']
        
        # Data from the power-flow
        delta0 = row['theta'] * (np.pi / 180)
        V = row['V']  # PCC line-line voltage RMS
        Psg0 = row['P'] * (Sb / Ssg)
        Qsg0 = row['Q'] * (Sb / Ssg)
        
        Itr = np.conj((Psg0 + 1j * Qsg0) / V)
        Vin = V + Itr * (Rtr + 1j * Xtr)
        theta_in = np.arctan2(np.imag(Vin), np.real(Vin))
        
        Isnb = Vin / Rsnb
        Isg = Isnb + Itr
        I = np.abs(Isg)
        
        Sin = Vin * np.conj(Isg)
        Pin = np.real(Sin)
        Qin = np.imag(Sin)
        phi = -np.arccos(Pin / (np.sqrt(Pin**2 + Qin**2))) * np.sign(Qin / Pin)
        
        E = np.abs(Vin) + (Rs_pu + 1j * Xq) * (I * np.cos(phi) + 1j * I * np.sin(phi))
        Eq = np.real(E)
        Ed = np.imag(E)
        
        Emag = np.abs(E)
        delta = np.arctan2(Ed, Eq)
        
        Iq = I * np.cos(-delta + phi)
        Id = -I * np.sin(-delta + phi)
        
        vsgq_g0 = np.abs(Vin) * np.cos(-delta)
        vsgd_g0 = -np.abs(Vin) * np.sin(-delta)
        
        delta_bus = delta0 + theta_in - delta_slk
        
        Vq = np.abs(Vin) * np.cos(delta_bus) * np.sqrt(2/3)
        Vd = -np.abs(Vin) * np.sin(delta_bus) * np.sqrt(2/3)
        
        Vq_bus = np.abs(V) * np.cos(delta0 - delta_slk) * np.sqrt(2/3)
        Vd_bus = -np.abs(V) * np.sin(delta0 - delta_slk) * np.sqrt(2/3)
        
        Eq_tr = Emag - Id * (Xq - Xd_tr)
        Efd = Eq_tr + (Xd - Xd_tr) * Id
        Ifd = Efd / Lmd_pu
        
        Pm0 = Pin + (Iq**2 + Id**2) * Rs_pu
        
        e_theta0 = delta0 + delta + theta_in - delta_slk
                
         # Store linearization point in DataFrame
        lp_SG.at[idx, 'isq0'] = Iq  # pu
        lp_SG.at[idx, 'isd0'] = Id  # pu
        lp_SG.at[idx, 'ifd0'] = Ifd  # pu
        lp_SG.at[idx, 'ikd0'] = 0
        lp_SG.at[idx, 'ikq10'] = 0
        lp_SG.at[idx, 'ikq20'] = 0
        lp_SG.at[idx, 'vq0'] = Vq  # V
        lp_SG.at[idx, 'vd0'] = Vd  # V
        lp_SG.at[idx, 'w0_pu'] = 1  # pu
        lp_SG.at[idx, 'w0'] = T_SG.loc[idx, 'wb'] # rad/s
        lp_SG.at[idx, 'etheta0'] = e_theta0
        lp_SG.at[idx, 'Pm0'] = Pm0
        lp_SG.at[idx, 'vq_bus0'] = Vq_bus
        lp_SG.at[idx, 'vd_bus0'] = Vd_bus
        lp_SG.at[idx, 'vsg_q0'] = vsgq_g0
        lp_SG.at[idx, 'vsg_d0'] = vsgd_g0
    
    return lp_SG






def generate_SG_pu(l_blocks, l_states, d_grid, lp_SG, connect_fun='append_and_connect',save_ss_matrices=False):    
    
    T_SG = d_grid['T_SG']
    T_global = d_grid['T_global']
    
    n_sg=0
    for idx, row in T_SG.iterrows():  
        
        ss_list = [] # Create list to store SG subsystems blocks 
        x_list = [] # Creat elist to store SG subsystems states
        num = row['number']
        bus = row['bus']
        num_slk = T_global[T_global['Area'] == row['Area']]['num_slk'].iloc[0]
        element_slk = T_global[T_global['Area'] == row['Area']]['ref_element'].iloc[0]
        REF_w = 'REF_w'
        
        # Set names of state variables, inputs and outputs  
        
        exc_x1 = 'SG' + str(num) + '_exc_x1'
        exc_x2 = 'SG' + str(num) + '_exc_x2'
        exc_filt = 'SG' + str(num) + '_exc_filtx'
        
        gov_x1 = 'SG' + str(num) + '_gov_x1'
        gov_x2 = 'SG' + str(num) + '_gov_x2'
        Pref = 'SG' + str(num) + '_Pref'
        
        turb_x = 'SG' + str(num) + '_turb_x'
        
        is_q = 'SG' + str(num) + '_is_q'
        is_d = 'SG' + str(num) + '_is_d'
        ik1_q = 'SG' + str(num) + '_ik1_q'
        ik2_q = 'SG' + str(num) + '_ik2_q'
        ik_d = 'SG' + str(num) + '_ik_d'
        if_d = 'SG' + str(num) + '_if_d'
        we_pu = 'SG' + str(num) + '_w_pu'
        theta = 'SG' + str(num) + '_th'
        e_theta = 'SG' + str(num) + '_e_th'
        Te = 'SG' + str(num) + '_Te'
        vk_d = 'SG' + str(num) + '_vk_d'
        vk1_q = 'SG' + str(num) + '_vk1_q'
        vk2_q = 'SG' + str(num) + '_vk2_q'
        vf_d = 'SG' + str(num) + '_vfd'
        
        vsgq_pu = 'SG' + str(num) + '_vsgq_pu'
        vsgd_pu = 'SG' + str(num) + '_vsgd_pu'
        
        w_real = 'SG' + str(num) + '_w'
        
        ig_q = 'SG' + str(num) + '_ig_qx'
        ig_d = 'SG' + str(num) + '_ig_dx'
        
        vnXq = 'NET_vn' + str(bus) + 'q'
        vnXd = 'NET_vn' + str(bus) + 'd'
        iq = 'SG' + str(num) + '_iq'
        id = 'SG' + str(num) + '_id'
        
        # Parameters
        
        Zl2g = row['Zbpu_l2g']
        Sl2g = row['Sbpu_l2g']
        Vl2g = row['Vbpu_l2g']
        Il2g = row['Ibpu_l2g']
        wb = row['wb']
        
        Rtr = row['Rtr']
        Ltr = row['Ltr']
        Rsnb = row['Rsnb']
        Rs_pu = row['Rs']
        Rf_pu = row['Rf_pu']
        R1d_pu = row['R1d_pu']
        R1q_pu = row['R1q_pu']
        R2q_pu = row['R2q_pu']
        Ll_pu = row['Ll_pu']
        Lmq_pu = row['Lmq_pu']
        Lmd_pu = row['Lmd_pu']
        L1q_pu = row['L1q_pu']
        L2q_pu = row['L2q_pu']
        L1d_pu = row['L1d_pu']
        Lfd_pu = row['Lfd_pu']
        
        H = row['H']
        exc = row['exc'].to_dict(orient="records")[0]
        mech = row['mech'].to_dict(orient="records")[0]
        pss = row['PSS'].to_dict(orient="records")[0]
        
        # Linearization point
        
        isq0 = lp_SG.loc[idx, 'isq0']
        isd0 = lp_SG.loc[idx, 'isd0']
        ifd0 = lp_SG.loc[idx, 'ifd0']
        ikd0 = lp_SG.loc[idx, 'ikd0']
        ikq10 = lp_SG.loc[idx, 'ikq10']
        ikq20 = lp_SG.loc[idx, 'ikq20']
        vq0 = lp_SG.loc[idx, 'vq0']
        vd0 = lp_SG.loc[idx, 'vd0']
        vsgq_g0 = lp_SG.loc[idx, 'vsg_q0']
        vsgd_g0 = lp_SG.loc[idx, 'vsg_d0']
        w0_pu = lp_SG.loc[idx, 'w0_pu']
        w0 = lp_SG.loc[idx, 'w0']
        e_theta0 = lp_SG.loc[idx, 'etheta0']
        Pm0 = lp_SG.loc[idx, 'Pm0']
              
               
        # TRANSFORMER AND SNUBBER
        
        # Transformer 
        Atr = np.array([[-(Rtr)/(Ltr), -w0], 
                        [w0, -(Rtr)/(Ltr)]])        
        Btr = np.array([[1/(Ltr*Zl2g), 0, -1/(Ltr*Zl2g), 0],
                        [0, 1/(Ltr*Zl2g), 0, -1/(Ltr*Zl2g)]])        
        Ctr = np.array([[1, 0], [0, 1]])        
        Dtr = np.array([[0, 0, 0, 0], [0, 0, 0, 0]])
        
        tr_x = [ig_q, ig_d]
        tr_u = ['vsg_q', 'vsg_d', 'vg_q', 'vg_d']
        tr_y = ['ig_q', 'ig_d']
        
        tr_ss = ss(Atr, Btr, Ctr, Dtr, inputs=tr_u, outputs=tr_y, states=tr_x)        
        ss_list.append(tr_ss)   
        x_list.extend(tr_x)
        
        # Sum of currents SG snubber
        Aisnb = np.empty(0)
        Bisnb = np.empty((0, 2))
        Cisnb = np.empty((0, 2))
        Disnb = np.array([[1, 0, -1, 0],
                         [0, 1, 0, -1]])
        
        isnb_u = ['isg_q', 'isg_d', 'ig_q', 'ig_d']
        isnb_y = ['isn_q', 'isn_d']
        
        isnb_ss = ss(Aisnb, Bisnb, Cisnb, Disnb, inputs=isnb_u, outputs=isnb_y)        
        ss_list.append(isnb_ss)
        
        # SG snubber
        Asnb = np.empty(0)
        Bsnb = np.empty((0, 2))
        Csnb = np.empty((0, 2))
        Dsnb = np.array([[Rsnb*Zl2g, 0],
                         [0, Rsnb*Zl2g]])
        
        snb_u = ['isn_q', 'isn_d']
        snb_y = ['vsg_q', 'vsg_d']
        
        snb_ss = ss(Asnb, Bsnb, Csnb, Dsnb, inputs=snb_u, outputs=snb_y)        
        ss_list.append(snb_ss)
        
        # Espacio de estados Vsg qd: system -> sg
        Avsg_pu = np.empty(0)
        Bvsg_pu = np.empty((0, 2))
        Cvsg_pu = np.empty((0, 2))
        Dvsg_pu = np.array([[1/Vl2g, 0], [0, 1/Vl2g]])
                
        if num == num_slk and element_slk == "SG":
            vsg_pu_u = ['vsg_q', 'vsg_d']
        else:
            vsg_pu_u = ['vsg_qg', 'vsg_dg']            
        vsg_pu_y = [vsgq_pu, vsgd_pu] 
        
        vsg_pu = ss(Avsg_pu, Bvsg_pu, Cvsg_pu, Dvsg_pu, inputs=vsg_pu_u, outputs=vsg_pu_y)       
        ss_list.append(vsg_pu)
    
        
        # EXCITER
        if row['exciter'] != "no":
        
            # SG voltage magnitude
            Avsg = np.empty(0)
            Bvsg = np.empty((0, 2))
            Cvsg = np.empty((0, 2))
            Dvsg = np.array([[vsgq_g0/np.sqrt(vsgq_g0**2 + vsgd_g0**2), vsgd_g0/np.sqrt(vsgq_g0**2 + vsgd_g0**2)]])       
            vsg_u = [vsgq_pu, vsgd_pu]
            vsg_y = ['Vsg_mag']            
            vsg = ss(Avsg, Bvsg, Cvsg, Dvsg, inputs=vsg_u, outputs=vsg_y)        
            ss_list.append(vsg)
        
            # Exciter filter (voltage transducer)   
            exf = ssf.SS_LOW_PASS(k=1, tau=exc['TR'], input='Vsg_mag', output='Vc', state=exc_filt)        
            ss_list.append(exf)
            x_list.extend([exc_filt])
        
            # Exciter control
            match row['exciter']:
                
                case 'ST4B': 
                    
                    # Set input names and compute linearization point values
                    Ve0 = np.sqrt(vsgq_g0**2 + vsgd_g0**2) * exc['KP']
                    Ifd0 = ifd0 * Lmd_pu
                    fIn0 = 1 - 0.577 * exc['KC'] * Ifd0 / Ve0
                    
                    if pss['hasPSS']: # with PSS
                        Vsi10 = 0
                        Vsi20 = Pm0 * 1
                        Vst0 = pss.Ks1 * (Vsi10 + (pss.Ks3 - 1) * pss.Ks2 * Vsi20)
                        Vm0 = (-np.sqrt(vsgq_g0**2 + vsgd_g0**2) + 1 + Vst0) * exc['KPR']                        
                        excInput_ss = ssf.SS_ERROR(input_ref='SG_Vst', input_sub='Vc', output='V_excInput')
                    
                    else: # without PSS
                        Vm0 = (-np.sqrt(vsgq_g0**2 + vsgd_g0**2) + 1) * exc['KPR']                        
                        excInput_ss = ssf.SS_GAIN(-1, 'Vc', 'V_excInput')                                    
                    
                    Vm0 = (-np.sqrt(vsgq_g0**2 + vsgd_g0**2) + 1 + 0) * exc['KPR']  
                    Vb0 = Ve0 * fIn0
            
                    # Exciter block 1                             
                    exc1_1 = ct.tf([exc['KPR'], exc['KIR']], [1, 0])
                    exc1_2 = ct.tf([1],[exc['TA'], 1])
                    exc1_tf = exc1_1*exc1_2
                    exc1_ss = ct.tf2ss(exc1_tf)
                    exc1_x = [exc_x1,exc_x2]
                    exc1_u = ['V_excInput']
                    exc1_y = ['Vm']
                    exc1_ss = ss(exc1_ss.A, exc1_ss.B, exc1_ss.C, exc1_ss.D, states=exc1_x, inputs=exc1_u, outputs=exc1_y)
            
                    # Exciter block 2
                    exc2_ss = ssf.SS_PROD('Vm', Vm0, 'Vb', Vb0, 'SG_Vfd')
            
                    # Exciter block 3 (base change)
                    exc3_ss = ssf.SS_GAIN(Rf_pu/Lmd_pu,'SG_Vfd', vf_d)
            
                    # Exciter block 4
                    exc4_ss = ssf.SS_PROD('Ve', Ve0, 'fIn', fIn0, 'Vb')
            
                    # Exciter block 5
                    exc5_ss = ssf.SS_GAIN(exc['KP'], 'Vsg_mag', 'Ve')
            
                    # Exciter block 6
                    exc6_ss = ssf.SS_PROD('Ve', -exc['KC'] * Ifd0 / Ve0**2, 'SG_Ifd', exc['KC'] / Ve0, 'In')
            
                    # Exciter block 7
                    exc7_ss = ssf.SS_GAIN(-0.577,'In', 'fIn')
            
                    # Exciter block 8
                    exc8_ss = ssf.SS_GAIN(Lmd_pu,'SG_ifd', 'SG_Ifd')
            
                    if pss['hasPSS']: # with PSS
                        exc_u = ['Vc', 'Vsg_mag', 'SG_ifd', 'SG_Vst']
                        exc_y = [vf_d]
                    else:
                        exc_u = ['Vc', 'Vsg_mag', 'SG_ifd']
                        exc_y = [vf_d]
            
                    if connect_fun=='interconnect':
                        exc_ss = ct.interconnect([excInput_ss, exc1_ss, exc2_ss, exc3_ss, exc4_ss, exc5_ss, exc6_ss, exc7_ss, exc8_ss], states = exc1_x , inputs = exc_u, outputs = exc_y)

                        if save_ss_matrices == True:
                            save_ss_matrices_fun(exc_ss,
                                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                     f'{exc_ss=}'.split('=')[0]+str(n_sg))
                    elif connect_fun == 'append_and_connect':
                        exc_ss = interconnect.interconnect([excInput_ss, exc1_ss, exc2_ss, exc3_ss, exc4_ss, exc5_ss, exc6_ss, exc7_ss, exc8_ss], states = exc1_x , inputs = exc_u, outputs = exc_y)

                        
                        if save_ss_matrices == True:
                            save_ss_matrices_fun(exc_ss,
                                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                 f'{exc_ss=}'.split('=')[0]+str(n_sg))

                    x_list.extend(exc1_x)
            
                case 'ST1':
                    print("Exciter model ST1 does not implement feedback yet and is equivalent to AC4A")
                    exc_1 = ct.tf([exc['TC'], 1], [exc['TB'], 1])
                    exc_2 = ct.tf([exc['KA']], [exc['TA'], 1])
                    exc_tf = exc_1*exc_2 * -Rf_pu/Lmd_pu
                    exc_ss = ct.tf2ss(exc_tf)
                    
                    if exc['TA']:
                        exc_x = [exc_x1,exc_x2]
                    else:                    
                        exc_x = [exc_x1]                        
                    exc_y = [vf_d]                 
                      
                    if pss['hasPSS']: # with PSS
                        excInput_ss = ssf.SS_ERROR(input_ref='Vc', input_sub='SG_Vst', output='V_excInput')
                        exc_ss0 = ss(exc_ss.A, exc_ss.B, exc_ss.C, exc_ss.D, states=exc_x, inputs=['V_excInput'], outputs=exc_y)
                        
                        if connect_fun=='interconnect':
                            exc_ss = ct.interconnect([excInput_ss, exc_ss0], states=exc_x, inputs = ['Vc','SG_Vst'], outputs = exc_y)

                            if save_ss_matrices == True:
                                save_ss_matrices_fun(exc_ss,
                                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                         f'{exc_ss=}'.split('=')[0]+str(n_sg))
                        elif connect_fun == 'append_and_connect':
                            exc_ss = interconnect.interconnect([excInput_ss, exc_ss0], states=exc_x, inputs = ['Vc','SG_Vst'], outputs = exc_y)

                            
                            if save_ss_matrices == True:
                                save_ss_matrices_fun(exc_ss,
                                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                     f'{exc_ss=}'.split('=')[0]+str(n_sg))
                                             
                    else:  # without PSS 
                        exc_ss = ss(exc_ss.A, exc_ss.B, exc_ss.C, exc_ss.D, states=exc_x, inputs=['Vc'], outputs=exc_y)
                    
                    x_list.extend(exc_x)
            
                case 'AC4A':
                    exc_1 = ct.tf([exc['TC'], 1], [exc['TB'], 1])
                    exc_2 = ct.tf([exc['KA']], [exc['TA'], 1])
                    exc_tf = exc_1*exc_2 * -Rf_pu/Lmd_pu
                    exc_ss = ct.tf2ss(exc_tf)
                    
                    if exc['TA']:
                        exc_x = [exc_x1,exc_x2]
                    else:                    
                        exc_x = [exc_x1]                        
                    exc_y = [vf_d]                 
                      
                    if pss['hasPSS']: # with PSS
                        excInput_ss = ssf.SS_ERROR(input_ref='Vc', input_sub='SG_Vst', output='V_excInput')
                        exc_ss0 = ss(exc_ss.A, exc_ss.B, exc_ss.C, exc_ss.D, states=exc_x, inputs=['V_excInput'], outputs=exc_y)
                        
                        if connect_fun=='interconnect':
                            exc_ss = ct.interconnect([excInput_ss, exc_ss0], states=exc_x, inputs = ['Vc','SG_Vst'], outputs = exc_y)

                            if save_ss_matrices == True:
                                save_ss_matrices_fun(exc_ss,
                                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                         f'{exc_ss=}'.split('=')[0]+str(n_sg))
                        elif connect_fun == 'append_and_connect':
                            exc_ss = interconnect.interconnect([excInput_ss, exc_ss0], states=exc_x, inputs = ['Vc','SG_Vst'], outputs = exc_y)

                            
                            if save_ss_matrices == True:
                                save_ss_matrices_fun(exc_ss,
                                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                     f'{exc_ss=}'.split('=')[0]+str(n_sg))
                        
                     
                    else:  # without PSS
                        exc_ss = ss(exc_ss.A, exc_ss.B, exc_ss.C, exc_ss.D, states=exc_x, inputs=['Vc'], outputs=exc_y)
                    
                    x_list.extend(exc_x)
        
            ss_list.append(exc_ss)
        
            # PSS
            if pss['hasPSS']:
                
                match row['pss']:
                
                    case '2A':
                        # Vsi1: Rotor speed deviation in [pu]    
                        # Vsi2: Electrical power [pu] == Te*w 
                        Pe_ss    = ssf.SS_PROD(Te,Pm0,we_pu,1,'SG_Pe')            
                        
                        # PSS block 1
                        pss1_1  = ssf.tf_WASH_OUT(pss['Tw1'])
                        pss1_2  = ssf.tf_WASH_OUT(pss['Tw2'])
                        pss1_3  = ssf.tf_LOW_PASS(1, pss['Tw6']) 
                        pss1_tf = pss1_1*pss1_2*pss1_3
                        pss1_ss = ct.tf2ss(pss1_tf)
                        pss1_x  = ['SG' + str(num) + '_pss1_x1', 'SG' + str(num) + '_pss1_x2']
                        pss1_ss = ss(pss1_ss.A, pss1_ss.B, pss1_ss.C, pss1_ss.D, states = pss1_x, inputs = we_pu, outputs = ['SG_Vsi1_out'])
                        
                        # PSS block 2
                        pss2_1  = ssf.tf_WASH_OUT(pss['Tw3'])
                        pss2_2  = ssf.tf_LOW_PASS(pss['Ks2'], pss['T7'])
                        pss2_tf = pss2_1*pss2_2
                        pss2_ss = ct.tf2ss(pss2_tf)
                        pss2_x  = ['SG' + str(num) + '_pss1_x1', 'SG' + str(num) + '_pss1_x2']
                        pss2_ss = ss(pss2_ss.A, pss2_ss.B, pss2_ss.C, pss2_ss.D, states = pss2_x, inputs = ['SG_Pe'], outputs = ['SG_Vsi2_out'])
                        
                        # PSS block 3
                        pss3_ss = ssf.SS_ADD('SG_Vsi1_out','SG_Vsi2_out','SG_Vsi_sum')
                        
                        # PSS block 4
                        pss4_tf = (ct.tf([pss['T8'], 1],1)/ct.tf([pss['T9'], 1],1)**int(pss['M']))**int(pss['N'])
                        pss4_ss = ct.tf2ss(pss4_tf)
                        pss4_x = []
                        for idx in range(1, pss['M']*pss['N']+1):
                            pss4_x.append('SG'+str(num)+'_pss4_x'+str(idx))
                        pss4_ss = ss(pss4_ss.A, pss4_ss.B, pss4_ss.C, pss4_ss.D, states = pss4_x, inputs = ['SG_Vsi_sum'], outputs = ['SG_Vsi_out'])
                                                   
                        # PSS block 5
                        pss5_ss = ssf.SS_ERROR('SG_Vsi_out','SG_Vsi2_out','SG_Vst_in')
                        
                        # PSS block 6
                        pss6_1 = ssf.tf_LEAD_LAG(pss['T1'], pss['T2'])
                        pss6_2 = ssf.tf_LEAD_LAG(pss['T3'], pss['T4'])
                        pss6_tf = pss['Ks1']*pss6_1*pss6_2
                        pss6_ss = ct.tf2ss(pss6_tf)
                        pss6_x  = ['SG'+str(num)+'_pss6_x1','SG'+str(num)+'_pss6_x2']                        
                        pss6_ss = ss(pss6_ss.A, pss6_ss.B, pss6_ss.C, pss6_ss.D, states = pss6_x, inputs = ['SG_Vst_in'], outputs = ['SG_Vst'])
                        
                        pss_x = pss1_x + pss2_x + pss4_x + pss6_x
                        
                        if connect_fun=='interconnect':
                            pss_ss = ct.interconnect([Pe_ss,pss1_ss,pss2_ss,pss3_ss,pss4_ss,pss5_ss,pss6_ss], states = pss_x, inputs = [we_pu,Te], outputs = ['SG_Vst'])

                            if save_ss_matrices == True:
                                save_ss_matrices_fun(pss_ss,
                                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                         f'{pss_ss=}'.split('=')[0]+str(n_sg))
                        elif connect_fun == 'append_and_connect':
                            pss_ss = interconnect.interconnect([Pe_ss,pss1_ss,pss2_ss,pss3_ss,pss4_ss,pss5_ss,pss6_ss], states = pss_x, inputs = [we_pu,Te], outputs = ['SG_Vst'])

                            
                            if save_ss_matrices == True:
                                save_ss_matrices_fun(pss_ss,
                                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                     f'{pss_ss=}'.split('=')[0]+str(n_sg))
                        
                        x_list.extend(pss_x)            
                        ss_list.append(pss_ss)                           
                        
        # GOVERNOR, TURBINE AND ROTOR SHAFT
        
        match row['govturb']:
            
            case 'IEEEG1':
                
                # Governor
                if mech['T1'] != 0:
                    Agov = np.array([[0, 1], 
                                    [-1/(mech['T1']*mech['T3']), -(mech['T1']+mech['T3'])/(mech['T1']*mech['T3'])]])        
                    Bgov = np.array([[0, 0, 0],
                                    [1, 1/mech['R'], -1/mech['R']]])        
                    Cgov = np.array([[1/(mech['T1']*mech['T3']), mech['T2']/(mech['T1']*mech['T3'])]])        
                    Dgov = np.array([[0, mech['Dt'], -mech['Dt']]])                    
                    gov_x = [gov_x1, gov_x2]                 
                          
                else:
                    Agov = np.array([[-1/mech['T3']]])        
                    Bgov = np.array([[1, 1/mech['R'], -1/mech['R']]])        
                    Cgov = np.array([[1/mech['T3']]])       
                    Dgov = np.array([[0, mech['Dt'], -mech['Dt']]])                    
                    gov_x = [gov_x1]
                                        
                gov_u = [Pref, 'SG_wref', we_pu]
                gov_y = ['SG_cv']                    
                gov_ss = ss(Agov, Bgov, Cgov, Dgov, inputs=gov_u, outputs=gov_y, states=gov_x)         
                ss_list.append(gov_ss)   
                x_list.extend(gov_x)                
                
                # Turbine
                turb_t4 = ct.tf(1,[mech['T4'], 1])
                turb_t5 = ct.tf(1,[mech['T5'], 1])
                turb_t6 = ct.tf(1,[mech['T6'], 1])
                turb_t7 = ct.tf(1,[mech['T7'], 1])   
                turb_tf = (mech['K7']+mech['K8'])*(turb_t7*turb_t6*turb_t5*turb_t4)+(mech['K5']+mech['K6'])*(turb_t6*turb_t5*turb_t4)+(mech['K3']+mech['K4'])*(turb_t5*turb_t4)+(mech['K1']+mech['K2'])*(turb_t4)            
                turb_ss = ct.tf2ss(turb_tf)
                
                x_turb = []
                for idx in range(1, len(turb_ss.A)+1):
                    x_turb.append(turb_x + str(idx))
                    
                turb_ss = ss(turb_ss.A, turb_ss.B, turb_ss.C, turb_ss.D, states = x_turb, inputs = ['SG_cv'], outputs = ['SG_Pm'])
                ss_list.append(turb_ss)   
                x_list.extend(x_turb) 
                
            case 'TANDEM-MULTI':
                
                # Governor
                ss_w_err      = ssf.SS_ERROR('SG_wref', we_pu, 'SG_w_err')    
                ss_w_droop    = ssf.SS_GAIN(1/mech['R'], 'SG_w_err', 'SG_Pm_err')
                ss_P_err      = ssf.SS_ADD(Pref, 'SG_Pm_err', 'SG_cv')    
                gov_in        = ['SG_wref', we_pu, Pref]
                gov_out       = ['SG_cv']
                
                if connect_fun=='interconnect':
                    gov_ss = ct.interconnect([ss_w_err, ss_w_droop, ss_P_err], inputs = gov_in, outputs = gov_out, check_unused = False) 

                    if save_ss_matrices == True:
                        save_ss_matrices_fun(gov_ss,
                                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                 f'{gov_ss=}'.split('=')[0]+str(n_sg))
                elif connect_fun == 'append_and_connect':
                    gov_ss = interconnect.interconnect([ss_w_err, ss_w_droop, ss_P_err], inputs = gov_in, outputs = gov_out, check_unused = False) 

                    
                    if save_ss_matrices == True:
                        save_ss_matrices_fun(gov_ss,
                                             'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                             f'{gov_ss=}'.split('=')[0]+str(n_sg))
                
                ss_list.append(gov_ss)
                
                # Turbine multi-mass
                Yturb_5 = 'SG' + str(num) + '_Yturb_5'
                Yturb_4 = 'SG' + str(num) + '_Yturb_4'
                Yturb_3 = 'SG' + str(num) + '_Yturb_3'
                Tt_2 = 'SG' + str(num) + '_Tt_2'
                Tt_3 = 'SG' + str(num) + '_Tt_3'
                Tt_4 = 'SG' + str(num) + '_Tt_4'
                Tt_5 = 'SG' + str(num) + '_Tt_5'
                x_turb5, ss_turb5 = SS_TURB(mech['T5'], mech['F5'], 'SG_cv', 5, num, turb_x) # STEAM CHEST (#5)     
                x_turb4, ss_turb4 = SS_TURB(mech['T4'], mech['F4'], Yturb_5, 4, num, turb_x) # REHEATER    (#4)      
                x_turb3, ss_turb3 = SS_TURB(mech['T3'], mech['F3'], Yturb_4, 3, num, turb_x) # REHEATER    (#3)       
                x_turb2, ss_turb2 = SS_TURB(mech['T2'], mech['F2'], Yturb_3, 2, num, turb_x) # REHEATER    (#2)
    
                x_turb = [x_turb5, x_turb4, x_turb3, x_turb2]
                turb_in = 'SG_cv'
                turb_out = [Tt_2, Tt_3, Tt_4, Tt_5]
                
                if connect_fun=='interconnect':
                    turb_ss = ct.interconnect([ss_turb5, ss_turb4, ss_turb3, ss_turb2], states = x_turb, inputs = turb_in, outputs = turb_out, check_unused = False) 

                    if save_ss_matrices == True:
                        save_ss_matrices_fun(turb_ss,
                                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                 f'{turb_ss=}'.split('=')[0]+str(n_sg))
                elif connect_fun == 'append_and_connect':
                    turb_ss = interconnect.interconnect([ss_turb5, ss_turb4, ss_turb3, ss_turb2], states = x_turb, inputs = turb_in, outputs = turb_out, check_unused = False) 

                    
                    if save_ss_matrices == True:
                        save_ss_matrices_fun(turb_ss,
                                             'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                             f'{turb_ss=}'.split('=')[0]+str(n_sg))
                
                ss_list.append(turb_ss)   
                x_list.extend(x_turb) 
                
                # Multi-mass shaft
                shaft_x, shaft_ss = SS_SHFTMM(mech, wb, num)
                ss_list.append(shaft_ss)   
                x_list.extend(shaft_x)               
                
            case 'TANDEM-SINGLE':

                # Governor
                ss_w_err      = ssf.SS_ERROR('SG_wref', we_pu, 'SG_w_err')    
                ss_w_droop    = ssf.SS_GAIN(1/mech['R'], 'SG_w_err', 'SG_Pm_err')
                ss_P_err      = ssf.SS_ADD(Pref, 'SG_Pm_err', 'SG_cv')    
                gov_in        = ['SG_wref', we_pu, Pref]
                gov_out       = ['SG_cv']
                
                if connect_fun=='interconnect':
                    gov_ss = ct.interconnect([ss_w_err, ss_w_droop, ss_P_err], inputs = gov_in, outputs = gov_out, check_unused = False) 

                    if save_ss_matrices == True:
                        save_ss_matrices_fun(gov_ss,
                                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                 f'{gov_ss=}'.split('=')[0]+str(n_sg))
                elif connect_fun == 'append_and_connect':
                    gov_ss = interconnect.interconnect([ss_w_err, ss_w_droop, ss_P_err], inputs = gov_in, outputs = gov_out, check_unused = False) 

                    
                    if save_ss_matrices == True:
                        save_ss_matrices_fun(gov_ss,
                                             'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                             f'{gov_ss=}'.split('=')[0]+str(n_sg))

                ss_list.append(gov_ss)  
                
                # Turbine single-mass
                turb_ss   = SS_TURBSM(mech['K_hp'], mech['tau_lp'], 'SG_cv', 'SG_Pm', turb_x)
                ss_list.append(turb_ss)   
                x_list.extend(turb_x)
            
        # ELECTRIC CIRCUIT
        
        if row['govturb'] == 'TANDEM-MULTI':
            
            # MULTI-MASS SG: Inertia equation outside electrical machine
            sem_x = [is_d, ik_d, if_d, is_q,  ik1_q, ik2_q] 
            sem_u = [vsgd_pu, vk_d,  vf_d,  vsgq_pu,  vk1_q,  vk2_q,  we_pu]
            sem_y = ['SG_isdg_pu', 'SG_ikd', 'SG_ifd', 'SG_isqg_pu', 'SG_ikq1', 'SG_ikq2', Te]
            
            sem_ss = SS_SEM(row, w0_pu, isq0, isd0, ikq10, ikq20, ifd0, ikd0, wb, num, sem_x, sem_u, sem_y)
            ss_list.append(sem_ss)   
            x_list.extend(sem_x)
            
        else:
            
            # SINGLE-MASS SG: Inertia equation inside electrical machine
            # Define matrices R7, M7, M7inv, N7
            R7 = np.array([[-Rs_pu, 0, 0, 0, 0, 0, 0],
                           [0, -Rs_pu, 0, 0, 0, 0, 0],
                           [0, 0, Rf_pu, 0, 0, 0, 0],
                           [0, 0, 0, R1d_pu, 0, 0, 0],
                           [0, 0, 0, 0, R1q_pu, 0, 0],
                           [0, 0, 0, 0, 0, R2q_pu, 0],
                           [0, 0, 0, 0, 0, 0, 0]])
        
            M7 = np.array([[-(Ll_pu+Lmq_pu), 0, 0, 0, Lmq_pu, Lmq_pu],
                           [0, -(Ll_pu+Lmd_pu), Lmd_pu, Lmd_pu, 0, 0],
                           [0, -Lmd_pu, Lfd_pu+Lmd_pu, Lmd_pu, 0, 0],
                           [0, -Lmd_pu, Lmd_pu, L1d_pu+Lmd_pu, 0, 0],
                           [-Lmq_pu, 0, 0, 0, L1q_pu+Lmq_pu, Lmq_pu],
                           [-Lmq_pu, 0, 0, 0, Lmq_pu, L2q_pu+Lmq_pu]]) / wb
        
            M7inv = np.linalg.inv(M7)
            M7inv = np.hstack((M7inv, np.zeros((6,1))))
            M7inv = np.vstack((M7inv, np.zeros((1,7))))
        
            N7 = np.array([[0, -w0_pu*(Ll_pu+Lmd_pu), w0_pu*Lmd_pu, w0_pu*Lmd_pu, 0, 0, -(Ll_pu+Lmd_pu)*isd0+Lmd_pu*ifd0],
                           [w0_pu*(Ll_pu+Lmq_pu), 0, 0, 0, -w0_pu*Lmq_pu, -w0_pu*Lmq_pu, (Ll_pu+Lmq_pu)*isq0],
                           [0, 0, 0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 0, 0, 0],
                           [0, 0, 0, 0, 0, 0, 0]])
        
            # Add the mechanical equation to the state space
            matA = np.vstack((np.zeros((6,7)), 
                              [-(isd0*(Lmq_pu-Lmd_pu)+Lmd_pu*ifd0), 
                               -(isq0*(Lmq_pu-Lmd_pu)), 
                               -isq0*Lmd_pu, 
                               -isq0*Lmd_pu, 
                               isd0*Lmq_pu, 
                               isd0*Lmq_pu, 
                               -Pm0/(w0_pu**2)])) / (2*H)
        
            matB = np.vstack((np.zeros((6,7)), 
                              np.hstack((np.zeros(6), 1/(2*H*w0_pu) )) ))
        
            Asem = -(np.dot(M7inv, (N7+R7))) + matA
            Bsem = M7inv + matB
        
            Csem = np.vstack((np.eye(7), 
                             [isd0*(Lmq_pu-Lmd_pu)+Lmd_pu*ifd0, 
                              isq0*(Lmq_pu-Lmd_pu), 
                              isq0*Lmd_pu, 
                              isq0*Lmd_pu, 
                              -isd0*Lmq_pu, 
                              -isd0*Lmq_pu, 
                              0]))
        
            Dsem = np.zeros((8, 7))      
   
            sem_x = [is_q, is_d, if_d, ik_d, ik1_q, ik2_q, we_pu] 
            sem_u = [vsgq_pu, vsgd_pu, vf_d, vk_d, vk1_q, vk2_q, 'SG_Pm']
            sem_y = ['SG_isqg_pu', 'SG_isdg_pu', 'SG_ifd', 'SG_ikd', 'SG_ikq1', 'SG_ikq2', we_pu, Te]
            sem_ss = ss(Asem, Bsem, Csem, Dsem, states = sem_x, inputs = sem_u, outputs = sem_y)
            ss_list.append(sem_ss)   
            x_list.extend(sem_x)     
        
        # LOCAL TO GLOBAL ROTATION (INV) - POC current
        
        # Change base of SG current: SG pu -> System pu
        Aisg_pu = np.empty(0)
        Bisg_pu = np.empty((0, 2))
        Cisg_pu = np.empty((0, 2))
        Disg_pu = np.array([[1, 0], [0, 1]])*Il2g   
        if (num==num_slk and element_slk == 'SG'):
            isg_pu_u = ['SG_isqg_pu','SG_isdg_pu']
        else:
            isg_pu_u = ['SG_isq_pu','SG_isd_pu']
        isg_pu_y = ['isg_q','isg_d']            
        isg_pu = ss(Aisg_pu, Bisg_pu, Cisg_pu, Disg_pu, inputs=isg_pu_u, outputs=isg_pu_y)        
        ss_list.append(isg_pu)        
        
        
        # PU to REAL ROTOR SPEED (w)
        
        # Espacio de estados wsg: pu -> real
        wsg_pu = ssf.SS_GAIN(wb, we_pu, w_real)
        ss_list.append(wsg_pu)        
        
        
        # ANGLE DEVIATION AND ROTATIONS
        
        # # Espacio de estados angulo 
        # Aang = np.array([[0]]) 
        # Bang = np.array([[1]]) 
        # Cang = np.array([[1]])
        # Dang = np.array([[0]])  
        # ang_x = [theta]
        # ang_u = [w_real]
        # ang_y = ['SG_th']
        # ang = ss(Aang, Bang, Cang, Dang, states = ang_x, inputs = ang_u, outputs = ang_y)        
        # ss_list.append(ang)  
        # x_list.extend(ang_x) 

        if not (num==num_slk and element_slk == 'SG'):      
            
            # Angle difference respect to system reference 
            Adang = np.array([[0]])   
            Bdang = np.array([[1, -1]])
            Cdang = np.array([[1]])
            Ddang = np.array([[0, 0]]) 
            dang_x = [e_theta]
            dang_u = [w_real, REF_w]
            dang_y = ['SG_e_th']
            dang = ss(Adang, Bdang, Cdang, Ddang, states = dang_x, inputs = dang_u, outputs = dang_y)              
            ss_list.append(dang)  
            x_list.extend(dang_x)   
            
            # Reference antitransformation for SG current (local -> global)
            Aigx_g = np.empty(0)
            Bigx_g = np.empty((0, 3))
            Cigx_g = np.empty((0, 2))
            Digx_g = np.array([[np.cos(e_theta0), np.sin(e_theta0), -np.sin(e_theta0)*isq0 + np.cos(e_theta0)*isd0],
                               [-np.sin(e_theta0), np.cos(e_theta0), -np.cos(e_theta0)*isq0 - np.sin(e_theta0)*isd0]])
            
            igx_g_u = ['SG_isqg_pu', 'SG_isdg_pu', 'SG_e_th']
            igx_g_y = ['SG_isq_pu', 'SG_isd_pu']
            igx_g = ss(Aigx_g, Bigx_g, Cigx_g, Digx_g, inputs = igx_g_u, outputs = igx_g_y)
            ss_list.append(igx_g) 
            
            # Reference transformation for SG voltage (global -> local)
            Avgx_g = np.empty(0)
            Bvgx_g = np.empty((0, 3))
            Cvgx_g = np.empty((0, 2))
            Dvgx_g = np.array([[np.cos(e_theta0), -np.sin(e_theta0), -np.sin(e_theta0)*vq0 - np.cos(e_theta0)*vd0],
                               [np.sin(e_theta0), np.cos(e_theta0), np.cos(e_theta0)*vq0 - np.sin(e_theta0)*vd0]])
            
            vgx_g_u = ['vsg_q', 'vsg_d', 'SG_e_th']
            vgx_g_y = ['vsg_qg', 'vsg_dg']            
            vgx_g = ss(Avgx_g, Bvgx_g, Cvgx_g, Dvgx_g, inputs = vgx_g_u, outputs = vgx_g_y)
            ss_list.append(vgx_g)
                    
        # BUILD COMPLETE MODEL  
        if (num==num_slk and element_slk == 'SG'):  
            input_vars = ['vg_q', 'vg_d']
            output_vars = ['ig_q', 'ig_d', w_real]
        else:
            input_vars = ['vg_q', 'vg_d', REF_w]
            output_vars = ['ig_q', 'ig_d', w_real]    
            
        if not row['govturb'] == 'no':
            input_vars.extend([Pref])
        
        if connect_fun=='interconnect':
            SS_SG = ct.interconnect(ss_list, states = x_list, inputs = input_vars, outputs = output_vars, check_unused = False) 
    
            if save_ss_matrices == True:
                save_ss_matrices_fun(SS_SG,
                                         'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                         f'{SS_SG=}'.split('=')[0]+str(n_sg))
        elif connect_fun == 'append_and_connect':
            SS_SG = interconnect.interconnect(ss_list, states = x_list, inputs = input_vars, outputs = output_vars, check_unused = False) 
            
            if save_ss_matrices == True:
                save_ss_matrices_fun(SS_SG,
                                     'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                     f'{SS_SG=}'.split('=')[0]+str(n_sg))
                
        # adapt inputs/outputs
        input_labels = SS_SG.input_labels
        input_labels[0] = vnXq
        input_labels[1] = vnXd
        SS_SG.input_labels = input_labels
        
        output_labels = SS_SG.output_labels
        output_labels[0] = iq
        output_labels[1] = id
        SS_SG.output_labels = output_labels
        
        if (num==num_slk and element_slk == 'SG'):  
            output_labels = SS_SG.output_labels
            output_labels[2] = REF_w
            SS_SG.output_labels = output_labels        
        
        # append ss to l_blocks
        l_blocks.append(SS_SG)
        l_states.extend(SS_SG.state_labels)
        # pd.DataFrame.to_excel(pd.DataFrame(SS_SG.A),'SS_SG'+str(num)+'_A_py.xlsx')
        n_sg=n_sg+1
    return l_blocks, l_states


# %% STATE-SPACE BLOCKS GENERATION FUNCTIONS

def SS_TURB(T,F,NAMEIN,STAGE,NUM,turb_x):
    
    Aturb  = np.array([[-1/T]]) 
    Bturb  = np.array([[1]]) 
    Cturb  = np.array([[1/T], [F/T]])  
    Dturb  = np.array([[0], [0]])  
    
    xturb = turb_x + str(STAGE)
    yturb = 'SG' + str(NUM) + '_Yturb_' + str(STAGE)
    Tturb = 'SG' + str(NUM) + '_Tt_' + str(STAGE)
     
    turb_u = NAMEIN
    turb_y = [yturb, Tturb]
    ss_turb   = ss(Aturb,Bturb,Cturb,Dturb, states = xturb, inputs = turb_u, outputs = turb_y)
    
    return xturb, ss_turb 


def SS_SHFTMM(mech, wb, NUM):
    
    H1 = mech['H1']
    H2 = mech['H2']
    H3 = mech['H3']
    H4 = mech['H4']
    H5 = mech['H5']
    K12 = mech['K12']
    K23 = mech['K23']
    K34 = mech['K34']
    K45 = mech['K45']
    D1 = mech['D1']
    D2 = mech['D2']
    D3 = mech['D3']
    D4 = mech['D4']
    D5 = mech['D5']
    
    Ashaft = np.array([[-D1/(2*H1), 0, 0, 0, 0, 1/(2*H1), 0, 0, 0],
                      [0, -D2/(2*H2), 0, 0, 0, -1/(2*H2), 1/(2*H2), 0, 0],
                      [0, 0, -D3/(2*H3), 0, 0, 0, -1/(2*H3), 1/(2*H3), 0],
                      [0, 0, 0, -D4/(2*H4), 0, 0, 0, -1/(2*H4), 1/(2*H4)],
                      [0, 0, 0, 0, -D5/(2*H5), 0, 0, 0, -1/(2*H5)],
                      [-K12*wb, K12*wb, 0, 0, 0, 0, 0, 0, 0],
                      [0, -K23*wb, K23*wb, 0, 0, 0, 0, 0, 0],
                      [0, 0, -K34*wb, K34*wb, 0, 0, 0, 0, 0],
                      [0, 0, 0, -K45*wb, K45*wb, 0, 0, 0, 0]])
    
    Bshaft = np.array([[-1/(2*H1), 0, 0, 0, 0],
                       [0, 1/(2*H2), 0, 0, 0],
                       [0, 0, 1/(2*H3), 0, 0],
                       [0, 0, 0, 1/(2*H4), 0],
                       [0, 0, 0, 0, 1/(2*H5)],
                       [0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0],
                       [0, 0, 0, 0, 0]])
    
    Cshaft = np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0]])
    
    Dshaft = np.array([[0, 0, 0, 0, 0]])
    
    deltaw1 = 'SG' + str(NUM) + '_deltaw1'
    deltaw2 = 'SG' + str(NUM) + '_deltaw2'
    deltaw3 = 'SG' + str(NUM) + '_deltaw3'
    deltaw4 = 'SG' + str(NUM) + '_deltaw4'
    deltaw5 = 'SG' + str(NUM) + '_deltaw5'
    ms2 = 'SG' + str(NUM) + '_ms2'
    ms3 = 'SG' + str(NUM) + '_ms3'
    ms4 = 'SG' + str(NUM) + '_ms4'
    ms5 = 'SG' + str(NUM) + '_ms5'
    we_pu = 'SG' + str(NUM) + '_w_pu'
    Te = 'SG' + str(NUM) + '_Te'
    Tt2 = 'SG' + str(NUM) + '_Tt_2'
    Tt3 = 'SG' + str(NUM) + '_Tt_3'
    Tt4 = 'SG' + str(NUM) + '_Tt_4'
    Tt5 = 'SG' + str(NUM) + '_Tt_5'
    
    shaft_x = [deltaw1, deltaw2, deltaw3, deltaw4, deltaw5, ms2, ms3, ms4, ms5]
    shaft_u = [Te, Tt2, Tt3, Tt4, Tt5]
    shaft_y = we_pu
    ss_shaft   = ss(Ashaft,Bshaft,Cshaft,Dshaft, states = shaft_x, inputs = shaft_u, outputs = shaft_y)
    
    return shaft_x, ss_shaft


def SS_TURBSM(K,tau,NAMEIN,NAMEOUT,turb_x):
    
    turb_tf = ct.tf([K*tau, 1],[tau, 1])
    ss_turb = ct.tf2ss(turb_tf)    
    ss_turb = ss(ss_turb.A, ss_turb.B, ss_turb.C, ss_turb.D, states = turb_x, inputs = NAMEIN, outputs = NAMEOUT)
    
    return ss_turb 

def SS_SEM(SG, we_0, isq0, isd0, ikq10, ikq20, ifd0, ikd0, wbase, NUM, sem_x, sem_u, sem_y):
    
    Rs = SG['Rs']
    Rkd = SG['R1d_pu']
    Rkq1 = SG['R1q_pu']
    Rkq2 = SG['R2q_pu']
    Rf_prime = SG['Rf_pu']
    Lmd = SG['Lmd_pu']
    Lmq = SG['Lmq_pu']
    Ll = SG['Ll_pu']
    Llkd = SG['L1d_pu']
    Llkq1 = SG['L1q_pu']
    Llkq2 = SG['L2q_pu']
    Llfd_prime = SG['Lfd_pu']

    Lmod = np.array([[-(Lmd+Ll), Lmd, Lmd, 0, 0, 0],     
                     [-Lmd, (Llkd+Lmd), Lmd, 0, 0, 0], 
                     [-Lmd, Lmd, (Llfd_prime+Lmd), 0, 0, 0],
                     [0, 0, 0, -(Lmq+Ll), Lmq, Lmq], 
                     [0, 0, 0, -Lmq, (Llkq1+Lmq), Lmq], 
                     [0, 0, 0, -Lmq, Lmq, (Llkq2+Lmq)]])/wbase
                     
    LmodInv = np.linalg.inv(Lmod)
    
    R8 = np.array([[-Rs, 0, 0, 0, 0, 0],
                   [0, Rkd, 0, 0, 0, 0],
                   [0, 0, (Rf_prime), 0, 0, 0],
                   [0, 0, 0, -Rs, 0, 0],
                   [0, 0, 0, 0, Rkq1, 0],
                   [0, 0, 0, 0, 0, Rkq2]])
    
    wLT = np.array([[0, 0, 0, we_0*(Lmq+Ll), -we_0*Lmq, -we_0*Lmq],
                    [0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0],
                    [-we_0*(Lmd+Ll), we_0*Lmd, we_0*Lmd, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0]])
    
    IL1 = np.array([[1, 0, 0, 0, 0, 0, -(isq0*(Lmq+Ll)-Lmq*ikq10 -Lmq*ikq20)],
                    [0, 1, 0, 0, 0, 0, 0],
                    [0, 0, 1, 0, 0, 0, 0],
                    [0, 0, 0, 1, 0, 0, -(-isd0*(Lmd+Ll)+Lmd*ikd0+Lmd*ifd0)],
                    [0, 0, 0, 0, 1, 0, 0],
                    [0, 0, 0, 0, 0, 1, 0]])

    Asem = -np.dot(LmodInv, (R8+wLT))
    Bsem = np.dot(LmodInv, IL1) 
    Csem = np.array([[1, 0, 0, 0, 0, 0],
                     [0, 1, 0, 0, 0, 0],
                     [0, 0, 1, 0, 0, 0],
                     [0, 0, 0, 1, 0, 0],
                     [0, 0, 0, 0, 1, 0],
                     [0, 0, 0, 0, 0, 1],
                     [(isq0*(-Lmd+Lmq)-Lmq*(ikq10 +ikq20)), Lmd*isq0, Lmd*isq0, (isd0*(-Lmd+Lmq)+Lmd*(ikd0+ifd0)), -Lmq*isd0, -Lmq*isd0]])
                     
    Dsem = np.zeros((7,7))        
    sem_ss = ss(Asem, Bsem, Csem, Dsem, states = sem_x, inputs = sem_u, outputs = sem_y)
    
    return sem_ss