import pandas as pd
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

from GridCalEngine.Simulations.PowerFlow.power_flow_options import  SolverType


def choose_slack_bus(d_raw_data):
    T_generators=d_raw_data['generator'].query('P_SG !=0 or P_GFOR!=0')
    T_generators['deltaP']=T_generators['MBASE']-T_generators['PG']
    T_generators=T_generators.sort_values(by='deltaP', ascending=False).reset_index(drop=True)
    slack_bus=T_generators.loc[0,'I']
    d_raw_data['data_global'].loc[0,'ref_bus']=slack_bus

    if T_generators.loc[0,'P_SG']!=0:
        d_raw_data['data_global'].loc[0,'ref_element']='SG'
    elif T_generators.loc[0,'P_GFOR']!=0:
        d_raw_data['data_global'].loc[0,'ref_element']='GFOR'
    else:
        raise RuntimeError('Error: missing generator at slack bus')
    return d_raw_data, slack_bus

def additional_info_PF_results(d_pf,i_slack,pf_results, N_PF):
    d_pf['pf_gen']['slack_bus']=0
    d_pf['pf_gen'].loc[i_slack,'slack_bus']=1
    d_pf['info'].loc[0,'convergence']=pf_results.convergence_reports[0].converged_[0]
    d_pf['info'].loc[0,'N_PF']=N_PF

    return d_pf

def additional_info_OPF_results(d_opf,i_slack, N_PF, d_opf_results):
    d_opf['pf_gen']['slack_bus']=0
    d_opf['pf_gen'].loc[i_slack,'slack_bus']=1
    d_opf['info'].loc[0,'convergence']=d_opf_results.converged
    d_opf['info'].loc[0,'N_PF']=N_PF

    return d_opf

def update_raw_data(d_raw_data,d_pf):
    
    d_raw_data['generator']['PG']=d_pf['pf_gen']['P']*100
    d_raw_data['generator']['QG']=d_pf['pf_gen']['Q']*100
    
    return d_raw_data

def proportional_increase_P(alpha,d_pf,d_raw_data,d_op,Gen_pf_violation,slack_bus_num):#, num_gen_viol,d_raw_data_gen_prev_iter):
    Gen_pf_violation_red=Gen_pf_violation.query('J_f>0').reset_index(drop=True)
    min_cosphi=min(Gen_pf_violation_red.drop(np.where(np.isclose(Gen_pf_violation_red['P_p_u'],1))[0],axis=0).query('GenBus != @slack_bus_num')['Val'])
    max_delta_cosphi=0.95-min_cosphi
    
    delta_P_tot=0
    while delta_P_tot<10:
        delta_P_tot_prev=delta_P_tot
        for i in range(len(Gen_pf_violation_red)):
            cosphi=Gen_pf_violation_red.loc[i,'Val']
            delta_cosphi=0.95-cosphi
            delta_P=alpha/max_delta_cosphi*delta_cosphi
            
            bus=Gen_pf_violation_red.loc[i,'GenBus']
            if bus == slack_bus_num:
                continue
            P_pu= d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus==@bus').index[0],'P']*100/d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus').index[0],'Pmax']
    
            if P_pu+delta_P<1:
                P_pu=P_pu+delta_P
            else:
                P_pu=1
            d_raw_data['generator'].loc[d_raw_data['generator'].query('I ==@bus').index[0],'PG']=P_pu*d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus').index[0],'Pmax']

        buses=list(set(list(Gen_pf_violation_red['GenBus']))-set([slack_bus_num]))
        delta_P_tot=np.sum(d_raw_data['generator'].query('I == @buses')['PG'])-np.sum(d_pf['pf_gen'].query('bus == @buses')['P'])*100
        delta_delta=abs(delta_P_tot_prev-delta_P_tot)
        if delta_delta < 1e-3:
            return d_raw_data#, d_raw_data_gen_prev_iter,num_gen_viol
        alpha=alpha+0.05
        print('delta_p_tot',delta_P_tot)
    return d_raw_data#, d_raw_data_gen_prev_iter,num_gen_viol

