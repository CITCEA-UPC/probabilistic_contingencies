import os
import yaml

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

import GridCalEngine.Devices as gc
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from stability_analysis.powerflow import GridCal_powerflow
from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from stability_analysis.powerflow.process_powerflow import process_GridCal_PF_loadPQ
from stability_analysis.preprocess import preprocess_data, read_data, \
    process_raw
#%%
raw_file='../stability_analysis/stability_analysis/data/raw/ieee9_hypersim.raw'

# lines_info = pd.read_excel('./hypersim9buses/Lineas_9bus_IEEE_hypersim.xlsx')
# trafos_info = pd.read_excel('./hypersim9buses/Trafos_9bus_IEEE_hypersim.xlsx')
# #%%
# gridCal_grid = MultiCircuit()
# v_b = 230
# S_b=100
# f_b=60
# gridCal_grid.Sbase=S_b
# gridCal_grid.fBase=f_b

# bus1 = gc.Bus('Bus 1', vnom=24)
# bus1.code=1
# bus1.is_slack = True
# gridCal_grid.add_bus(bus1)

# bus2 = gc.Bus('Bus 2', vnom=18) 
# bus2.code=2
# gridCal_grid.add_bus(bus2)

# bus3 = gc.Bus('Bus 3', vnom=15.5)
# bus3.code=3
# gridCal_grid.add_bus(bus3)

# bus4 = gc.Bus('Bus 4', vnom=v_b)
# bus4.code=4
# gridCal_grid.add_bus(bus4)

# bus5 = gc.Bus('Bus 5', vnom=v_b)
# bus5.code=5
# gridCal_grid.add_bus(bus5)

# bus6 = gc.Bus('Bus 6', vnom=v_b)
# bus6.code=6
# gridCal_grid.add_bus(bus6)

# bus7 = gc.Bus('Bus 7', vnom=v_b)
# bus7.code=7
# gridCal_grid.add_bus(bus7)

# bus8 = gc.Bus('Bus 8', vnom=v_b)
# bus8.code=8
# gridCal_grid.add_bus(bus8)

# bus9 = gc.Bus('Bus 9', vnom=v_b)
# bus9.code=9
# gridCal_grid.add_bus(bus9)

# for bus in gridCal_grid.get_buses():
#     bus.Vm0=1
#     bus.Va0=0
#     # if bus.code=='1':
#     #     bus.Vm0=1.04
#     #     bus.Va0=0
#     # elif bus.code=='2' or bus.code=='3' or bus.code=='4' or bus.code=='7' or bus.code=='9':
#     #     bus.Vm0=1.03#2579
#     #     bus.Va0=0
#     # elif bus.code=='5':
#     #     bus.Vm0=1#0.99563
#     #     bus.Va0=0
#     # elif bus.code=='6':
#     #     bus.Vm0=1.01#265
#     #     bus.Va0=0
#     # elif bus.code=='8':
#     #     bus.Vm0= 1.02#15884            
#     #     bus.Va0=0
#     # # elif bus.code=='9':
#     # #     bus.Vm0=1.03235
#     # #     bus.Va0=0

# gen1 = gc.Generator('Slack Generator')
# gridCal_grid.add_generator(bus1, gen1)

# gen2 = gc.Generator('Generator 2')
# gridCal_grid.add_generator(bus2, gen2)

# gen3 = gc.Generator('Generator 3')
# gridCal_grid.add_generator(bus3, gen3)
    
# Snom_gen=[512,270,125]
# Pgen=[72,163,85]
# V_set=[1.04,1.025,1.025]

# for idx,gen in enumerate(gridCal_grid.get_generators()):
#     gen.Pmax=1e3
#     gen.Qmax=1e3
#     gen.Qmin=-1e3
    
#     gen.P=Pgen[idx]
#     gen.Snom=Snom_gen[idx]
#     gen.Vset=V_set[idx]

# gridCal_grid.add_load(bus5, gc.Load('load 5', P=125, Q=50))
# gridCal_grid.add_load(bus6, gc.Load('load 6', P=90, Q=30))
# gridCal_grid.add_load(bus8, gc.Load('load 8', P=100, Q=35))

# Pg_tot=sum([gen.P for gen in gridCal_grid.get_generators()]) 
# Pl_tot=sum([load.P for load in gridCal_grid.get_loads()]) 
# Ql_tot=sum([load.Q for load in gridCal_grid.get_loads()]) 

