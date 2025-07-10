import math
import time
import numpy as np
import copy

from datagen.src import sampling

from .utils import get_case_results
from stability_analysis.operating_point_from_datagenerator import datagen_OP
from stability_analysis.modify_GridCal_grid import assign_Generators_to_grid,assign_PQ_Loads_to_grid, assign_SlackBus_to_grid
from stability_analysis.powerflow import GridCal_powerflow, process_powerflow, slack_bus, fill_d_grid_after_powerflow
from stability_analysis.preprocess import preprocess_data, read_data, process_raw, parameters,read_op_data_excel, admittance_matrix
from stability_analysis.state_space import generate_NET, build_ss, generate_elements
from stability_analysis.analysis import small_signal

from stability_analysis.optimal_power_flow import process_optimal_power_flow
from stability_analysis.powerflow import check_feasibility

from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.OPF.NumericalMethods import ac_opf
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf, ac_optimal_power_flow
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
import GridCalEngine.api as gce

from .utils_obj_fun import *

import time

import sympy as sp

def feasible_power_flow_ACOPF(case,N_pf, tau_droop_f_gfor_12, **kwargs):
    d_raw_data = kwargs.get("d_raw_data", None)
    d_op = kwargs.get("d_op", None)
    GridCal_grid = kwargs.get("GridCal_grid", None)
    d_grid = kwargs.get("d_grid", None)
    d_sg = kwargs.get("d_sg", None)
    d_vsc = kwargs.get("d_vsc", None)
    voltage_profile = kwargs.get("voltage_profile", None)
    v_min_v_max_delta_v = kwargs.get("v_min_v_max_delta_v", None)
    V_set = kwargs.get("V_set", None)
    
    computing_times=dict()


    if voltage_profile != None and v_min_v_max_delta_v == None:
        print('Error: Voltage profile option selected but v_min, v_max, and delta_v are missing')
        return None, None, None

    if voltage_profile != None and V_set != None:
        print('Error: Both Voltage profile and V_set option is selected. Choose only one of them')
        return None, None, None

    if voltage_profile == None and V_set == None:
        print('Error: Neither Voltage profile or V_set option is selected. Choose one of them')
        return None, None, None

    d_raw_data, d_op = datagen_OP.generated_operating_point(case, d_raw_data,
                                                            d_op)
    d_raw_data, slack_bus_num = choose_slack_bus(d_raw_data)
    i_slack=int(d_raw_data['generator'].query('I == @slack_bus_num').index[0])

    # slack_bus_num=80
    assign_SlackBus_to_grid.assign_slack_bus(GridCal_grid, slack_bus_num)

    if voltage_profile != None:
        vmin = v_min_v_max_delta_v[0]
        vmax = v_min_v_max_delta_v[1]
        delta_v = v_min_v_max_delta_v[2]

        voltage_profile_list, indx_id = sampling.gen_voltage_profile(vmin, vmax, delta_v, d_raw_data, slack_bus_num,
                                                                     GridCal_grid)

        assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op,
                                               voltage_profile_list=voltage_profile_list, indx_id=indx_id)

    elif V_set != None:
        assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)

    assign_PQ_Loads_to_grid.assign_PQ_load(GridCal_grid, d_raw_data)
    
    # %% Run 1st POWER-FLOW

    # Receive system status from OPAL
    # d_grid, GridCal_grid, data_old = process_opal.update_OP_from_RT(d_grid, GridCal_grid, data_old)

    # Get Power-Flow results with GridCal
    pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)

    print('Converged:', pf_results.convergence_reports[0].converged_[0])
    

    # Update PF results and operation point of generator elements
    d_pf_original = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
    d_pf_original = additional_info_PF_results(d_pf_original, i_slack, pf_results, N_pf)

    nc = compile_numerical_circuit_at(GridCal_grid)
    nc.generator_data.cost_0[:] = 0
    nc.generator_data.cost_1[:] = 0
    nc.generator_data.cost_2[:] = 0
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, tolerance=1e-8, max_iter=100)
#    d_opf_results = ac_optimal_power_flow(Pref=np.array(d_pf_original['pf_gen']['P']), slack_bus_num=i_slack, nc=nc, pf_options=pf_options, plot_error=True)
    
    start = time.time()
    
    d_opf_results = ac_optimal_power_flow(nc=nc, pf_options=pf_options, plot_error=True)
        
    end = time.time()
    computing_times['time_powerflow']=end - start
    
    d_opf = process_optimal_power_flow.update_OP(GridCal_grid, d_opf_results, d_raw_data)
    d_opf = additional_info_OPF_results(d_opf,i_slack, N_pf)

                                        
    #########################################################################33



    d_grid, d_opf = fill_d_grid_after_powerflow.fill_d_grid(d_grid,
                                                           GridCal_grid, d_opf,
                                                           d_raw_data, d_op)

    # %% READ PARAMETERS

    # Get parameters of generator units from excel files & compute pu base
    d_grid = parameters.get_params(d_grid, d_sg, d_vsc)

    d_grid = update_control(case, d_grid)
    
    d_grid['T_VSC'].loc[d_grid['T_VSC'].query('mode == "GFOL"').index,'k_droop_u']=0.1    
    d_grid['T_VSC'].loc[d_grid['T_VSC'].query('mode == "GFOL"').index,'k_droop_f']=0.01    

    # Assign slack bus and slack element
    d_grid = slack_bus.assign_slack(d_grid)

    # Compute reference angle (delta_slk)
    d_grid, REF_w, num_slk, delta_slk = slack_bus.delta_slk(d_grid)

    # %% GENERATE STATE-SPACE MODEL

    # Generate AC & DC NET State-Space Model
    start = time.time()

    l_blocks, l_states, d_grid = generate_NET.generate_SS_NET_blocks(d_grid,
                                                                     delta_slk)

    end = time.time()
    computing_times['time_generate_SS_net']=end - start
    
    start = time.time()

    d_grid['T_VSC'].loc[28,'tau_droop_f']=tau_droop_f_gfor_12
    # Generate generator units State-Space Model
    l_blocks, l_states = generate_elements.generate_SS_elements(d_grid,
                                                                delta_slk,
                                                                l_blocks,
                                                                l_states)
    end = time.time()
    computing_times['time_generate_SS_elem']=end - start
   
    # %% BUILD FULL SYSTEM STATE-SPACE MODEL

    # Define full system inputs and ouputs
    var_in = ['NET_Rld1']
    var_out = ['all'] #['all']  # ['GFOR3_w'] #

    # Build full system state-space model
    start = time.time()

    inputs, outputs = build_ss.select_io(l_blocks, var_in, var_out)
    ss_sys = build_ss.connect(l_blocks, l_states, inputs, outputs)
    
    end = time.time()
    computing_times['time_connect']=end - start
  

    # %% SMALL-SIGNAL ANALYSIS

    start = time.time()

    
    T_EIG = small_signal.FEIG(ss_sys, True)
    T_EIG.head
    
    end = time.time()
    computing_times['time_eig']=end - start
 

    # write to excel
    # T_EIG.to_excel(path.join(path_results, "EIG_" + excel + ".xlsx"))

    if max(T_EIG['real'] >= 0):
        stability = 0
    else:
        stability = 1
        
    # Obtain all participation factors
    # df_PF = small_signal.FMODAL(ss_sys, plot=False)
    # # Obtain the participation factors for the selected modes
    # T_modal, df_PF = small_signal.FMODAL_REDUCED(ss_sys, plot=True, modeID = [1,3,11])
    # # Obtain the participation factors >= tol, for the selected modes
    
    start = time.time()

    T_modal, df_PF = small_signal.FMODAL_REDUCED_tol(ss_sys, plot=True, modeID = np.arange(1,23), tol = 0.3)

    end = time.time()
    computing_times['time_partfact']=end - start
    
   
    df_op, df_real, df_imag, df_freq, df_damp = (
        get_case_results(T_EIG=T_EIG, d_grid=d_grid))
    output_dataframes = {
        "df_op": df_op, "df_real": df_real, "df_imag": df_imag,
        "df_freq": df_freq, "df_damp": df_damp
    }
    return stability, output_dataframes, d_pf_original, d_opf, d_grid, T_EIG, computing_times

