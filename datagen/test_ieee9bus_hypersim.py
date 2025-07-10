import random
import os
import yaml
from datetime import datetime

from datagen import parse_args, parse_setup_file
from datagen.src.dimensions import Dimension
from datagen.src.start_app import start
from datagen.src.objective_function_ACOPF import feasible_power_flow_ACOPF

from stability_analysis.preprocess import preprocess_data, read_data, \
    process_raw
from stability_analysis.powerflow import GridCal_powerflow
from stability_analysis.preprocess.utils import *

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
except ImportError:
    from datagen.dummies.task import task
    from datagen.dummies.api import compss_wait_on

import warnings
warnings.filterwarnings("ignore")

import GridCalEngine.Devices as gc
from GridCalEngine.Devices.multi_circuit import MultiCircuit


@task()
def main(working_dir='', path_data='', setup_path=''):
    # %% Parse arguments (emulate sys.argv list as input)
    working_dir, path_data, setup_path = parse_args(
        [None, working_dir, path_data, setup_path])
    (generators_power_factor, grid_name, loads_power_factor, n_cases, n_pf,
     n_samples, seed, v_min_v_max_delta_v, voltage_profile, rel_tolerance,
     max_depth, setup_dict) = \
        parse_setup_file(setup_path)

    # Slurm configuration
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)
    # Get computing units assigned to the objective function
    cu = os.environ.get("COMPUTING_UNITS", default=None)
    cu_str = ""
    if cu:
        cu_str = f"_cu{cu}"
    print("COMPUTING_UNITS: ", cu)
    # Get slurm job id
    slurm_job_id = os.getenv("SLURM_JOB_ID", default=None)
    slurm_str = ""
    if slurm_job_id:
        slurm_str = f"_slurm{slurm_job_id}"
    # Get slurm n_nodes
    slurm_num_nodes = os.environ.get('SLURM_JOB_NUM_NODES', default=None)
    slurm_nodes_str = ""
    if slurm_num_nodes:
        slurm_nodes_str = f"_nodes{slurm_num_nodes}"
    print("NUMBER OF NODES: ", slurm_num_nodes)
    print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%", flush=True)

    # CASE CONFIGURATION
    # Create unique directory name for results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd_num = random.randint(1000, 9999)
    dir_name = f"datagen_ACOPF{slurm_str}{cu_str}{slurm_nodes_str}_LF09_seed{seed}_nc{n_cases}" \
               f"_ns{n_samples}_d{max_depth}_{timestamp}_{rnd_num}"
    path_results = os.path.join(
        working_dir, "results", dir_name)
    if not os.path.isdir(path_results):
        os.makedirs(path_results)

    # Save yaml setup in the results directory
    with open(os.path.join(path_results, 'case_setup.yaml'), 'w') as f:
        yaml.dump(setup_dict, f)

    # %% SET FILE NAMES AND PATHS
    if grid_name == 'IEEE9':
        # IEEE 9
        raw = "ieee9_hypersim_trans"
        excel_headers = "IEEE_9_headers"
        excel_data = "IEEE_9"
        excel_op = "OperationData_IEEE_9"
        excel_trafos = 'trafos_ieee9buses'
        excel_lines = 'lineas_ieee9buses'
    elif grid_name == 'IEEE118':
        # IEEE 118
        raw = "IEEE118busNREL"
        # excel_headers = "IEEE_118bus_TH"  # THÉVENIN
        # excel_headers = "IEEE_118_01"  # SG
        excel_headers = "IEEE_118_FULL_headers"
        excel_data = "IEEE_118_FULL"
        excel_op = "OperationData_IEEE_118_NREL"
        excel_lines_ratings = "IEEE_118_Lines"
    else:
        raise ValueError(f"Grid {grid_name} not implemented")

    raw_file = os.path.join(path_data, "raw", raw + ".raw")
    excel_sys = os.path.join(path_data, "cases", excel_headers + ".xlsx")
    excel_sg = os.path.join(path_data, "cases", excel_data + "_data_sg.xlsx")
    excel_vsc = os.path.join(path_data, "cases", excel_data + "_data_vsc.xlsx")
    excel_op = os.path.join(path_data, "cases", excel_op + ".xlsx")
    if grid_name == 'IEEE118':
        excel_lines_ratings = os.path.join(
            path_data, "cases", excel_lines_ratings + ".csv")
    if grid_name == 'IEEE9':
        excel_trafos = os.path.join(
            path_data, "cases", excel_trafos + ".xlsx")
        excel_lines = os.path.join(
                path_data, "cases", excel_lines + ".xlsx")

    # %% READ OPERATION EXCEL FILE
    d_op = read_data.read_data(excel_op)

    # %% READ RAW FILE
    d_raw_data = process_raw.read_raw(raw_file)

    if grid_name == 'IEEE9':
        # For the IEEE 9-bus system
        d_raw_data['generator']['Region'] = 1
        d_raw_data['load']['Region'] = 1
        d_raw_data['branch']['Region'] = 1
        d_raw_data['results_bus']['Region'] = 1
        trafos_info = pd.read_excel(excel_trafos,sheet_name='data_pu')
        lines_info = pd.read_excel(excel_lines,sheet_name='data_from_hypersim')

    elif grid_name == 'IEEE118':
        # FOR the 118-bus system
        d_raw_data['generator']['Region'] = d_op['Generators']['Region']
        d_raw_data['load']['Region'] = d_op['Loads']['Region']
        # d_raw_data['branch']['Region']=1
        d_raw_data['results_bus']['Region'] = d_op['Buses']['Region']
        d_raw_data['generator']['MBASE'] = d_op['Generators']['Snom']
        lines_ratings = pd.read_csv(excel_lines_ratings)

    # Preprocess input raw data to match Excel file format
    preprocess_data.preprocess_raw(d_raw_data)

    # %% Create GridCal Model
    # gridCal_grid = GridCal_powerflow.create_model(raw_file)
    gridCal_grid = MultiCircuit()
    v_b = 230
    S_b=100
    
    Sg1=512
    Sg2=270
    Sg3=125

    bus1 = gc.Bus('Bus 1', vnom=24)
    bus1.code=1
    bus1.is_slack = True
    gridCal_grid.add_bus(bus1)
    
    bus2 = gc.Bus('Bus 2', vnom=18) 
    bus2.code=2
    gridCal_grid.add_bus(bus2)
    
    bus3 = gc.Bus('Bus 3', vnom=15.5)
    bus3.code=3
    gridCal_grid.add_bus(bus3)
    
    bus4 = gc.Bus('Bus 4', vnom=v_b)
    bus4.code=4
    gridCal_grid.add_bus(bus4)
    
    bus5 = gc.Bus('Bus 5', vnom=v_b)
    bus5.code=5
    gridCal_grid.add_bus(bus5)
    
    bus6 = gc.Bus('Bus 6', vnom=v_b)
    bus6.code=6
    gridCal_grid.add_bus(bus6)
    
    bus7 = gc.Bus('Bus 7', vnom=v_b)
    bus7.code=7
    gridCal_grid.add_bus(bus7)
    
    bus8 = gc.Bus('Bus 8', vnom=v_b)
    bus8.code=8
    gridCal_grid.add_bus(bus8)
    
    bus9 = gc.Bus('Bus 9', vnom=v_b)
    bus9.code=9
    gridCal_grid.add_bus(bus9)
    
    for bus in gridCal_grid.get_buses():
    #     bus.Vm0=1
    #     bus.Va0=0
        if bus.code=='1':
            bus.Vm0=1.04
            bus.Va0=0
        elif bus.code=='2' or bus.code=='3' or bus.code=='4' or bus.code=='7' or bus.code=='9':
            bus.Vm0=1.03#2579
            bus.Va0=0
        elif bus.code=='5':
            bus.Vm0=1#0.99563
            bus.Va0=0
        elif bus.code=='6':
            bus.Vm0=1.01#265
            bus.Va0=0
        elif bus.code=='8':
            bus.Vm0= 1.02#15884            
            bus.Va0=0
        # elif bus.code=='9':
        #     bus.Vm0=1.03235
        #     bus.Va0=0

    gen1 = gc.Generator('Slack Generator',P=72)
    gridCal_grid.add_generator(bus1, gen1)
    
    gen2 = gc.Generator('Generator 2',P=163)
    gridCal_grid.add_generator(bus2, gen2)
    
    gen3 = gc.Generator('Generator 3', P=85)
    gridCal_grid.add_generator(bus3, gen3)
    
        
    for gen in gridCal_grid.get_generators():
        gen.Pmax=1e3
        gen.Qmax=1e3
        gen.Qmin=-1e3
    
        if gen.bus.code==1:
            gen.Vset=1.04#17.1600/24 # 
        elif gen.bus.code==2:
            gen.Vset=1.03#1.025#2579
        elif gen.bus.code==3:
            gen.Vset=1.03#14.145/15.5
        
        # bus = gen._bus
        # if bus.is_slack:
        #     gen.Vset=1
        # bus.Vm0=1
        # bus.Va0=0
           
    
    
    gridCal_grid.add_load(bus5, gc.Load('load 5', P=125, Q=50))
    
    
    gridCal_grid.add_load(bus6, gc.Load('load 6', P=90, Q=30))
    
    
    gridCal_grid.add_load(bus8, gc.Load('load 8', P=100, Q=35))
    
    Pg_tot=sum([gen.P for gen in gridCal_grid.get_generators()]) 
    Pl_tot=sum([load.P for load in gridCal_grid.get_loads()]) 
    Ql_tot=sum([load.Q for load in gridCal_grid.get_loads()]) 
    
    
    # for line in gridCal_grid.get_branches()[:-3]:
    #     line.rate=1e10
        
    #     bf = int(line.bus_from.code)
    #     bt = int(line.bus_to.code)
    #     #t_info=trafos_info.query("bus_from == @bf and bus_to==@bt")
    #     idx_line=lines_info.query("bus_from == @bf and bus_to==@bt").index[0]
    #     line.R=lines_info.loc[idx_line,'Rpu']
    #     line.X=lines_info.loc[idx_line,'Xpu']
    #     line.B=lines_info.loc[idx_line,'Bpu']
        
    gridCal_grid.add_line(gc.Line(bus4, bus5, 'line 4-5', r=lines_info.loc[0,'Rpu'], x=lines_info.loc[0,'Xpu'], b=lines_info.loc[0,'Bpu'], rate=1e6))
    gridCal_grid.add_line(gc.Line(bus4, bus6, 'line 4-6', r=lines_info.loc[1,'Rpu'], x=lines_info.loc[1,'Xpu'], b=lines_info.loc[1,'Bpu'], rate=1e6))
    gridCal_grid.add_line(gc.Line(bus5, bus7, 'line 5-7', r=lines_info.loc[2,'Rpu'], x=lines_info.loc[2,'Xpu'], b=lines_info.loc[2,'Bpu'], rate=1e6))
    gridCal_grid.add_line(gc.Line(bus6, bus9, 'line 6-9', r=lines_info.loc[3,'Rpu'], x=lines_info.loc[3,'Xpu'], b=lines_info.loc[3,'Bpu'], rate=1e6))
    gridCal_grid.add_line(gc.Line(bus7, bus8, 'line  7-8', r=lines_info.loc[4,'Rpu'], x=lines_info.loc[4,'Xpu'], b=lines_info.loc[4,'Bpu'], rate=1e6))
    gridCal_grid.add_line(gc.Line(bus8, bus9, 'line 8-9', r=lines_info.loc[5,'Rpu'], x=lines_info.loc[5,'Xpu'], b=lines_info.loc[5,'Bpu'], rate=1e6))
    
    gridCal_grid.add_transformer2w(gc.Transformer2W(bus1,bus4))    
    gridCal_grid.add_transformer2w(gc.Transformer2W(bus2,bus7))    
    gridCal_grid.add_transformer2w(gc.Transformer2W(bus3,bus9))    
   
     