def sum_cosphi_underdev(Gen_pf_violation):
    sum_diff=0.95*len(Gen_pf_violation)-np.sum(Gen_pf_violation['Val'])
    return sum_diff

def calculate_grad(sum_diff_0,Gen_pf_violation_0, d_raw_data, d_op, delta_p,GridCal_grid, **kwargs):
   
    voltage_profile_list=kwargs.get("voltage_profile_list",None)
    indx_id=kwargs.get("indx_id",None)
    V_set=kwargs.get("V_set",None)
   
    J_f=np.zeros([1,len(Gen_pf_violation_0)])
    
    for gen_count in range(0,len(Gen_pf_violation_0)): 
        d_raw_data_increase_gen=copy.deepcopy(d_raw_data)
        gen_bus=Gen_pf_violation_0.loc[gen_count,'GenBus']
        d_raw_data_increase_gen['generator'].loc[d_raw_data_increase_gen['generator'].query('I == @gen_bus').index[0],'PG']=d_raw_data_increase_gen['generator'].loc[d_raw_data_increase_gen['generator'].query('I == @gen_bus').index[0],'PG']+delta_p
        
        if voltage_profile_list!=None:
            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data_increase_gen, d_op=d_op, voltage_profile_list=voltage_profile_list, indx_id=indx_id)
        elif V_set!=None:
            assign_Generators_to_grid.assign_PVGen(GridCal_grid=GridCal_grid, d_raw_data=d_raw_data_increase_gen, d_op=d_op, V_set=V_set)
                    
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
        
        Bus_voltage_violation, Gen_Q_Min_limit_violation, Gen_Q_Max_limit_violation, Gen_pf_violation, Gen_V_violation, Gen_pf_above095 = check_feasibility.check_violations(d_pf, d_op)
    
        if len(Gen_pf_violation)>0:
            J_f[0,gen_count]=sum_diff_0-sum_cosphi_underdev(Gen_pf_violation)
        else:
            # J_f=np.zeros([1,len(Gen_pf_violation_0)])
            # J_f[0,gen_count]=1
            return d_raw_data_increase_gen
    return J_f

def proportional_decrease_P(d_pf,d_raw_data,d_op,Gen_high_cosphi,alpha):
    max_cosphi=max(Gen_high_cosphi['cosphi'])
    max_delta_cosphi=max_cosphi- 0.95
    # d_raw_data_gen_prev_iter=d_raw_data['generator'].copy(deep=True)
    
    for i in range(len(Gen_high_cosphi)):
        cosphi=Gen_high_cosphi.loc[i,'cosphi']
        delta_cosphi=cosphi-0.95
        delta_P=alpha/max_delta_cosphi*delta_cosphi
        
        
        bus=Gen_high_cosphi.loc[i,'bus']
        P_pu= d_pf['pf_gen'].loc[d_pf['pf_gen'].query('bus==@bus').index[0],'P']*100/d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus').index[0],'Pmax']

        if P_pu-delta_P>0:
            P_pu=P_pu-delta_P
        else:
            P_pu=0
        d_raw_data['generator'].loc[d_raw_data['generator'].query('I ==@bus').index[0],'PG']=P_pu*d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus').index[0],'Pmax']

    return d_raw_data#, d_raw_data_gen_prev_iter
  

def update_previous_best(Gen_pf_violation,d_raw_data,num_gen_viol, d_pf, iter_num):
            
    d_raw_data_gen_prev_iter=copy.deepcopy(d_raw_data)
    num_gen_viol=len(Gen_pf_violation)
    Gen_pf_violation_prev_iter=Gen_pf_violation.copy(deep=True)
    d_pf_prev=copy.deepcopy(d_pf)        
    iter_num_best=iter_num
    
    return d_raw_data_gen_prev_iter, num_gen_viol, Gen_pf_violation_prev_iter,  d_pf_prev, iter_num_best

    
