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

from stability_analysis.powerflow import check_feasibility

from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.OPF.NumericalMethods import ac_opf

from .utils_obj_fun import *

# file where objective function is declared (dummy test)
def dummy(case, **kwargs):
    time.sleep(0.0001)
    return round(math.sin(sum(case)) * 0.5 + 0.5), {}

def matmul(case, **kwargs):
    t0 = time.time()
    while(time.time() - t0 < 0.0000):
        m0 = np.random.randint(0, 101, size=(1000, 1000))
        m1 = np.random.randint(0, 101, size=(1000, 1000))
        x = np.dot(m0, m1)
    return round(math.sin(sum(case)) * 0.5 + 0.5), {}

def dummy_linear(case, **kwargs):
    total_sum = sum(case)
    return total_sum/19 > 0.5, {}  # 19 => maximum value among all upper borders

# @task(return=3)
def feasible_power_flow(case, **kwargs):
    d_raw_data = kwargs.get("d_raw_data", None)
    d_op = kwargs.get("d_op", None)
    GridCal_grid = kwargs.get("GridCal_grid", None)
    d_grid = kwargs.get("d_grid", None)
    d_sg = kwargs.get("d_sg", None)
    d_vsc = kwargs.get("d_vsc", None)
    voltage_profile=kwargs.get("voltage_profile",None)
    v_min_v_max_delta_v=kwargs.get("v_min_v_max_delta_v",None)
    V_set=kwargs.get("V_set",None)
    
    if voltage_profile!=None and v_min_v_max_delta_v==None:
        print('Error: Voltage profile option selected but v_min, v_max, and delta_v are missing')        
        return None, None, None

    if voltage_profile!=None and V_set!=None:
        print('Error: Both Voltage profile and V_set option is selected. Choose only one of them')        
        return None, None, None
    
    if voltage_profile==None and V_set==None:
        print('Error: Neither Voltage profile or V_set option is selected. Choose one of them')        
        return None, None, None

    d_raw_data, d_op = datagen_OP.generated_operating_point(case, d_raw_data,
                                                            d_op) 
    
    d_raw_data, slack_bus_num = choose_slack_bus(d_raw_data)
    # slack_bus_num=80
    assign_SlackBus_to_grid.assign_slack_bus(GridCal_grid, slack_bus_num)
    
    if voltage_profile!=None:
        vmin=v_min_v_max_delta_v[0]
        vmax=v_min_v_max_delta_v[1]
        delta_v=v_min_v_max_delta_v[2]
        
        voltage_profile_list, indx_id=sampling.gen_voltage_profile(vmin,vmax,delta_v,d_raw_data,slack_bus_num,GridCal_grid)
    
        assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
    
    elif V_set!=None:
        assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
        
    assign_PQ_Loads_to_grid.assign_PQ_load(GridCal_grid, d_raw_data)
    
# #%% solve optimal power flow
    import GridCalEngine.api as gce

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    
    from GridCal.src.GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf_autodif import ac_optimal_power_flow
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)    

    # %% Run 1st POWER-FLOW

    # Receive system status from OPAL
    # d_grid, GridCal_grid, data_old = process_opal.update_OP_from_RT(d_grid, GridCal_grid, data_old)

    # Get Power-Flow results with GridCal
    pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)

    print('Converged:', pf_results.convergence_reports[0].converged_[0])
    

    # Update PF results and operation point of generator elements
    d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
    
    d_pf_original=copy.deepcopy(d_pf)
    
    if pf_results.convergence_reports[0].converged_[0] == False:
        print('No Convergent solution')
        return None, None, None
    
    d_raw_data=update_raw_data(d_raw_data,d_pf)
    # check violations
    Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095= check_feasibility.check_violations(d_pf, d_op)

    if len(Gen_pf_violation)==0:
        return d_pf_original, d_pf, d_raw_data 
 
