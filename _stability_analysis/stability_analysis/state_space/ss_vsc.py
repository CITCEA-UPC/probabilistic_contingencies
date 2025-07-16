import numpy as np
import control as ct
from control.matlab import ss
from stability_analysis.state_space import ss_functions as ssf
import pandas as pd
from stability_analysis.state_space import interconnect

def save_ss_matrices_fun(ss,path,filename):
    pd.DataFrame.to_csv(pd.DataFrame(ss.A),path+filename+'_A.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.B),path+filename+'_B.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.C),path+filename+'_C.csv',index=False,header=False)
    pd.DataFrame.to_csv(pd.DataFrame(ss.D),path+filename+'_D.csv',index=False,header=False)


def generate_linearization_point_VSC(d_grid):
    
    def rotation_vect(x, y, angle):
        x_rot = x * np.cos(angle) - y * np.sin(angle)
        y_rot = x * np.sin(angle) + y * np.cos(angle)
        return x_rot, y_rot
    
    T_VSC = d_grid['T_VSC']
    T_global = d_grid['T_global']    
    lp_VSC = T_VSC[['number','bus']].copy()
    
    for idx,row in T_VSC.iterrows():
        
        Svsc = row['Sb']  # VSC rated power, VSC power base
        Sb = T_global[T_global['Area'] == row['Area']]['Sb'].iloc[0]  # System power base
        delta_slk = T_global[T_global['Area'] == row['Area']]['delta_slk'].iloc[0]  
        
        # VSC parameters
        Rtr = row['Rtr']
        Xtr = row['Xtr']
        Rc = row['Rc']
        Xc = row['Xc']
        Cac = row['Cac']
        Rac = row['Rac']
        wb = row['wb']
        
        # Data from the power-flow
        delta0 = row['theta'] * (np.pi / 180)
        Vg = row['V']/np.sqrt(3)/row['Vbpu_l2g']  # PCC line-line voltage RMS
        Pvsc0 = row['P'] * (Sb / Svsc)
        Qvsc0 = row['Q'] * (Sb / Svsc)
        
        mode = row['mode']
        
        match mode:
            
            case 'GFOL':
  
                # Calculation of voltages and currents (REF: NET-POC)
                if Cac != 0:
                    # RLC filter
                     Ig = np.conj((Pvsc0 + 1j*Qvsc0) / (3*Vg))  # Transformer current
                     phi = np.arctan2(np.imag(Ig), np.real(Ig))  # angle of transformer current
                     U = Vg + Ig * (Rtr + 1j*Xtr)  # Voltage at capacitor bus
                     theta_in = np.arctan2(np.imag(U), np.real(U))  # angle between POC and capacitor bus
                     Icap = U / (Rac - 1j/(wb*Cac))  # current through capacitor
                     Ucap = U - Rac * Icap
                     theta_ucap = np.arctan2(np.imag(Ucap), np.real(Ucap))
                     Is = Ig + Icap  # converter filter current
                     phi_is = np.arctan2(np.imag(Is), np.real(Is))
                     Vc = U + Is * (Rc + 1j*Xc)  # voltage applied by the converter
                     theta_vc = np.arctan2(np.imag(Vc), np.real(Vc))                      
                else:
                    # RL filter (no capacitor)
                    Is = np.conj((Pvsc0 + 1j * Qvsc0) / (3 * Vg))  # converter filter current
                    phi_is = np.angle(Is)  # angle of converter filter current
                    U = Vg + Is * (Rtr + 1j * Xtr)  # Voltage at capacitor bus
                    theta_in = np.angle(U)  # angle between POC and capacitor bus                
                    Vc = U + Is * (Rc + 1j * Xc)  # voltage applied by the converter
                    theta_vc = np.angle(Vc)
                    
                    # Additional variables
                    Ig = Is
                    phi = phi_is
                    Ucap = U
                    theta_ucap = 0
                    
  
            case 'GFOR':
    
                # Calculation of voltages and currents (REF: NET-POC)
                Ig = np.conj((Pvsc0 + 1j*Qvsc0) / (3*Vg))  # Transformer current
                phi = np.arctan2(np.imag(Ig), np.real(Ig))  # angle of transformer current
                U = Vg + Ig * (Rtr + 1j*Xtr)  # Voltage at capacitor bus
                theta_in = np.arctan2(np.imag(U), np.real(U))  # angle between POC and capacitor bus
                Icap = U / (Rac - 1j/(wb*Cac))  # current through capacitor
                Ucap = U - Rac * Icap
                theta_ucap = np.arctan2(np.imag(Ucap), np.real(Ucap))
                Is = Ig + Icap  # converter filter current
                phi_is = np.arctan2(np.imag(Is), np.real(Is))
                Vc = U + Is * (Rc + 1j*Xc)  # voltage applied by the converter
                theta_vc = np.arctan2(np.imag(Vc), np.real(Vc))
                    
        # Calculate angles
        delta_bus = delta0 - delta_slk  # NET-POC
        e_theta0 = delta0 + theta_in - delta_slk  # VSC-POC 
        
        
        # Initial values in qd referenced to GLOBAL REF (add delta_bus: delta0-delta_slk)
        
        # qd GRID voltage (REF:GLOBAL)
        vg_q0 = np.abs(Vg) * np.cos(delta_bus) * np.sqrt(2)
        vg_d0 = -np.abs(Vg) * np.sin(delta_bus) * np.sqrt(2)
        
        # qd VSC-PCC voltage (REF:GLOBAL)
        u_q0 = np.abs(U) * np.cos(e_theta0) * np.sqrt(2)
        u_d0 = -np.abs(U) * np.sin(e_theta0) * np.sqrt(2)
        
        # qd TRAFO current (REF:GLOBAL)
        ig_q0 = np.abs(Ig) * np.cos(delta_bus + phi) * np.sqrt(2)
        ig_d0 = -np.abs(Ig) * np.sin(delta_bus + phi) * np.sqrt(2)
        
        # qd VSC current (REF:GLOBAL)
        is_q0 = np.abs(Is) * np.cos(delta_bus + phi_is) * np.sqrt(2)
        is_d0 = -np.abs(Is) * np.sin(delta_bus + phi_is) * np.sqrt(2)
        
        # qd converter voltage (REF:GLOBAL)
        vc_q0 = np.abs(Vc) * np.cos(delta_bus + theta_vc) * np.sqrt(2)
        vc_d0 = -np.abs(Vc) * np.sin(delta_bus + theta_vc) * np.sqrt(2)
        
        # Capacitor voltage GLOBAL
        ucap_q0 = np.abs(Ucap) * np.cos(delta_bus + theta_ucap) * np.sqrt(2)
        ucap_d0 = -np.abs(Ucap) * np.sin(delta_bus + theta_ucap) * np.sqrt(2)
        
        
        # Initial values in qd referenced to VSC REF
                
        # qd converter voltage (REF:LOCAL)
        vc_qc0, vc_dc0 = rotation_vect(np.real(Vc) * np.sqrt(2), -np.imag(Vc) * np.sqrt(2), theta_in)
        
        # qd VSC-POC voltage (REF:LOCAL)
        u_qc0, u_dc0 = rotation_vect(np.real(U) * np.sqrt(2), -np.imag(U) * np.sqrt(2), theta_in)
        
        # qd VSC-POC voltage (REF:LOCAL)
        is_qc0, is_dc0 = rotation_vect(np.real(Is) * np.sqrt(2), -np.imag(Is) * np.sqrt(2), theta_in)
        
        # Store linearization point in DataFrame
        lp_VSC.at[idx, 'ig_q0'] = ig_q0  # pu
        lp_VSC.at[idx, 'ig_d0'] = ig_d0  # pu
        lp_VSC.at[idx, 'is_q0'] = is_q0  # pu
        lp_VSC.at[idx, 'is_d0'] = is_d0  # pu
        lp_VSC.at[idx, 'u_q0'] = u_q0  # pu
        lp_VSC.at[idx, 'u_d0'] = u_d0  # pu
        lp_VSC.at[idx, 'ucap_q0'] = ucap_q0  # pu
        lp_VSC.at[idx, 'ucap_d0'] = ucap_d0  # pu
        lp_VSC.at[idx, 'u_qc0'] = u_qc0  # pu
        lp_VSC.at[idx, 'u_dc0'] = u_dc0  # pu
        lp_VSC.at[idx, 'vc_qc0'] = vc_qc0  # pu
        lp_VSC.at[idx, 'vc_dc0'] = vc_dc0  # pu
        lp_VSC.at[idx, 'vg_q0'] = vg_q0  # pu
        lp_VSC.at[idx, 'vg_d0'] = vg_d0  # pu
        lp_VSC.at[idx, 'is_cq0'] = is_qc0  # pu
        lp_VSC.at[idx, 'is_cd0'] = is_dc0  # pu
        lp_VSC.at[idx, 'w0_pu'] = 1  # pu
        lp_VSC.at[idx, 'w0'] = row['wb']  # rad/s
        lp_VSC.at[idx, 'etheta0'] = e_theta0  # rad    
                    
    return lp_VSC