# gridCal_grid.add_line(gc.Line(bus4, bus5, 'line 4-5', r=lines_info.loc[0,'Rpu'], x=lines_info.loc[0,'Xpu'], b=lines_info.loc[0,'Bpu'], rate=1e6))
# gridCal_grid.add_line(gc.Line(bus4, bus6, 'line 4-6', r=lines_info.loc[1,'Rpu'], x=lines_info.loc[1,'Xpu'], b=lines_info.loc[1,'Bpu'], rate=1e6))
# gridCal_grid.add_line(gc.Line(bus5, bus7, 'line 5-7', r=lines_info.loc[2,'Rpu'], x=lines_info.loc[2,'Xpu'], b=lines_info.loc[2,'Bpu'], rate=1e6))
# gridCal_grid.add_line(gc.Line(bus6, bus9, 'line 6-9', r=lines_info.loc[3,'Rpu'], x=lines_info.loc[3,'Xpu'], b=lines_info.loc[3,'Bpu'], rate=1e6))
# gridCal_grid.add_line(gc.Line(bus7, bus8, 'line  7-8', r=lines_info.loc[4,'Rpu'], x=lines_info.loc[4,'Xpu'], b=lines_info.loc[4,'Bpu'], rate=1e6))
# gridCal_grid.add_line(gc.Line(bus8, bus9, 'line 8-9', r=lines_info.loc[5,'Rpu'], x=lines_info.loc[5,'Xpu'], b=lines_info.loc[5,'Bpu'], rate=1e6))

# gridCal_grid.add_transformer2w(gc.Transformer2W(bus1,bus4))    
# gridCal_grid.add_transformer2w(gc.Transformer2W(bus2,bus7))    
# gridCal_grid.add_transformer2w(gc.Transformer2W(bus3,bus9))    

# trafo_x=[0.0576,0.0625,0.0586]
# for tt,trafo in enumerate(gridCal_grid.transformers2w):
#     bf = int(trafo.bus_from.code)
#     bt = int(trafo.bus_to.code)
#     #t_info=trafos_info.query("bus_from == @bf and bus_to==@bt")
#     idx_trafo=trafos_info.query("bus_from == @bf and bus_to==@bt").index[0]
   
#     w=1#2*np.pi*50
#     trafos_info.loc[idx_trafo, 'Zp']=complex(trafos_info.loc[idx_trafo, 'Rp_pu'],trafos_info.loc[idx_trafo, 'Lp_pu']*w)
#     trafos_info.loc[idx_trafo, 'Zs']=complex(trafos_info.loc[idx_trafo, 'Rs_pu'],trafos_info.loc[idx_trafo, 'Ls_pu']*w)
#     #trafos_info.loc[idx_trafo, 'Zs"']=trafos_info.loc[idx_trafo, 'Zs']*(trafos_info.loc[idx_trafo, 'Vp']/trafos_info.loc[idx_trafo, 'Vs'])**2
#     #trafos_info.loc[idx_trafo, 'Zm']=1/(1/trafos_info.loc[idx_trafo, 'Rm']+1/complex(0,2*np.pi*trafos_info.loc[idx_trafo, 'Lm']))
#     trafos_info.loc[idx_trafo, 'Zm_par']=complex(0,trafos_info.loc[idx_trafo, 'Rm_pu']*trafos_info.loc[idx_trafo, 'Lm_pu']*w)/complex(trafos_info.loc[idx_trafo, 'Rm_pu'],trafos_info.loc[idx_trafo, 'Lm_pu']*w)
    
#     Z1= trafos_info.loc[idx_trafo, 'Zs']+trafos_info.loc[idx_trafo, 'Zp']
#     Z2= trafos_info.loc[idx_trafo, 'Zm_par']
    
#     # Z3=Z1+1/Z2
#     # trafos_info.loc[idx_trafo, 'R']=np.real(Z3)#np.real(trafos_info.loc[idx_trafo, 'Zp']+trafos_info.loc[idx_trafo, 'Zs"']+trafos_info.loc[idx_trafo, 'Zm_par'])
#     # trafos_info.loc[idx_trafo, 'X']=np.imag(Z3)#np.imag(trafos_info.loc[idx_trafo, 'Zp']+trafos_info.loc[idx_trafo, 'Zs"']+trafos_info.loc[idx_trafo, 'Zm_par'])
    
#     Zbase=1#trafos_info.loc[idx_trafo, 'Vp']**2/gridCal_grid.Sbase/1e6
#     trafos_info.loc[idx_trafo, 'R_pu']=np.real(Z1)/Zbase
#     trafos_info.loc[idx_trafo, 'X_pu']=np.imag(Z1)/Zbase
#     trafos_info.loc[idx_trafo, 'G_pu']=1/5000#♣trafos_info.loc[idx_trafo, 'Rm_pu']#np.real(1/Z2)*Zbase
#     trafos_info.loc[idx_trafo, 'B_pu']=1/5000#trafos_info.loc[idx_trafo, 'Lm_pu']#abs(np.imag(1/Z2)*Zbase)
    