#%% IF UNFEASIBLE

    sum_diff_0= sum_cosphi_underdev(Gen_pf_violation) # funcion objectivo 

    num_gen_viol=len(Gen_pf_violation)
    d_raw_data_gen_prev_iter=d_raw_data['generator'].copy(deep=True)
    Gen_pf_violation_prev_iter=Gen_pf_violation.copy(deep=True)
    d_pf_prev=copy.deepcopy(d_pf)
    iter_num_best=0

    print('min cosphi',min(Gen_pf_violation['Val']))
    print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])
    n_iter=0
    molt=1
    alpha_incr=0.1
    alpha_decr=0.1

    while len(Gen_pf_violation)>0 and n_iter<100:
        print(n_iter)
        if n_iter==12:
            print('stop')
        
        slack_injecting_positive_power=d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus == @slack_bus_num').index[0],'P']>0
        
#%% P slack >0 ?         
        if slack_injecting_positive_power:
            more_than_one_gen_violating=len(Gen_pf_violation)>1 
#%%  P slack >0 and more_than_one_gen_violating=True
            if more_than_one_gen_violating:
                all_gen_violatin_at_1_pu=np.all(np.round(Gen_pf_violation.query('GenBus != @slack_bus_num')['P_p_u'],4)==1)
#%% P slack >0 and more_than_one_gen_violating=True and generators violating are not all at 1 p.u.
                if all_gen_violatin_at_1_pu == False:
                    
                    if voltage_profile!=None:
                
                        J_f_pos=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_violation, d_raw_data=d_raw_data,
                                           d_op=d_op, delta_p=10, GridCal_grid=GridCal_grid,
                                           voltage_profile_list=voltage_profile_list,indx_id=indx_id)
                    elif V_set!=None:
                
                        J_f_pos=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_violation, d_raw_data=d_raw_data,
                                           d_op=d_op, delta_p=10, GridCal_grid=GridCal_grid,
                                           V_set=V_set)
                    
                    if isinstance(J_f_pos, np.ndarray):
                        Gen_pf_violation['J_f']=J_f_pos.reshape(-1,1)
                    else: # It means it found a fesible solution!
                        d_raw_data=J_f_pos
                        
                        if voltage_profile!=None:
                        
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
                        
                        elif V_set!=None:
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
                                                
                        # Get Power-Flow results with GridCal
                        pf_results = GridCal_powerflow.run_powerflow(GridCal_grid,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                    
                        print('Converged:',pf_results.convergence_reports[0].converged_[0])
                        
                        # if pf_results.convergence_reports[0].converged_[0] == False:
                        #     return None, None, None
                        
                        if pf_results.convergence_reports[0].converged_[0] == False:
                        
                            pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)#,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                        
                            print('Converged:',pf_results.convergence_reports[0].converged_[0])
                            
                            if pf_results.convergence_reports[0].converged_[0] == False:
                                print('No Convergent solution')
                                return None, None, None
                        
                        # Update PF results and operation point of generator elements
                        d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
                        
                        d_raw_data=update_raw_data(d_raw_data,d_pf)

                        Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
                        
                        if len(Gen_pf_violation)<=num_gen_viol:
                            d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best=update_previous_best(Gen_pf_violation, d_raw_data, num_gen_viol, d_pf, n_iter)
                        
                        if len(Gen_pf_violation)==0:
                            return d_pf_original, d_pf, d_raw_data 
                    
                    increasing_gen_power_positive_effect=len(Gen_pf_violation.query('GenBus != @slack_bus_num and J_f >0'))!=0