def generate_VSC_pu(l_blocks, l_states, d_grid, lp_VSC, connect_fun='append_and_connect',save_ss_matrices=False):  
    
    T_VSC = d_grid['T_VSC']
    T_global = d_grid['T_global']
    
    n_vsc=0
    for idx, row in T_VSC.iterrows():  
        
        ss_list = [] # Create list to store SG subsystems blocks 
        x_list = [] # Creat elist to store SG subsystems states
        num = row['number']
        bus = row['bus']
        num_slk = T_global[T_global['Area'] == row['Area']]['num_slk'].iloc[0]
        element_slk = T_global[T_global['Area'] == row['Area']]['ref_element'].iloc[0]
        REF_w = 'REF_w'
        
        # Base values and conversions
        
        Zl2g = row['Zbpu_l2g']
        Sl2g = row['Sbpu_l2g']
        Vl2g = row['Vbpu_l2g']
        Il2g = row['Ibpu_l2g']
        wb = row['wb']
        
        # Linearization point
        
        ig_q0 = lp_VSC.loc[idx, 'ig_q0']
        ig_d0 = lp_VSC.loc[idx, 'ig_d0']
        is_q0 = lp_VSC.loc[idx, 'is_q0']
        is_d0 = lp_VSC.loc[idx, 'is_d0']
        u_q0 = lp_VSC.loc[idx, 'u_q0']
        u_d0 = lp_VSC.loc[idx, 'u_d0']
        ucap_q0 = lp_VSC.loc[idx, 'ucap_q0']
        ucap_d0 = lp_VSC.loc[idx, 'ucap_d0']
        vc_qc0 = lp_VSC.loc[idx, 'vc_qc0']
        vc_dc0 = lp_VSC.loc[idx, 'vc_dc0']
        w0 = lp_VSC.loc[idx, 'w0']
        e_theta0 = lp_VSC.loc[idx, 'etheta0']              
        
        
        mode = row['mode']        
        match mode:
            
            case 'GFOL':  
                                
                # Set names of state variables, inputs and outputs 
                
                # Frequency droop
                fdroop_x = 'GFOL' + str(num) + '_w_filt_x'
                P_ref = 'GFOL' + str(num) + '_P_ref'
                omega_ref = 'GFOL' + str(num) + '_omega_ref'
                
                # Voltage droop
                udroop_x = 'GFOL' + str(num) + '_q_filt_x'
                Q_ref = 'GFOL' + str(num) + '_Q_ref'
                Umag_ref = 'GFOL' + str(num) + '_Umag_ref'
                
                # LC:
                is_q = 'GFOL' + str(num) + '_is_q'
                is_d = 'GFOL' + str(num) + '_is_d'
                ucap_q = 'GFOL' + str(num) + '_ucap_q_x'
                ucap_d = 'GFOL' + str(num) + '_ucap_d_x'
                is_q_x = 'GFOL' + str(num) + '_is_q_x'
                is_d_x = 'GFOL' + str(num) + '_is_d_x'
                u_q = 'GFOL' + str(num) + '_u_q'
                u_d = 'GFOL' + str(num) + '_u_d'
                
                # Trafo
                ig_q = 'GFOL' + str(num) + '_ig_q'
                ig_d = 'GFOL' + str(num) + '_ig_d'
                ig_q_x = 'GFOL' + str(num) + '_ig_q_x'
                ig_d_x = 'GFOL' + str(num) + '_ig_d_x'
                
                # Power control:
                p_x = 'GFOL' + str(num) + '_Ke_P'
                q_x = 'GFOL' + str(num) + '_Ke_Q'
                
                # AC side current control
                is_q_x1 = 'GFOL' + str(num) + '_Ke_is_q'
                is_q_x2 = 'GFOL' + str(num) + '_Ke_is_d'
                is_qc_ref = 'GFOL' + str(num) + '_is_qc_ref'
                is_dc_ref = 'GFOL' + str(num) + '_is_dc_ref'
                
                # omega to angle VSC (1/s)
                angle_vsc_x = 'GFOL' + str(num) + '_angle_vsc_x'
                w_vsc = 'GFOL' + str(num) + '_w'
                
                # PLL
                pll_x = 'GFOL' + str(num) + '_pll_x'
                
                # omega to angle grid (1/s)
                etheta_x = 'GFOL' + str(num) + '_etheta_x'
                
                # in/out voltages & currents in grid (global) ref
                vnXq = 'NET_vn' + str(bus) + 'q'
                vnXd = 'NET_vn' + str(bus) + 'd'
                iq = 'GFOL' + str(num) + '_iq'
                id = 'GFOL' + str(num) + '_id'                
            
                # Parameters
 
                # Transformer
                Rtr = row['Rtr']
                Ltr = row['Ltr']
                
                # RL filter
                Rc = row['Rc']
                Lc = row['Lc']
                Cac = row['Cac']
                Rac = row['Rac']
                
                # Current control
                kp_s = row['kp_s']
                ki_s = row['ki_s']
                
                # PLL
                kp_pll = row['kp_pll']
                ki_pll = row['ki_pll']
                
                # Power loops
                kp_P = row['kp_P']
                ki_P = row['ki_P']
                kp_Q = row['kp_Q']
                ki_Q = row['ki_Q']
                
                tau_droop_f = row['tau_droop_f']
                k_droop_f = row['k_droop_f']
                tau_droop_u = row['tau_droop_u']
                k_droop_u = row['k_droop_u']           
                
                # if Cac == 0:
                #     raise RuntimeError("Cac of GFOL cannot be set to zero.")                
                
                # ROTATION MATRICES
                
                # REF INVERSE transform: vc_c to vc (local -> global)
                vc_l2g = ssf.SS_ROTATE(e_theta0, vc_qc0, vc_dc0, "l2g", ['vc_qc','vc_dc', 'e_theta'], ['vc_q','vc_d'])
                ss_list.append(vc_l2g) 
                
                # REF transform: is to is_c (global -> local)
                is_g2l = ssf.SS_ROTATE(e_theta0, is_q0, is_d0, "g2l", [is_q, is_d, 'e_theta'], ['is_qc', 'is_dc'])
                ss_list.append(is_g2l)               
                
                # REF transform: u to u_c (global -> local)
                u_g2l = ssf.SS_ROTATE(e_theta0, u_q0, u_d0, "g2l", [u_q, u_d, 'e_theta'], ['u_qc','u_dc'])
                ss_list.append(u_g2l)               
                
                
                # BASE CHANGE
                
                # Change base of voltage: system -> vsc
                Av_pu = np.empty(0)
                Bv_pu = np.empty((0, 2))
                Cv_pu = np.empty((0, 2))
                Dv_pu = np.array([[1/Vl2g, 0], [0, 1/Vl2g]])
                        
                v_pu_u = ['vg_sys_q','vg_sys_d']            
                v_pu_y = ['vg_q','vg_d']                 
                v_pu = ss(Av_pu, Bv_pu, Cv_pu, Dv_pu, inputs=v_pu_u, outputs=v_pu_y)       
                ss_list.append(v_pu)
                
                # Change base of current: VSC pu -> System pu
                Ai_pu = np.empty(0)
                Bi_pu = np.empty((0, 2))
                Ci_pu = np.empty((0, 2))
                Di_pu = np.array([[1, 0], [0, 1]])*Il2g 
                
                if Cac != 0: # RLC filter             
                    i_pu_u = [ig_q, ig_d]                              
                else: # RL filter
                    i_pu_u = [is_q,is_d]
                         
                i_pu_y = [iq, id]     
                i_pu = ss(Ai_pu, Bi_pu, Ci_pu, Di_pu, inputs=i_pu_u, outputs=i_pu_y)        
                ss_list.append(i_pu)  


                # PLL, omega and angle
                
                # PLL control block
                Apll = np.array([[0]]) 
                Bpll = np.array([[1]]) 
                Cpll = np.array([[-ki_pll]])
                Dpll = np.array([[-kp_pll]])  
                
                pll_x = [pll_x]
                pll_u = ['u_dc']
                pll_y = ['w_vsc_pu']
                
                pll = ss(Apll, Bpll, Cpll, Dpll, states = pll_x, inputs = pll_u, outputs = pll_y)        
                ss_list.append(pll)  
                x_list.extend(pll_x) 
                
                # Espacio de estados wsg: pu -> real
                w_pu = ssf.SS_GAIN(wb, 'w_vsc_pu', w_vsc)
                ss_list.append(w_pu)             
                
                # Angle deviation from system reference
                Adang = np.array([[0]])   
                Bdang = np.array([[1, -1]])
                Cdang = np.array([[1]])
                Ddang = np.array([[0, 0]]) 
                
                dang_x = [etheta_x]
                dang_u = [w_vsc, REF_w]
                dang_y = ['e_theta']
                
                dang = ss(Adang, Bdang, Cdang, Ddang, states = dang_x, inputs = dang_u, outputs = dang_y)              
                ss_list.append(dang)  
                x_list.extend(dang_x) 
                
                
                # OUTTER LOOPS
                
                # Frequency droop with low-pass filter on omega
                Afdroop = np.array([[-1/tau_droop_f]])   
                Bfdroop = np.array([[0, 1]])
                Cfdroop = np.array([[-k_droop_f/tau_droop_f/wb]])
                Dfdroop = np.array([[+k_droop_f/wb, 0]]) 
                
                fdroop_x = [fdroop_x]
                fdroop_u = [omega_ref, w_vsc]
                fdroop_y = [P_ref]
                
                fdroop = ss(Afdroop, Bfdroop, Cfdroop, Dfdroop, states = fdroop_x, inputs = fdroop_u, outputs = fdroop_y)              
                ss_list.append(fdroop)  
                x_list.extend(fdroop_x)                                   
    
                # Voltage magnitude
                Au = np.empty(0)
                Bu = np.empty((0, 2))
                Cu = np.empty((0, 2))
                Du = np.array([[u_q0/np.sqrt(u_q0**2 + u_d0**2), u_d0/np.sqrt(u_q0**2 + u_d0**2)]])       
                
                u_u = [u_q, u_d]
                u_y = ['Umag']    
                
                ss_u = ss(Au, Bu, Cu, Du, inputs=u_u, outputs=u_y)        
                ss_list.append(ss_u)
                
                # Voltage droop with low-pass filter in v
                Audroop = np.array([[-1/tau_droop_u]])   
                Budroop = np.array([[0, 1]])
                Cudroop = np.array([[-k_droop_u/tau_droop_u]])
                Dudroop = np.array([[+k_droop_u, 0]]) 
               
                udroop_x = [udroop_x]
                udroop_u = [Umag_ref, 'Umag']
                udroop_y = [Q_ref]
                
                udroop = ss(Audroop, Budroop, Cudroop, Dudroop, states = udroop_x, inputs = udroop_u, outputs = udroop_y)              
                ss_list.append(udroop)  
                x_list.extend(udroop_x) 
                
                # PQ control
                
                # P control
                Ap = np.array([[0]])
                Bp = np.array([[1, -3/2*u_q0, -3/2*u_d0, -3/2*ig_q0, -3/2*ig_d0]])
                Cp = np.array([[ki_P]])
                Dp = np.array([[kp_P, -3/2*u_q0*kp_P, -3/2*u_d0*kp_P, -3/2*ig_q0*kp_P, -3/2*ig_d0*kp_P]])        
                p_x = [p_x]
                
                # Q control
                Aq = np.array([[0]])
                Bq = np.array([[1, 3/2*u_d0, -3/2*u_q0, -3/2*ig_d0, 3/2*ig_q0]])
                Cq = np.array([[ki_Q]])
                Dq = np.array([[kp_Q, 3/2*u_d0*kp_Q, -3/2*u_q0*kp_Q, -3/2*ig_d0*kp_Q, 3/2*ig_q0*kp_Q]])
                q_x = [q_x]                
                
                if Cac != 0: # RLC filter
                
                    # P control                    
                    p_u = [P_ref, ig_q, ig_d, u_q, u_d]
                    p_y = [is_qc_ref]
                    
                    ss_p = ss(Ap, Bp, Cp, Dp, states = p_x, inputs = p_u, outputs = p_y)              
                    ss_list.append(ss_p)  
                    x_list.extend(p_x) 
                    
                    # Q control 
                    q_u = [Q_ref, ig_q, ig_d, u_q, u_d]
                    q_y = [is_dc_ref]
                    
                    ss_q = ss(Aq, Bq, Cq, Dq, states=q_x, inputs=q_u, outputs=q_y)
                    ss_list.append(ss_q)
                    x_list.extend(q_x)            
                           
                else: # RL filter
                
                    # P control                    
                    p_u = [P_ref, is_q, is_d, u_q, u_d]
                    p_y = [is_qc_ref]
                    
                    ss_p = ss(Ap, Bp, Cp, Dp, states = p_x, inputs = p_u, outputs = p_y)              
                    ss_list.append(ss_p)  
                    x_list.extend(p_x) 
                    
                    # Q control 
                    q_u = [Q_ref, is_q, is_d, u_q, u_d]
                    q_y = [is_dc_ref]
                    
                    ss_q = ss(Aq, Bq, Cq, Dq, states=q_x, inputs=q_u, outputs=q_y)
                    ss_list.append(ss_q)
                    x_list.extend(q_x)     
                                        
                                                    
                # AC side current control
                Ais = np.array([[0, 0],
                                [0, 0]])
                
                Bis = np.array([[1, 0, -1, 0, 0, 0],
                                [0, 1, 0, -1, 0, 0]])
                
                Cis = np.array([[ki_s, 0],
                                [0, ki_s]])
                
                Dis = np.array([[kp_s, 0, -kp_s, wb*Lc, 1, 0],
                                [0, kp_s, -wb*Lc, -kp_s, 0, 1]])
                
                is_x = [is_q_x1, is_q_x2]
                is_u = [is_qc_ref,  is_dc_ref, 'is_qc', 'is_dc', 'u_qc', 'u_dc']
                is_y = ['vc_qc', 'vc_dc']   
                
                is_ss = ss(Ais, Bis, Cis, Dis, states=is_x, inputs=is_u, outputs=is_y)                
                ss_list.append(is_ss)  
                x_list.extend(is_x)
   
    
               # RL/RLC FILTER AND TRANSFORMER
  
                if Cac != 0: # RLC filter
                
                    # Transformer 
                    Atr = np.array([[-(Rtr)/(Ltr), -w0], 
                                    [w0, -(Rtr)/(Ltr)]])        
                    Btr = np.array([[1/Ltr, 0, -1/Ltr, 0],
                                    [0, 1/Ltr, 0, -1/Ltr]])        
                    Ctr = np.array([[1, 0], 
                                    [0, 1]])        
                    Dtr = np.array([[0, 0, 0, 0],
                                    [0, 0, 0, 0]])
                    
                    tr_x = [ig_q_x, ig_d_x]
                    tr_u = [u_q, u_d,'vg_q','vg_d']
                    tr_y = [ig_q, ig_d]  
                    
                    tr_ss = ss(Atr, Btr, Ctr, Dtr, inputs=tr_u, outputs=tr_y, states=tr_x)        
                    ss_list.append(tr_ss)   
                    x_list.extend(tr_x)
                    
                    # LC
                    Alc = np.array([[-(Rc + Rac)/Lc, -wb, -1/Lc, 0],
                                    [wb, -(Rc + Rac)/Lc, 0, -1/Lc],
                                    [1/Cac, 0, 0, -wb],
                                    [0, 1/Cac, wb, 0]])
                    
                    Blc = np.array([[1/Lc, 0, Rac/Lc, 0, -is_d0],
                                    [0, 1/Lc, 0, Rac/Lc, + is_q0],
                                    [0, 0, -1/Cac, 0, -ucap_d0],
                                    [0, 0, 0, -1/Cac, ucap_q0]])
                    
                    Clc = np.array([[1, 0, 0, 0],
                                    [0, 1, 0, 0],
                                    [Rac, 0, 1, 0],
                                    [0, Rac, 0, 1]])
                    
                    Dlc = np.array([[0, 0, 0, 0, 0],
                                    [0, 0, 0, 0, 0],
                                    [0, 0, -Rac, 0, 0],
                                    [0, 0, 0, -Rac, 0]])
                    
                    lc_x = [is_q_x, is_d_x, ucap_q, ucap_d]
                    lc_u = ['vc_q', 'vc_d', ig_q, ig_d, REF_w]
                    lc_y = [is_q, is_d, u_q, u_d]  
                    
                    Lc_ss = ss(Alc, Blc, Clc, Dlc, states=lc_x, inputs=lc_u, outputs=lc_y)                    
                    ss_list.append(Lc_ss)
                    x_list.extend(lc_x)             
                                
                else: # RL filter                         
                
                    # plant: RL filter and trafo --> ALGEBRAIC LOOP
                    Arl = np.array([[-(Rc + Rtr)/(Lc + Ltr), -wb],
                                  [wb, -(Rc + Rtr)/(Lc + Ltr)]])
                    
                    Brl = np.array([[1/(Lc + Ltr), 0, -1/(Lc + Ltr), 0],
                                    [0, 1/(Lc + Ltr), 0, -1/(Lc + Ltr)]])
                    
                    Crl = np.array([[1, 0],
                                    [0, 1],
                                    [(Lc * Rtr - Ltr * (Rc))/(Lc + Ltr), 0],
                                    [0, (Lc * Rtr - Ltr * (Rc))/(Lc + Ltr)]])
                    
                    Drl = np.array([[0, 0, 0, 0],
                                    [0, 0, 0, 0],
                                    [Ltr/(Lc + Ltr), 0, Lc/(Lc + Ltr), 0],
                                    [0, Ltr/(Lc + Ltr), 0, Lc/(Lc + Ltr)]])
                    
                    rl_x = [is_q_x, is_d_x]
                    rl_u = ['vc_q', 'vc_d', 'vg_q', 'vg_d']
                    rl_y = [is_q, is_d, u_q, u_d]  
                    
                    rl = ss(Arl, Brl, Crl, Drl, states=rl_x, inputs=rl_u, outputs=rl_y)                    
                    ss_list.append(rl) 
                    x_list.extend(rl_x)         
                    
    
                # BUILD COMPLETE MODEL  

                input_vars = ['vg_sys_q','vg_sys_d',REF_w]
                output_vars = [iq, id, w_vsc]    

                if connect_fun=='interconnect':
                    SS_GFOL = ct.interconnect(ss_list, states = x_list, inputs = input_vars, outputs = output_vars, check_unused = False) 

                    if save_ss_matrices == True:
                        save_ss_matrices_fun(SS_GFOL,
                                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                 f'{SS_GFOL=}'.split('=')[0]+str(n_vsc))
                elif connect_fun == 'append_and_connect':
                    SS_GFOL = interconnect.interconnect(ss_list, states = x_list, inputs = input_vars, outputs = output_vars, check_unused = False) 

                    
                    if save_ss_matrices == True:
                        save_ss_matrices_fun(SS_GFOL,
                                             'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                             f'{SS_GFOL=}'.split('=')[0]+str(n_vsc))                                       
                        
                # adapt inputs/outputs
                input_labels = SS_GFOL.input_labels
                input_labels[0] = vnXq
                input_labels[1] = vnXd
                SS_GFOL.input_labels = input_labels                   
                
                # append ss to l_blocks
                l_blocks.append(SS_GFOL)
                l_states.extend(SS_GFOL.state_labels)
                # pd.DataFrame.to_excel(pd.DataFrame(SS_GFOL.A),'SS_GFOL'+str(num)+'_A_py.xlsx')


                
            case 'GFOR':
        
                 # Set names of state variables, inputs and outputs 
                 
                # Frequency droop
                fdroop_x1 = 'GFOR' + str(num) + '_p_filt_x'
                P_ref = 'GFOR' + str(num) + '_P_ref'
                
                # Voltage droop
                udroop_x1 = 'GFOR' + str(num) + '_q_filt_x'
                Q_ref = 'GFOR' + str(num) + '_Q_ref'
                
                # LC:
                is_q = 'GFOR' + str(num) + '_is_q'
                is_d = 'GFOR' + str(num) + '_is_d'
                ucap_q = 'GFOR' + str(num) + '_ucap_q_x'
                ucap_d = 'GFOR' + str(num) + '_ucap_d_x'
                is_q_x = 'GFOR' + str(num) + '_is_q_x'
                is_d_x = 'GFOR' + str(num) + '_is_d_x'
                u_q = 'GFOR' + str(num) + '_u_q'
                u_d = 'GFOR' + str(num) + '_u_d'
                
                # AC side voltage control:
                u_q_x1 = 'GFOR' + str(num) + '_Ke_u_q'
                u_d_x2 = 'GFOR' + str(num) + '_Ke_u_d'
                u_qc_ref = 'GFOR' + str(num) + '_u_qc_ref'
                u_dc_ref = 'GFOR' + str(num) + '_u_dc_ref'
                
                # AC side current control
                is_q_x1 = 'GFOR' + str(num) + '_Ke_is_q'
                is_q_x2 = 'GFOR' + str(num) + '_Ke_is_d'
                is_qc_ref = 'GFOR' + str(num) + '_is_qc_ref'
                is_dc_ref = 'GFOR' + str(num) + '_is_dc_ref'
                
                # omega to angle VSC (1/s)
                angle_vsc_x = 'GFOR' + str(num) + '_angle_vsc_x'
                w_vsc = 'GFOR' + str(num) + '_w'
                
                # omega to angle grid (1/s)
                etheta_x = 'GFOR' + str(num) + '_etheta_x'
                
                # AC voltage feedforward filter
                f_igd_x1 = 'GFOR' + str(num) + '_igd_ff_x'
                f_igq_x1 = 'GFOR' + str(num) + '_igq_ff_x'
                
                # Trafo
                ig_q = 'GFOR' + str(num) + '_ig_q'
                ig_d = 'GFOR' + str(num) + '_ig_d'
                ig_q_x = 'GFOR' + str(num) + '_ig_q_x'
                ig_d_x = 'GFOR' + str(num) + '_ig_d_x'
                
                # in/out voltages & currents in grid (global) ref
                vnXq = 'NET_vn' + str(bus) + 'q'
                vnXd = 'NET_vn' + str(bus) + 'd'
                iq = 'GFOR' + str(num) + '_iq'
                id = 'GFOR' + str(num) + '_id'
               
                # Parameters                 
 
                # Transformer
                Rtr = row['Rtr']
                Ltr = row['Ltr']
                
                # RL filter
                Rc = row['Rc']
                Lc = row['Lc']
                Cac = row['Cac']
                Rac = row['Rac']
                
                # Current control
                kp_s = row['kp_s']
                ki_s = row['ki_s']
                
                # AC voltage control
                kp_vac = row['kp_vac']
                ki_vac = row['ki_vac']
                
                # Feedforward filters
                tau_u = row['tau_u']
                tau_ig = row['tau_ig']
                
                # Droop parameters
                tau_droop_f = row['tau_droop_f']
                k_droop_f = row['k_droop_f']
                tau_droop_u = row['tau_droop_u']
                k_droop_u = row['k_droop_u']                
                   
        
                # BASE CHANGE      
                
                # Change base of voltage: system -> vsc
                Av_pu = np.empty(0)
                Bv_pu = np.empty((0, 2))
                Cv_pu = np.empty((0, 2))
                Dv_pu = np.array([[1/Vl2g, 0], [0, 1/Vl2g]])
                        
                v_pu_u = ['vg_sys_q','vg_sys_d']            
                v_pu_y = ['vg_q','vg_d']     
                
                v_pu = ss(Av_pu, Bv_pu, Cv_pu, Dv_pu, inputs=v_pu_u, outputs=v_pu_y)       
                ss_list.append(v_pu)
                
                # Change base of current: VSC pu -> System pu
                Ai_pu = np.empty(0)
                Bi_pu = np.empty((0, 2))
                Ci_pu = np.empty((0, 2))
                Di_pu = np.array([[1, 0], [0, 1]])*Il2g 
                
                i_pu_u = [ig_q, ig_d]                                                       
                i_pu_y = [iq, id]  
                
                i_pu = ss(Ai_pu, Bi_pu, Ci_pu, Di_pu, inputs=i_pu_u, outputs=i_pu_y)        
                ss_list.append(i_pu)  
                
                
                # ANGLE AND ROTATIONS

                
                if not (num==num_slk and element_slk == 'GFOR'):     
                    
                    # ANGLE DEVIATION
                    
                    # Angle deviation from system reference
                    Adang = np.array([[0]])   
                    Bdang = np.array([[1, -1]])
                    Cdang = np.array([[1]])
                    Ddang = np.array([[0, 0]]) 
                    
                    dang_x = [etheta_x]
                    dang_u = [w_vsc, REF_w]
                    dang_y = ['e_theta']
                    
                    dang = ss(Adang, Bdang, Cdang, Ddang, states = dang_x, inputs = dang_u, outputs = dang_y)              
                    ss_list.append(dang)  
                    x_list.extend(dang_x)  
                    
                    # ROTATION MATRICES
                    
                    # REF INVERSE transform: vc_c to vc (local -> global)
                    vc_l2g = ssf.SS_ROTATE(e_theta0, vc_qc0, vc_dc0, "l2g", ['vc_qc','vc_dc', 'e_theta'], ['vc_q','vc_d'])
                    ss_list.append(vc_l2g) 
                    
                    # REF transform: ig to ig_c (global -> local)
                    ig_g2l = ssf.SS_ROTATE(e_theta0, ig_q0, ig_d0, "g2l", [ig_q, ig_d, 'e_theta'], ['ig_qc','ig_dc'])
                    ss_list.append(ig_g2l)   
                    
                    # REF transform: is to is_c (global -> local)
                    is_g2l = ssf.SS_ROTATE(e_theta0, is_q0, is_d0, "g2l", [is_q, is_d, 'e_theta'], ['is_qc', 'is_dc'])
                    ss_list.append(is_g2l)               
                    
                    # REF transform: u to u_c (global -> local)
                    u_g2l = ssf.SS_ROTATE(e_theta0, u_q0, u_d0, "g2l", [u_q, u_d, 'e_theta'], ['u_qc','u_dc'])
                    ss_list.append(u_g2l)      
                    
                else:
                    
                    # ANGLE DEVIATION --> ALGEBRAIC LOOP if uneeded etheta_x exists
                    
                    # Angle deviation from system reference (if slack)
                    
                    # Adang = np.array([[0]]) 
                    # Bdang = np.array([[1]]) 
                    # Cdang = np.array([[0]])
                    # Ddang = np.array([[0]])  
                    
                    # dang_x = [etheta_x]
                    # dang_u = [w_vsc]
                    # dang_y = ['e_theta']
                    # dang = ss(Adang, Bdang, Cdang, Ddang, states = dang_x, inputs = dang_u, outputs = dang_y)              
                    # ss_list.append(dang)  
                    # x_list.extend(dang_x) 
                    
                    # ROTATION MATRICES
                    
                    # REF INVERSE transform: vc_c to vc (local -> global)
                    vc_l2g = SS_ROTATE_SLACK(e_theta0, "l2g", ['vc_qc','vc_dc'], ['vc_q','vc_d'])
                    ss_list.append(vc_l2g) 
                    
                    # REF transform: ig to ig_c (global -> local)
                    ig_g2l = SS_ROTATE_SLACK(e_theta0, "g2l", [ig_q, ig_d], ['ig_qc','ig_dc'])
                    ss_list.append(ig_g2l)   
                    
                    # REF transform: is to is_c (global -> local)
                    is_g2l = SS_ROTATE_SLACK(e_theta0, "g2l", [is_q, is_d], ['is_qc', 'is_dc'])
                    ss_list.append(is_g2l)               
                    
                    # REF transform: u to u_c (global -> local)
                    u_g2l = SS_ROTATE_SLACK(e_theta0, "g2l", [u_q, u_d], ['u_qc','u_dc'])
                    ss_list.append(u_g2l)   
                    
    
                # OUTTER LOOPS
                
                # Frequency droop with low-pass filter on omega
                Afdroop = np.array([[-1/tau_droop_f]])
                Bfdroop = np.array([[0, 3/2*ig_q0, 3/2*ig_d0, 3/2*u_q0, 3/2*u_d0]])
                Cfdroop = np.array([[-k_droop_f/(tau_droop_f)*wb]])
                Dfdroop = np.array([[k_droop_f*wb, 0, 0, 0, 0]])
                
                fdroop_x = [fdroop_x1]
                fdroop_u = [P_ref, u_q, u_d, ig_q, ig_d]
                fdroop_y = [w_vsc]
                
                fdroop = ss(Afdroop, Bfdroop, Cfdroop, Dfdroop, states = fdroop_x, inputs = fdroop_u, outputs = fdroop_y)              
                ss_list.append(fdroop)  
                x_list.extend(fdroop_x)     

                # Voltage droop with low-pass filter in Qac
                Audroop = np.array([[-1/tau_droop_u]])
                Budroop = np.array([[0, -3/2*ig_d0, 3/2*ig_q0, 3/2*u_d0, -3/2*u_q0]])
                Cudroop = np.array([[k_droop_u/tau_droop_u]])
                Dudroop = np.array([[k_droop_u, 0, 0, 0, 0]])
                
                udroop_x = [udroop_x1]
                udroop_u = [Q_ref, u_q, u_d, ig_q, ig_d]
                udroop_y = [u_qc_ref]
                
                udroop = ss(Audroop, Budroop, Cudroop, Dudroop, states=udroop_x, inputs=udroop_u, outputs=udroop_y)
                ss_list.append(udroop)
                x_list.extend(udroop_x)   
                
                # AC side voltage control
                Au = np.array([[0, 0], 
                               [0, 0]])
                Bu = np.array([[1, 0, -1, 0, 0, 0], 
                               [0, 1, 0, -1, 0, 0]])
                Cu = np.array([[ki_vac, 0], 
                               [0, ki_vac]])
                Du = np.array([[kp_vac, 0, -kp_vac, wb*Cac, 1, 0], 
                               [0, kp_vac, -wb*Cac, -kp_vac, 0, 1]])
                
                u_x = [u_q_x1, u_d_x2]
                u_u = [u_qc_ref,u_dc_ref,'u_qc','u_dc','ig_qc_f','ig_dc_f']
                u_y = [is_qc_ref ,is_dc_ref]
                
                ss_u = ss(Au, Bu, Cu, Du, states=u_x, inputs=u_u, outputs=u_y)
                ss_list.append(ss_u)      
                x_list.extend(u_x) 
  
                # AC side current control
                Ais = np.array([[0, 0],
                                [0, 0]])
                
                Bis = np.array([[1, 0, -1, 0, 0, 0],
                                [0, 1, 0, -1, 0, 0]])
                
                Cis = np.array([[ki_s, 0],
                                [0, ki_s]])
                
                Dis = np.array([[kp_s, 0, -kp_s, wb*Lc, 1, 0],
                                [0, kp_s, -wb*Lc, -kp_s, 0, 1]])
                
                is_x = [is_q_x1, is_q_x2]
                is_u = [is_qc_ref,  is_dc_ref, 'is_qc', 'is_dc', 'u_qc_f', 'u_dc_f']
                is_y = ['vc_qc', 'vc_dc']   
                
                is_ss = ss(Ais, Bis, Cis, Dis, states=is_x, inputs=is_u, outputs=is_y)                
                ss_list.append(is_ss)  
                x_list.extend(is_x)   
                
                # AC voltage feedforward filter 
                f_igd = ssf.SS_LOW_PASS(1, tau_ig, 'ig_dc', 'ig_dc_f', f_igd_x1)
                ss_list.append(f_igd)
                x_list.extend([f_igd_x1])
  
                f_igq = ssf.SS_LOW_PASS(1, tau_ig, 'ig_qc', 'ig_qc_f', f_igq_x1)
                ss_list.append(f_igq)
                x_list.extend([f_igq_x1])              
  
                # current feedforward filter
                f_ud = ssf.SS_GAIN(1, 'u_dc', 'u_dc_f')  
                ss_list.append(f_ud)
    
                f_uq = ssf.SS_GAIN(1, 'u_qc', 'u_qc_f')  
                ss_list.append(f_uq)                
                
                # RL/RLC FILTER AND TRANSFORMER                
 
                # Transformer 
                Atr = np.array([[-(Rtr)/(Ltr), -w0], 
                                [w0, -(Rtr)/(Ltr)]])        
                Btr = np.array([[1/Ltr, 0, -1/Ltr, 0],
                                [0, 1/Ltr, 0, -1/Ltr]])        
                Ctr = np.array([[1, 0], 
                                [0, 1]])        
                Dtr = np.array([[0, 0, 0, 0],
                                [0, 0, 0, 0]])
                
                tr_x = [ig_q_x, ig_d_x]
                tr_u = [u_q, u_d,'vg_q','vg_d']
                tr_y = [ig_q, ig_d]
                
                tr_ss = ss(Atr, Btr, Ctr, Dtr, inputs=tr_u, outputs=tr_y, states=tr_x)        
                ss_list.append(tr_ss)   
                x_list.extend(tr_x)    
   
                # LC
                Alc = np.array([[-(Rc + Rac)/Lc, -wb, -1/Lc, 0],
                                [wb, -(Rc + Rac)/Lc, 0, -1/Lc],
                                [1/Cac, 0, 0, -wb],
                                [0, 1/Cac, wb, 0]])
                
                Blc = np.array([[1/Lc, 0, Rac/Lc, 0, -is_d0],
                                [0, 1/Lc, 0, Rac/Lc,  is_q0],
                                [0, 0, -1/Cac, 0, -ucap_d0],
                                [0, 0, 0, -1/Cac, ucap_q0]])
                
                Clc = np.array([[1, 0, 0, 0],
                                [0, 1, 0, 0],
                                [Rac, 0, 1, 0],
                                [0, Rac, 0, 1]])
                
                Dlc = np.array([[0, 0, 0, 0, 0],
                                [0, 0, 0, 0, 0],
                                [0, 0, -Rac, 0, 0],
                                [0, 0, 0, -Rac, 0]])
                
                lc_x = [is_q_x, is_d_x, ucap_q, ucap_d]
                if not (num==num_slk and element_slk == 'GFOR'): 
                    lc_u = ['vc_q', 'vc_d', ig_q, ig_d, REF_w]
                else:
                    lc_u = ['vc_q', 'vc_d', ig_q, ig_d, w_vsc]
                lc_y = [is_q, is_d, u_q, u_d]  
                
                Lc_ss = ss(Alc, Blc, Clc, Dlc, states=lc_x, inputs=lc_u, outputs=lc_y)                    
                ss_list.append(Lc_ss)
                x_list.extend(lc_x)          
   
    
                # BUILD COMPLETE MODEL  
                
                
                if (num==num_slk and element_slk == 'GFOR'):  
                    input_vars = ['vg_sys_q','vg_sys_d']
                    output_vars = [iq, id, w_vsc]
                else:
                    input_vars = ['vg_sys_q','vg_sys_d', REF_w]
                    output_vars = [iq, id, w_vsc]    
                                
                if connect_fun=='interconnect':
                    SS_GFOR = ct.interconnect(ss_list, states = x_list, inputs = input_vars, outputs = output_vars, check_unused = False) 

                    if save_ss_matrices == True:
                        save_ss_matrices_fun(SS_GFOR,
                                                 'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                                 f'{SS_GFOR=}'.split('=')[0]+str(n_vsc))
                elif connect_fun == 'append_and_connect':
                    SS_GFOR = interconnect.interconnect(ss_list, states = x_list, inputs = input_vars, outputs = output_vars, check_unused = False) 

                    
                    if save_ss_matrices == True:
                        save_ss_matrices_fun(SS_GFOR,
                                             'C:/Users/Francesca/miniconda3/envs/gridcal_original/hp2c-dt/' + connect_fun + '_test/',
                                             f'{SS_GFOR=}'.split('=')[0]+str(n_vsc)) 
                        
                # adapt inputs/outputs
                input_labels = SS_GFOR.input_labels
                input_labels[0] = vnXq
                input_labels[1] = vnXd
                SS_GFOR.input_labels = input_labels      
                
                if (num==num_slk and element_slk == 'GFOR'):  
                    output_labels = SS_GFOR.output_labels
                    output_labels[2] = REF_w
                    SS_GFOR.output_labels = output_labels     
                
                # append ss to l_blocks
                l_blocks.append(SS_GFOR)
                l_states.extend(SS_GFOR.state_labels)     
                # pd.DataFrame.to_excel(pd.DataFrame(SS_GFOR.A),'SS_GFOR'+str(num)+'_A_py.xlsx')

        n_vsc=n_vsc+1
        
    return l_blocks, l_states




# %% ROTATION FOR SLACK

def SS_ROTATE_SLACK(etheta_0, direction, u, y):
    
    if direction == "g2l":
        k = -1
    elif direction == "l2g":
        k = 1

    A = np.empty(0)
    B = np.empty((0, 2))
    C = np.empty((0, 2))
    D = np.array([[np.cos(etheta_0), k * np.sin(etheta_0)],
                  [-k * np.sin(etheta_0), np.cos(etheta_0)]])
    
    ss_rot = ss(A, B, C, D, inputs = u, outputs = y) 
    return ss_rot