#     trafo.R=0#np.real(Z1)/Zbase
#     trafo.X=np.imag(Z1)/Zbase
    
#     trafo.G=1/5000#np.real(1/Z2)*Zbase
#     trafo.B=1/5000#np.imag(1/Z2)*Zbase
    
#     # trafo.R=trafos_info.loc[idx_trafo, 'R_pu']
#     # trafo.X=trafos_info.loc[idx_trafo, 'X_pu']
    
#     trafo.rate = 1e10
    
    
#     # trafo.rate = lines_ratings.loc[
#     #     lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
#     #         0], 'Max Flow (MW)']

    
# #%%
    
# # Get Power-Flow results with GridCal
# #SolverType.IWAMOTO, SolverType.NR, SolverType.LM, SolverType.FASTDECOUPLED
# pf_results = GridCal_powerflow.run_powerflow(gridCal_grid,solver_type=SolverType.NR, Qconrol_mode=ReactivePowerControlMode.NoControl)

# print('Converged:', pf_results.convergence_reports[0].converged_[0])

# pf_bus, pf_load, pf_gen = process_GridCal_PF_loadPQ(gridCal_grid, pf_results)
# Sf=pf_results.results.Sf

#%%
d_raw_data = process_raw.read_raw(raw_file)
preprocess_data.preprocess_raw(d_raw_data)

gridCal_gri_raw= GridCal_powerflow.create_model(raw_file)
gridCal_gri_raw.fBase=60

for gen in gridCal_gri_raw.get_generators():
    gen.Pf=0.95
#%%
pf_results_raw = GridCal_powerflow.run_powerflow(gridCal_gri_raw,solver_type=SolverType.NR, Qconrol_mode=ReactivePowerControlMode.Direct)

print('Converged:', pf_results_raw.convergence_reports[0].converged_[0])

pf_bus_raw, pf_load_raw, pf_gen_raw = process_GridCal_PF_loadPQ(gridCal_gri_raw, pf_results_raw)
Sf=pf_results_raw.results.Sf

#%%
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf, ac_optimal_power_flow
from stability_analysis.optimal_power_flow import process_optimal_power_flow
from datagen.src.utils_obj_fun import additional_info_OPF_results

excel_op = "OperationData_IEEE_9_hypersim"

excel_op = os.path.join('../stability_analysis/stability_analysis/data/', "cases", excel_op + ".xlsx")
d_op = read_data.read_data(excel_op)

for idx_gen,gen in enumerate(gridCal_gri_raw.get_generators()):
    gen.Pmax=d_op['Generators'].loc[idx_gen,'Pmax']
    gen.Pmin=d_op['Generators'].loc[idx_gen,'Pmin']
    gen.Qmax=d_op['Generators'].loc[idx_gen,'Qmax']
    gen.Qmin=d_op['Generators'].loc[idx_gen,'Qmin']
    
    gridCal_gri_raw.transformers2w[idx_gen].rate=gen.Snom
    

# for load in gridCal_gri_raw.loads:
#     load.Q=0
    
for line in gridCal_gri_raw.get_branches():
    print(line.rate)#=1e6
    
nc = compile_numerical_circuit_at(gridCal_gri_raw)
nc.generator_data.cost_0[:] = 0
nc.generator_data.cost_1[:] = 0
nc.generator_data.cost_2[:] = 0
pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, tolerance=1e-8, control_q=ReactivePowerControlMode.Direct)#, max_iter=100)
opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NR, verbose=0, ips_tolerance=1e-8, ips_iterations=50)

#    d_opf_results = ac_optimal_power_flow(Pref=np.array(d_pf_original['pf_gen']['P']), slack_bus_num=i_slack, nc=nc, pf_options=pf_options, plot_error=True)


pf_results = multi_island_pf_nc(nc=nc, options=pf_options)

d_opf_results = ac_optimal_power_flow(nc= nc,
                                      pf_options= pf_options,
                                      opf_options= opf_options,
                                      # debug: bool = False,
                                      #use_autodiff = True,
                                      pf_init= True,
                                      Sbus_pf= pf_results.Sbus,
                                      voltage_pf= pf_results.voltage,
                                      plot_error= True)


try: 
    d_raw_data['generator']['Region']
except:
    d_raw_data['generator']['Region']=1
    
d_opf = process_optimal_power_flow.update_OP(gridCal_gri_raw, d_opf_results, d_raw_data)
d_opf['info']=pd.DataFrame()
d_opf = additional_info_OPF_results(d_opf,0, 0, d_opf_results)