#%% P slack >0 and more_than_one_gen_violating=True and generators violating are not all at 1 p.u. len(J_f_pos)>0:   
                    if increasing_gen_power_positive_effect:
                        
                        #     actions:
                        #          - proportionally increase P of J_f_pos>0
                        # 			- assign generators
                        # 			- calculate convergent power flow
                        # 			- update d_raw_data
                        # 			- check violations --> Gen_pf_violation
                        # 			- calculate sum_diff_1: sum_i=1^N_gen_viol|0.95-cosphi_i|_iter_1
                        # 			- check sum_diff_1 vs exprected decrease --> in case increase alpha
                        # 			- calculate J_f_pos(sum_diff_1, Gen_pf_violation)=[sum_diff_1-sum_diff(delta_P_i) for i in Gen_pf_viol]
                        # 			- sum_dif_0=sum_dif_1
                         
                        
                        d_raw_data =proportional_increase_P(alpha_incr,d_pf,d_raw_data, d_op, Gen_pf_violation, slack_bus_num)   
                                            
                        if voltage_profile!=None:
                        
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
                        
                        elif V_set!=None:
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
                                                
                        # Get Power-Flow results with GridCal
                        pf_results = GridCal_powerflow.run_powerflow(GridCal_grid,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                    
                        print('Converged:',pf_results.convergence_reports[0].converged_[0])
                        
                        # if pf_results.convergence_reports[0].converged_[0] == False:
                        #     return None, None, None
                        
                        if pf_results.convergence_reports[0].converged_[0] == False:
                        
                            pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)#,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                        
                            print('Converged:',pf_results.convergence_reports[0].converged_[0])
                            
                            if pf_results.convergence_reports[0].converged_[0] == False:
                                print('No Convergent solution')
                                return None, None, None
                        
                        # Update PF results and operation point of generator elements
                        d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
                        
                        d_raw_data=update_raw_data(d_raw_data,d_pf)

                        Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
                        
                        if len(Gen_pf_violation)<=num_gen_viol:
                            d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best=update_previous_best(Gen_pf_violation, d_raw_data, num_gen_viol, d_pf, n_iter)
                        
                        if len(Gen_pf_violation)==0:
                            return d_pf_original, d_pf, d_raw_data 
                            
                        sum_diff_1= sum_cosphi_underdev(Gen_pf_violation)

                        c1=1
                        rho=1.1
                        expected_decrease = c1 * alpha_incr * np.dot(J_f_pos, -J_f_pos.reshape(-1,1))

                        if sum_diff_1 <=sum_diff_0+expected_decrease:
                            alpha_incr=alpha_incr
                        else:
                            alpha_incr=alpha_incr*rho
                
                        sum_diff_0=sum_diff_1
                        
                        try:
                            print('min cosphi',min(Gen_pf_violation['Val']))
                            print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])
                        except: 
                            print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])
                        
#%% P slack >0 and more_than_one_gen_violating=True and generators violating are not all at 1 p.u. and increasing power doesn't have positive effect
                        
                    else:
                        
                        #     actions:
                        #          - select generators with high cosphi
                        #          - calculate their J_f_neg(sum_diff_0, Gen_pf_violation)
                        #          - proportionally decrease P of high cosphi gen with J_f_neg>0
                        # 			- assign generators
                        # 			- calculate convergent power flow
                        # 			- update d_raw_data
                        # 			- check violations --> Gen_pf_violation
                        # 			- calculate sum_diff_1: sum_i=1^N_gen_viol|0.95-cosphi_i|_iter_1
                        # 			- calculate J_f_neg(sum_diff_1, Gen_pf_violation)=[sum_diff_1-sum_diff(delta_P_i) for i in Gen_pf_viol]
                        # 			- sum_dif_0=sum_dif_1
                       
                        max_cosphi=0.95#max(Gen_pf_above095['Val'])
                        Gen_pf_above095_red=Gen_pf_above095.query('Val > @max_cosphi').reset_index(drop=True)
                        # Gen_pf_above095_red=Gen_pf_above095.sort_values(by='Val',ascending=False).reset_index(drop=True)
                        
                        if voltage_profile!=None:

                            J_f_neg=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_above095_red, d_raw_data=d_raw_data,
                                               d_op=d_op, delta_p=-10, GridCal_grid=GridCal_grid,
                                               voltage_profile_list=voltage_profile_list,indx_id=indx_id)
                        elif V_set!=None:

                            J_f_neg=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_above095_red, d_raw_data=d_raw_data,
                                               d_op=d_op, delta_p=-10, GridCal_grid=GridCal_grid,
                                               V_set=V_set)

                            
                        Gen_pf_above095_red['J_f']=J_f_neg.reshape(-1,1)
                        exclude_gen=list(Gen_pf_above095_red.query('J_f <=0')['GenBus'])
                        
                        # Gen_high_cosphi=d_pf['pf_gen'].query('cosphi >= @max_cosphi and bus!=@exclude_gen').reset_index(drop=True)
                        
                        Gen_high_cosphi=d_pf['pf_gen'].query('cosphi >= @max_cosphi and bus!=@exclude_gen').sort_values(by='cosphi',ascending=False).reset_index(drop=True)
                       
                        if len(Gen_high_cosphi)==0:
                            print('No solution beacuse booth increasing and decreasing P has not a positive effect')
                            return None, None, None 
                                                
                        d_raw_data= proportional_decrease_P(d_pf,d_raw_data,d_op,Gen_high_cosphi,alpha_decr)
                                                
                        if voltage_profile!=None:
                        
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
                        
                        elif V_set!=None:
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
                        
                        
                        # Get Power-Flow results with GridCal
                        pf_results = GridCal_powerflow.run_powerflow(GridCal_grid,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                    
                        print('Converged:',pf_results.convergence_reports[0].converged_[0])
                        
                        # if pf_results.convergence_reports[0].converged_[0] == False:
                        #     return None, None, None
                        
                        if pf_results.convergence_reports[0].converged_[0] == False:
                        
                            pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)#,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                        
                            print('Converged:',pf_results.convergence_reports[0].converged_[0])
                            
                            if pf_results.convergence_reports[0].converged_[0] == False:
                                print('No Convergent solution')
                                return None, None, None
                                                
                        # Update PF results and operation point of generator elements
                        d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
                        
                        d_raw_data=update_raw_data(d_raw_data,d_pf)

                        Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
                    
                        if len(Gen_pf_violation)<=num_gen_viol:
                            d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best=update_previous_best(Gen_pf_violation, d_raw_data, num_gen_viol, d_pf, n_iter)
                        
                        if len(Gen_pf_violation)==0:
                            return d_pf_original, d_pf, d_raw_data 

                        sum_diff_0= sum_cosphi_underdev(Gen_pf_violation)
                        
                        # c1=1
                        # rho=1.1
                        # expected_decrease = c1 * alpha_decr * np.dot(J_f_neg, -J_f_neg.reshape(-1,1))

                        # if sum_diff_1 <=sum_diff_0+expected_decrease:
                        #     alpha_decr=alpha_decr
                        # else:
                        #     alpha_decr=alpha_decr*rho
                        
                        # sum_diff_1=sum_diff_0
                                            
                        try:
                            print('min cosphi',min(Gen_pf_violation['Val']))
                            print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])
                        except: 
                            print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])                              
                        
                            
