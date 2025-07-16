import numpy as np
import pandas as pd

from stability_analysis.state_space import generate_NET
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults

def update_OP(GridCal_grid, pf_results, d_raw_data):
# def update_OP_PFsolution(GridCal_grid, pf_results):
    
    # Process GridCal PowerFlow raw pf_results
    pf_bus, pf_load, pf_gen = process_GridCal_PF_loadPQ(GridCal_grid, pf_results)
        
    d_pf = {'pf_bus':pf_bus, 'pf_load': pf_load, 'pf_gen': pf_gen}
    
    d_pf = assign_region_to_generator(d_pf,d_raw_data)
    
    return d_pf
    
def update_OP_OPFsolution(GridCal_grid, pf_results):
    
    # Process GridCal PowerFlow raw pf_results
    pf_bus, pf_load, pf_gen = process_GridCal_PF_loadPQ_OPFsol(GridCal_grid, pf_results)
        
    d_pf = {'pf_bus':pf_bus, 'pf_load': pf_load, 'pf_gen': pf_gen}
    
    return d_pf
    
    

def process_GridCal_PF_loadPQ_onlyGen(GridCal_grid, pf_results):
    
    Sbase = GridCal_grid.Sbase
    
    # pf_bus: voltage and angle in buses
    
    bus = [int(bus) for bus in [bus.code for bus in GridCal_grid.buses]]
    Vm = np.abs(pf_results.results.voltage)
    theta = np.angle(pf_results.results.voltage, deg=True) 
    pf_bus = pd.DataFrame({'bus':bus, 'Vm': Vm, 'theta':theta, 'type':pf_results.results.bus_types})
            
    # pf_load: active and reactive power in loads
    
    bus_load = [int(load.bus.code) for load in GridCal_grid.get_loads()] 
    idx_load = [i for load_bus in bus_load for i, b in enumerate(bus) if b == load_bus]
    Vm = np.abs([pf_results.results.voltage[idx] for idx in idx_load])
    theta = np.angle([pf_results.results.voltage[idx] for idx in idx_load], deg=True) 
    P = np.array([pf_results.grid.buses[idx].loads[0].P for idx in idx_load])/Sbase
    Q = np.array([pf_results.grid.buses[idx].loads[0].Q for idx in idx_load])/Sbase
    pf_load = pd.DataFrame({'bus':bus_load, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q})
    
    #pf_gen: active and reactive power in generator buses
    
    bus_gen = [int(gen.bus.code) for gen in GridCal_grid.get_generators()]   
    idx_gen = [i for gen_bus in bus_gen for i, b in enumerate(bus) if b == gen_bus] 
    Vm = np.abs([pf_results.results.voltage[idx] for idx in idx_gen])
    theta = np.angle([pf_results.results.voltage[idx] for idx in idx_gen], deg=True) 
    P = [(np.real(pf_results.results.Sbus[idx]) + (pf_results.grid.buses[idx].loads[0].P if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    Q = [(np.imag(pf_results.results.Sbus[idx]) + (pf_results.grid.buses[idx].loads[0].Q if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    
    cosphi= np.cos(np.arctan(Q/P))
    pf_gen = pd.DataFrame({'bus':bus_gen, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q,'cosphi':cosphi})
    
    return pf_bus, pf_load, pf_gen

def process_GridCal_PF_loadPQ(GridCal_grid, pf_results):
    
    Sbase = GridCal_grid.Sbase
    
    # pf_bus: voltage and angle in buses
    
    bus = [int(bus) for bus in [bus.code for bus in GridCal_grid.buses]]
       
    Vm = np.abs(pf_results.results.voltage)
    theta = np.angle(pf_results.results.voltage, deg=True) 
    P= list(PowerFlowResults.get_bus_df(pf_results.results)['P'])
    Q= list(PowerFlowResults.get_bus_df(pf_results.results)['Q'])
    pf_bus = pd.DataFrame({'bus':bus, 'Vm': Vm, 'theta':theta,'P':P,'Q':Q, 'type':pf_results.results.bus_types})
        
    # pf_load: active and reactive power in loads
    
    bus_load = [int(load.bus.code) for load in GridCal_grid.get_loads()]   
    idx_load = [i for i, bus in enumerate(bus) if bus in bus_load]   
    Vm = np.abs([pf_results.results.voltage[idx] for idx in idx_load])
    theta = np.angle([pf_results.results.voltage[idx] for idx in idx_load], deg=True)     
    
    P = np.array([load.P for load in GridCal_grid.loads])/Sbase
    Q = np.array([load.Q for load in GridCal_grid.loads])/Sbase
    
    # B = np.array([pf_results.grid.buses[idx].loads[0].B for idx in idx_load])
    # Ir = np.array([pf_results.grid.buses[idx].loads[0].Ir for idx in idx_load])
    # P = Ir
    # Q=abs(B)
    
    pf_load = pd.DataFrame({'bus':bus_load, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q})

    #pf_gen: active and reactive power in generator buses
    
    bus_gen = [int(gen.bus.code) for gen in GridCal_grid.get_generators() + GridCal_grid.get_static_generators()]   
    idx_gen = [np.where(np.array(bus)==b)[0][0] for b in bus_gen]

    Vm = np.abs([pf_results.results.voltage[idx] for idx in idx_gen])
    theta = np.angle([pf_results.results.voltage[idx] for idx in idx_gen], deg=True) 
    
    P=[]
    Q=[]
    
    for gen in GridCal_grid.get_generators():
        idx=np.where(np.array(bus)==int(gen.bus.code))[0][0]
        
        P_bus=np.real(pf_results.results.Sbus[idx])/Sbase
        Q_bus=np.imag(pf_results.results.Sbus[idx])/Sbase
        
        try:
            idx=np.where(np.array(bus_load)==int(gen.bus.code))[0][0]
        except:
            idx=None

        if idx != None:
            P_load= GridCal_grid.loads[idx].P/Sbase
            Q_load= GridCal_grid.loads[idx].Q/Sbase
        else: 
            P_load=0
            Q_load=0
            
        P.append(P_bus+P_load)
        Q.append(Q_bus+Q_load)

    cosphi= np.cos(np.arctan(np.array(Q)/np.array(P)))
        
    pf_gen = pd.DataFrame({'bus':bus_gen, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q,'cosphi':cosphi})
    # pf_gen['PF']=n_pf
    # pf_gen['cos_phi']=np.cos(np.arctan(pf_gen['Q']/pf_gen['P']))

    return pf_bus, pf_load, pf_gen

def process_GridCal_PF_loadPQ_OPFsol(GridCal_grid, pf_results):
    
    Sbase = GridCal_grid.Sbase
    
    # pf_bus: voltage and angle in buses
    
    bus = [int(bus) for bus in [bus.code for bus in GridCal_grid.buses]]
       
    Vm = np.abs(pf_results.voltage)
    theta = np.angle(pf_results.voltage, deg=True) 
    P= list(PowerFlowResults.get_bus_df(pf_results)['P'])
    Q= list(PowerFlowResults.get_bus_df(pf_results)['Q'])
    pf_bus = pd.DataFrame({'bus':bus, 'Vm': Vm, 'theta':theta,'P':P,'Q':Q, 'type':pf_results.bus_types})
        
    # pf_load: active and reactive power in loads
    
    bus_load = [int(load.bus.code) for load in GridCal_grid.get_loads()]   
    idx_load = [i for i, bus in enumerate(bus) if bus in bus_load]   
    Vm = np.abs([pf_results.voltage[idx] for idx in idx_load])
    theta = np.angle([pf_results.voltage[idx] for idx in idx_load], deg=True)     
    P = np.array([GridCal_grid.buses[idx].loads[0].P for idx in idx_load])/Sbase
    Q = np.array([GridCal_grid.buses[idx].loads[0].Q for idx in idx_load])/Sbase
    
    # B = np.array([pf_results.grid.buses[idx].loads[0].B for idx in idx_load])
    # Ir = np.array([pf_results.grid.buses[idx].loads[0].Ir for idx in idx_load])
    # P = Ir
    # Q=abs(B)
    
    pf_load = pd.DataFrame({'bus':bus_load, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q})

    #pf_gen: active and reactive power in generator buses
    
    bus_gen = [int(gen.bus.code) for gen in GridCal_grid.get_generators() + GridCal_grid.get_static_generators()]   
    idx_gen = [np.where(np.array(bus)==b)[0][0] for b in bus_gen]
  
    Vm = np.abs([pf_results.voltage[idx] for idx in idx_gen])
    theta = np.angle([pf_results.voltage[idx] for idx in idx_gen], deg=True) 
    P = [(np.real(pf_results.Sbus[idx]) + (GridCal_grid.buses[idx].loads[0].P if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    Q = [(np.imag(pf_results.Sbus[idx]) + (GridCal_grid.buses[idx].loads[0].Q if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    
    # Qmin= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Qmin']/Sbase for bus_gen_i in bus_gen]
    # Qmax= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Qmax']/Sbase for bus_gen_i in bus_gen]
    # Pmin= [0 for bus_gen_i in bus_gen]
    # Pmax= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Pmax_TOT']/Sbase for bus_gen_i in bus_gen]

    # Pg_i= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Pg_i']/Sbase for bus_gen_i in bus_gen]
    # Qg_i= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Qg_i']/Sbase for bus_gen_i in bus_gen]
    
    cosphi= np.cos(np.arctan(np.array(Q)/np.array(P)))
    pf_gen = pd.DataFrame({'bus':bus_gen, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q,'cosphi':cosphi})
    # pf_gen['PF']=n_pf
    # pf_gen['cos_phi']=np.cos(np.arctan(pf_gen['Q']/pf_gen['P']))

    return pf_bus, pf_load, pf_gen

def assign_region_to_generator(d_pf,d_raw_data):
    for b in range(0,len(d_pf['pf_gen'])):
        bus=d_pf['pf_gen'].loc[b,'bus']
        d_pf['pf_gen'].loc[b,'Region']=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus').index[0],'Region']
    return d_pf