def return_d_opf(d_raw_data, d_opf_results):
    df_opf_bus = pd.DataFrame(
        {'bus': d_raw_data['results_bus']['I'], 'Vm': d_opf_results.Vm, 'theta': d_opf_results.Va})
    df_opf_gen_pre = pd.DataFrame(
        {'bus': d_raw_data['generator']['I'], 'P': d_opf_results.Pg, 'Q': d_opf_results.Qg})
    df_opf_gen = pd.merge(df_opf_gen_pre, df_opf_bus[['bus', 'Vm', 'theta']], on='bus', how='left')
    d_opf = {'opf_bus': df_opf_bus, 'opf_gen': df_opf_gen,'opf_load': d_raw_data['load']} 
    return d_opf


def write_csv(d, path, N_pf, filename_start):
    for df_name, df in d.items():
        filename=filename_start+'_'+str(N_pf)+'_'+str(df_name)
        pd.DataFrame.to_csv(df,path+filename+".csv")
        
def write_xlsx(d, path, filename):
    with pd.ExcelWriter(path+filename+".xlsx") as writer:
        for df_name, df in d.items():
            if isinstance(df, pd.DataFrame):                
                df.to_excel(writer, sheet_name=df_name)


def update_control(case, d_grid):
    case_index=case.index

    for i in range(0,len(d_grid['T_VSC'])):
        mode=d_grid['T_VSC'].loc[i,'mode']
        bus=d_grid['T_VSC'].loc[i,'bus']
        
        control_p_mode=[cc for cc in case.index if 'tau' and mode.lower() in cc]
        control_p_mode_bus=[cc for cc in control_p_mode if str(bus) in cc]
        
        control_p_labels=[''.join(filter(lambda x: not x.isdigit(), cc))[:-1].replace(mode.lower(),'')[:-1] for cc in control_p_mode_bus ]
        
        for control_p,control_p_bus in zip(control_p_labels,control_p_mode_bus):
            d_grid['T_VSC'].loc[i,control_p]=case[control_p_bus]
    
    return d_grid