#%% P slack >0 and more_than_one_gen_violating=True and generators violating are all at 1 p.u.:
                else:
                    Slack_at_1_pu=d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus == @slack_bus_num').index[0],'P']*100/d_op['Generators'].loc[d_op['Generators'].query('BusNum == @slack_bus_num').index[0],'Pmax']==1

#%% P slack >0 and more_than_one_gen_violating=True and generators violating are all at 1 p.u., but not the slack                 
                    if Slack_at_1_pu==False:
                        print('Decrease P of close generators with J_f_neg >0')
                        return d_pf_original, d_pf, d_raw_data 
#%% P slack >0 and more_than_one_gen_violating=True and generators violating are all at 1 p.u., including the slack                 
                    else:
                        print('Decrease P of close generators with J_f_neg >0 and increas P')
                        return d_pf_original, d_pf, d_raw_data 
                    
#%%  P slack >0 and only one generator is violating                
            else:
                is_the_slack=Gen_pf_violation.loc[0,'GenBus']==slack_bus_num
#%%  P slack >0 and only one generator is violating and is the slack:
                if is_the_slack==True:
                    print('only slack violating')
                    return d_pf_original, d_pf, d_raw_data 
                
#%%  P slack >0 and only one generator is violating and is not the slack:                
                else:
                    print('only one generator violating (not slack)')
                    
                    if voltage_profile!=None:
                
                        J_f_pos=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_violation, d_raw_data=d_raw_data,
                                           d_op=d_op, delta_p=10, GridCal_grid=GridCal_grid,
                                           voltage_profile_list=voltage_profile_list,indx_id=indx_id)
                    elif V_set!=None:
                
                        J_f_pos=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_violation, d_raw_data=d_raw_data,
                                           d_op=d_op, delta_p=10, GridCal_grid=GridCal_grid,
                                           V_set=V_set)
                
                    if isinstance(J_f_pos, np.ndarray):
                        Gen_pf_violation['J_f']=J_f_pos.reshape(-1,1)
                    else: # It means it found a fesible solution!
                        d_raw_data=J_f_pos
                        
                        if voltage_profile!=None:
                        
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
                        
                        elif V_set!=None:
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
                                                
                        # Get Power-Flow results with GridCal
                        pf_results = GridCal_powerflow.run_powerflow(GridCal_grid,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                    
                        print('Converged:',pf_results.convergence_reports[0].converged_[0])
                        
                        # if pf_results.convergence_reports[0].converged_[0] == False:
                        #     return None, None, None
                        
                        if pf_results.convergence_reports[0].converged_[0] == False:
                        
                            pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)#,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                        
                            print('Converged:',pf_results.convergence_reports[0].converged_[0])
                            
                            if pf_results.convergence_reports[0].converged_[0] == False:
                                print('No Convergent solution')
                                return None, None, None
                        
                        # Update PF results and operation point of generator elements
                        d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
                        
                        d_raw_data=update_raw_data(d_raw_data,d_pf)

                        Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
                        
                        if len(Gen_pf_violation)<=num_gen_viol:
                            d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best=update_previous_best(Gen_pf_violation, d_raw_data, num_gen_viol, d_pf, n_iter)
                        
                        if len(Gen_pf_violation)==0:
                            return d_pf_original, d_pf, d_raw_data 
                    
                    increasing_gen_power_positive_effect=len(Gen_pf_violation.query('GenBus != @slack_bus_num and J_f >0'))!=0