#%%    
    
    for trafo in gridCal_grid.transformers2w:
        bf = int(trafo.bus_from.code)
        bt = int(trafo.bus_to.code)
        #t_info=trafos_info.query("bus_from == @bf and bus_to==@bt")
        idx_trafo=trafos_info.query("bus_from == @bf and bus_to==@bt").index[0]
       
        w=1#2*np.pi*50
        trafos_info.loc[idx_trafo, 'Zp']=complex(trafos_info.loc[idx_trafo, 'Rp'],trafos_info.loc[idx_trafo, 'Lp']*w)
        trafos_info.loc[idx_trafo, 'Zs']=complex(trafos_info.loc[idx_trafo, 'Rs'],trafos_info.loc[idx_trafo, 'Ls']*w)
        trafos_info.loc[idx_trafo, 'Zs"']=trafos_info.loc[idx_trafo, 'Zs']*(trafos_info.loc[idx_trafo, 'Vp']/trafos_info.loc[idx_trafo, 'Vs'])**2
        #trafos_info.loc[idx_trafo, 'Zm']=1/(1/trafos_info.loc[idx_trafo, 'Rm']+1/complex(0,2*np.pi*trafos_info.loc[idx_trafo, 'Lm']))
        trafos_info.loc[idx_trafo, 'Zm_par']=complex(0,trafos_info.loc[idx_trafo, 'Rm']*trafos_info.loc[idx_trafo, 'Lm']*w)/complex(trafos_info.loc[idx_trafo, 'Rm'],trafos_info.loc[idx_trafo, 'Lm']*w)
        
        Z1= trafos_info.loc[idx_trafo, 'Zs"']+trafos_info.loc[idx_trafo, 'Zp']
        Z2= trafos_info.loc[idx_trafo, 'Zm_par']
        
        # Z3=Z1+1/Z2
        # trafos_info.loc[idx_trafo, 'R']=np.real(Z3)#np.real(trafos_info.loc[idx_trafo, 'Zp']+trafos_info.loc[idx_trafo, 'Zs"']+trafos_info.loc[idx_trafo, 'Zm_par'])
        # trafos_info.loc[idx_trafo, 'X']=np.imag(Z3)#np.imag(trafos_info.loc[idx_trafo, 'Zp']+trafos_info.loc[idx_trafo, 'Zs"']+trafos_info.loc[idx_trafo, 'Zm_par'])
        
        Zbase=1#trafos_info.loc[idx_trafo, 'Vp']**2/gridCal_grid.Sbase/1e6
        trafos_info.loc[idx_trafo, 'R_pu']=np.real(Z1)/Zbase
        trafos_info.loc[idx_trafo, 'X_pu']=np.imag(Z1)/Zbase
        trafos_info.loc[idx_trafo, 'G_pu']=np.real(1/Z2)/Zbase
        trafos_info.loc[idx_trafo, 'B_pu']=np.imag(1/Z2)/Zbase
        
        trafo.R=np.real(Z1)/Zbase
        trafo.X=np.imag(Z1)/Zbase
        
        trafo.G=np.real(1/Z2)*Zbase
        trafo.B=np.imag(1/Z2)*Zbase
        
        # trafo.R=trafos_info.loc[idx_trafo, 'R_pu']
        # trafo.X=trafos_info.loc[idx_trafo, 'X_pu']
        
        trafo.rate = 1e10
        
        
        # trafo.rate = lines_ratings.loc[
        #     lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
        #         0], 'Max Flow (MW)']

        
    
    from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
    
        
    # Get Power-Flow results with GridCal
    #SolverType.IWAMOTO, SolverType.NR, SolverType.LM, SolverType.FASTDECOUPLED
    pf_results = GridCal_powerflow.run_powerflow(gridCal_grid,solver_type=SolverType.NR, Qconrol_mode=ReactivePowerControlMode.NoControl)

    print('Converged:', pf_results.convergence_reports[0].converged_[0])
    
    from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
    from stability_analysis.powerflow.process_powerflow import process_GridCal_PF_loadPQ
    pf_bus, pf_load, pf_gen = process_GridCal_PF_loadPQ(gridCal_grid, pf_results)

    # # for line in gridCal_grid.lines:
    # #     bf = int(line.bus_from.code)
    # #     bt = int(line.bus_to.code)
    # #     line.rate = lines_ratings.loc[
    # #         lines_ratings.query('Bus_from == @bf and Bus_to == @bt').index[
    # #             0], 'Max Flow (MW)']


    # # %% READ EXCEL FILE
    # # Read data of grid elements from Excel file
    # d_grid, d_grid_0 = read_data.read_sys_data(excel_sys)
    # # TO BE DELETED
    # d_grid = read_data.tempTables(d_grid)

    # # %% READ EXEC FILES WITH SG AND VSC CONTROLLERS PARAMETERS
    # d_sg = read_data.read_data(excel_sg)
    # d_vsc = read_data.read_data(excel_vsc)

    # # %% CONFIGURATION OF DIMENSIONS FOR THE DATA GENERATOR
    # # Set up dimensions for generators, converters and loads
    # p_sg = []
    # p_cig = []
    # for i in range(len(d_op['Generators'])):
    #     p_sg.append((d_op['Generators']['Pmin_SG'].iloc[i],
    #                  d_op['Generators']['Pmax_SG'].iloc[i]))
    #     p_cig.append((d_op['Generators']['Pmin_CIG'].iloc[i],
    #                   d_op['Generators']['Pmax_CIG'].iloc[i]))

    # p_loads = list(d_op['Loads']['Load_Participation_Factor'])

    # dimensions = [
    #     Dimension(label="p_sg", variable_borders=p_sg,
    #               n_cases=n_cases, divs=2,
    #               borders=(d_op['Generators']['Pmin_SG'].sum(),
    #                        d_op['Generators']['Pmax_SG'].sum()),
    #               independent_dimension=True, cosphi=generators_power_factor),
    #     Dimension(label="p_cig", variable_borders=p_cig,
    #               n_cases=n_cases, divs=1,
    #               borders=(d_op['Generators']['Pmin_CIG'].sum(),
    #                        d_op['Generators']['Pmax_CIG'].sum()),
    #               independent_dimension=True,
    #               cosphi=generators_power_factor),
    #     Dimension(label="perc_g_for", variable_borders=[(0, 1)],
    #               n_cases=n_cases, divs=1, borders=(0, 1),
    #               independent_dimension=True, cosphi=None),
    #     Dimension(label="p_load", values=p_loads,
    #               n_cases=n_cases, divs=1,
    #               independent_dimension=False,
    #               cosphi=loads_power_factor)
    # ]

    # # Set up independent dimensions (controllers)
    # for d in list(d_op['Generators']['BusNum']):
    #     dimensions.append(
    #         Dimension(label='tau_droop_f_gfor_' + str(d), n_cases=n_cases,
    #                   divs=1, borders=(0.01, 0.2),
    #                   independent_dimension=True,
    #                   cosphi=None))
    #     dimensions.append(
    #         Dimension(label='tau_droop_u_gfor_' + str(d), n_cases=n_cases,
    #                   divs=1, borders=(0.01, 0.2),
    #                   independent_dimension=True,
    #                   cosphi=None))
    #     dimensions.append(
    #         Dimension(label='tau_droop_f_gfol_' + str(d), n_cases=n_cases,
    #                   divs=1, borders=(0.01, 0.2),
    #                   independent_dimension=True,
    #                   cosphi=None))
    #     dimensions.append(
    #         Dimension(label='tau_droop_u_gfol_' + str(d), n_cases=n_cases,
    #                   divs=1, borders=(0.01, 0.2),
    #                   independent_dimension=True,
    #                   cosphi=None))

    # # %% RUN OBJECTIVE FUNCTION
    # func_params = {"n_pf": n_pf, "d_raw_data": d_raw_data, "d_op": d_op,
    #                "gridCal_grid": gridCal_grid, "d_grid": d_grid,
    #                "d_sg": d_sg,
    #                "d_vsc": d_vsc, "voltage_profile": voltage_profile,
    #                "v_min_v_max_delta_v": v_min_v_max_delta_v}

    # stability_array = []
    # output_dataframes_array = []
    # cases_df, dims_df, execution_logs, output_dataframes = start(
    #     dimensions=dimensions, n_samples=n_samples,
    #     rel_tolerance=rel_tolerance, func=feasible_power_flow_ACOPF,
    #     max_depth=max_depth, seed=seed, func_params=func_params,
    #     dst_dir=path_results
    # )

    # stability_array = compss_wait_on(stability_array)
    # output_dataframes_array = compss_wait_on(output_dataframes_array)
#%%

if __name__ == "__main__":
    main(setup_path="./setup/test_setup.yaml")