#%% P slack >0 and only one generator is violating and is not the slack and increasing its power has a positive effect                
                    if increasing_gen_power_positive_effect==True:
                        
                        #♠alpha_incr_1_gen=0.008
                        d_raw_data =proportional_increase_P(alpha_incr,d_pf,d_raw_data, d_op, Gen_pf_violation, slack_bus_num)   
                                            
                        if voltage_profile!=None:
                        
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
                        
                        elif V_set!=None:
                            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
                                                
                        # Get Power-Flow results with GridCal
                        pf_results = GridCal_powerflow.run_powerflow(GridCal_grid,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                    
                        print('Converged:',pf_results.convergence_reports[0].converged_[0])
                        
                        # if pf_results.convergence_reports[0].converged_[0] == False:
                        #     return None, None, None
                        
                        if pf_results.convergence_reports[0].converged_[0] == False:
                        
                            pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)#,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
                        
                            print('Converged:',pf_results.convergence_reports[0].converged_[0])
                            
                            if pf_results.convergence_reports[0].converged_[0] == False:
                                print('No Convergent solution')
                                return None, None, None
                        
                        # Update PF results and operation point of generator elements
                        d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
                        
                        d_raw_data=update_raw_data(d_raw_data,d_pf)
    
                        Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
                        
                        if len(Gen_pf_violation)<=num_gen_viol:
                            d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best=update_previous_best(Gen_pf_violation, d_raw_data, num_gen_viol, d_pf, n_iter)
                        
                        if len(Gen_pf_violation)==0:
                            return d_pf_original, d_pf, d_raw_data 
                            
                        sum_diff_1= sum_cosphi_underdev(Gen_pf_violation)
    
                        c1=1
                        rho=1.1
                        expected_decrease = c1 * alpha_incr * np.dot(J_f_pos, -J_f_pos.reshape(-1,1))
    
                        if sum_diff_1 <=sum_diff_0+expected_decrease:
                            alpha_incr=alpha_incr
                        else:
                            alpha_incr=alpha_incr*rho
                
                        sum_diff_0=sum_diff_1
                        
                        try:
                            print('min cosphi',min(Gen_pf_violation['Val']))
                            print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])
                        except: 
                            print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])

#%% P slack >0 and only one generator is violating and is not the slack and increasing its power has not a positive effect                
                    else:
                        print('one generator is violating and is not the slack and increasing its power has not a positive effect')                                            
#%% P slack <=0            
        else:
            
            max_cosphi=0.95#max(Gen_pf_above095['Val'])
            Gen_pf_above095_red=Gen_pf_above095.query('Val > @max_cosphi').reset_index(drop=True)
            # Gen_pf_above095_red=Gen_pf_above095.sort_values(by='Val',ascending=False).reset_index(drop=True)
            
            if voltage_profile!=None:

                J_f_neg=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_above095_red, d_raw_data=d_raw_data,
                                   d_op=d_op, delta_p=-10, GridCal_grid=GridCal_grid,
                                   voltage_profile_list=voltage_profile_list,indx_id=indx_id)
            elif V_set!=None:

                J_f_neg=calculate_grad(sum_diff_0=sum_diff_0, Gen_pf_violation_0=Gen_pf_above095_red, d_raw_data=d_raw_data,
                                   d_op=d_op, delta_p=-10, GridCal_grid=GridCal_grid,
                                   V_set=V_set)

                
            Gen_pf_above095_red['J_f']=J_f_neg.reshape(-1,1)
            exclude_gen=list(Gen_pf_above095_red.query('J_f <=0')['GenBus'])
            
            # Gen_high_cosphi=d_pf['pf_gen'].query('cosphi >= @max_cosphi and bus!=@exclude_gen').reset_index(drop=True)
            
            Gen_high_cosphi=d_pf['pf_gen'].query('cosphi >= @max_cosphi and bus!=@exclude_gen').sort_values(by='cosphi',ascending=False).reset_index(drop=True)
            
#%% Pslack <=0 and len(J_f_neg)>0:            
            if len(Gen_high_cosphi)>0:
                # try:
                #     Gen_high_cosphi=Gen_high_cosphi.iloc[0:5]
                # except:
                #     Gen_high_cosphi=Gen_high_cosphi
                                        
                d_raw_data= proportional_decrease_P(d_pf,d_raw_data,d_op,Gen_high_cosphi,alpha_decr)

#%% Pslack <=0 and len(J_f_neg)>0:                
            else:
                Gen_high_cosphi=d_pf['pf_gen'].query('cosphi >= @max_cosphi').sort_values(by='cosphi',ascending=False).reset_index(drop=True)

#%% Pslack <=0 and len(J_f_neg)>0 or len(J_f_neg)<=0
                            
            if voltage_profile!=None:
            
                assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
            
            elif V_set!=None:
                assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data, d_op=d_op, V_set=V_set)
            
            
            # Get Power-Flow results with GridCal
            pf_results = GridCal_powerflow.run_powerflow(GridCal_grid,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
        
            print('Converged:',pf_results.convergence_reports[0].converged_[0])
            
            # if pf_results.convergence_reports[0].converged_[0] == False:
            #     return None, None, None
            
            if pf_results.convergence_reports[0].converged_[0] == False:
            
                pf_results = GridCal_powerflow.run_powerflow(GridCal_grid)#,SolverType.IWAMOTO,ReactivePowerControlMode.Iterative)
            
                print('Converged:',pf_results.convergence_reports[0].converged_[0])
                
                if pf_results.convergence_reports[0].converged_[0] == False:
                    print('No Convergent solution')
                    return None, None, None
                                    
            # Update PF results and operation point of generator elements
            d_pf = process_powerflow.update_OP(GridCal_grid, pf_results, d_raw_data)
            
            d_raw_data=update_raw_data(d_raw_data,d_pf)

            Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
        
            if len(Gen_pf_violation)<=num_gen_viol:
                d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best=update_previous_best(Gen_pf_violation, d_raw_data, num_gen_viol, d_pf, n_iter)
            
            if len(Gen_pf_violation)==0:
                return d_pf_original, d_pf, d_raw_data 

            sum_diff_0= sum_cosphi_underdev(Gen_pf_violation)
            
            # c1=1
            # rho=1.1
            # expected_decrease = c1 * alpha_decr * np.dot(J_f_neg, -J_f_neg.reshape(-1,1))

            # if sum_diff_1 <=sum_diff_0+expected_decrease:
            #     alpha_decr=alpha_decr
            # else:
            #     alpha_decr=alpha_decr*rho
            
            # sum_diff_1=sum_diff_0
                                
            try:
                print('min cosphi',min(Gen_pf_violation['Val']))
                print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])
            except: 
                print('P slack', d_pf['pf_gen'].query('bus == @slack_bus_num')['P'])       
            
        n_iter=n_iter+1            
        print('sum_diff ',sum_diff_1)
        print('gen viol ', len(Gen_pf_violation))
         
        
    return d_pf_original, d_pf, d_raw_data 
