import numpy as np
import pandas as pd
import numpy as np
import GridCalEngine.api as gce

def process_GridCal_PF_loadPQ(GridCal_grid, pf_results):
    
    Sbase = GridCal_grid.Sbase
    
    # pf_bus: voltage and angle in buses
    
    bus = [int(bus) for bus in [bus.code for bus in GridCal_grid.buses]]
    Vm = np.abs(pf_results.results.voltage)
    theta = np.angle(pf_results.results.voltage, deg=True) 
    pf_bus = pd.DataFrame({'bus':bus, 'Vm': Vm, 'theta':theta, 'type':pf_results.results.bus_types})
            
    # pf_load: active and reactive power in loads
    
#    bus_load = [int(load.bus.name) for load in GridCal_grid.get_loads()]   
    bus_load = [int(load.bus.code) for load in GridCal_grid.get_loads()]   
    idx_load = [i for i, bus in enumerate(bus) if bus in bus_load]  
    Vm = np.abs([pf_results.results.voltage[idx] for idx in idx_load])
    theta = np.angle([pf_results.results.voltage[idx] for idx in idx_load], deg=True) 
    P = np.array([pf_results.grid.buses[idx].loads[0].P for idx in idx_load])/Sbase
    Q = np.array([pf_results.grid.buses[idx].loads[0].Q for idx in idx_load])/Sbase
    
    pf_load = pd.DataFrame({'bus':bus_load, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q})
    
    #pf_gen: active and reactive power in generator buses
    
#    bus_gen = [int(gen.bus.name) for gen in GridCal_grid.get_generators()]   
    bus_gen = [int(gen.bus.code) for gen in GridCal_grid.get_generators()]   
    idx_gen = [i for i, bus in enumerate(bus) if bus in bus_gen]   
    Vm = np.abs([pf_results.results.voltage[idx] for idx in idx_gen])
    theta = np.angle([pf_results.results.voltage[idx] for idx in idx_gen], deg=True) 
    P = [(np.real(pf_results.results.Sbus[idx]) + (pf_results.grid.buses[idx].loads[0].P if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    Q = [(np.imag(pf_results.results.Sbus[idx]) + (pf_results.grid.buses[idx].loads[0].Q if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    
    Qmin = [GridCal_grid.get_generators()[idx].Qmin/Sbase for idx in range(0,len(GridCal_grid.get_generators()))]
    Qmax = [GridCal_grid.get_generators()[idx].Qmax/Sbase for idx in range(0,len(GridCal_grid.get_generators()))]

    pf_gen = pd.DataFrame({'bus':bus_gen, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q,'Qmin':Qmin,'Qmax':Qmax})
    
    return pf_bus, pf_load, pf_gen

def process_GridCal_PF_loadPQ_StaticGen(GridCal_grid, pf_results, Generators,n_pf=1):
    
    Sbase = GridCal_grid.Sbase
    
    # pf_bus: voltage and angle in buses
    
    bus = [int(bus) for bus in [bus.code for bus in GridCal_grid.buses]]
    Vm = np.abs(pf_results.voltage)
    theta = np.angle(pf_results.voltage, deg=True) 
    pf_bus = pd.DataFrame({'bus':bus, 'Vm': Vm, 'theta':theta, 'type':pf_results.bus_types})
    pf_bus['PF']=n_pf
        
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
    pf_load['PF']=n_pf

    #pf_gen: active and reactive power in generator buses
    
    bus_gen = [int(gen.bus.code) for gen in GridCal_grid.get_generators() + GridCal_grid.get_static_generators()]   
    idx_gen = [i for i, bus in enumerate(bus) if bus in bus_gen[1:]]   
    idx_gen=[62]+idx_gen
    Vm = np.abs([pf_results.voltage[idx] for idx in idx_gen])
    theta = np.angle([pf_results.voltage[idx] for idx in idx_gen], deg=True) 
    P = [(np.real(pf_results.Sbus[idx]) + (GridCal_grid.buses[idx].loads[0].P if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    Q = [(np.imag(pf_results.Sbus[idx]) + (GridCal_grid.buses[idx].loads[0].Q if bus[idx] in bus_load else 0))/Sbase for idx in idx_gen]
    
    Qmin= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Qmin']/Sbase for bus_gen_i in bus_gen]
    Qmax= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Qmax']/Sbase for bus_gen_i in bus_gen]
    Pmin= [0 for bus_gen_i in bus_gen]
    Pmax= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Pmax_TOT']/Sbase for bus_gen_i in bus_gen]

    Pg_i= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Pg_i']/Sbase for bus_gen_i in bus_gen]
    Qg_i= [Generators.loc[Generators.query('BusNum == @bus_gen_i').index[0],'Qg_i']/Sbase for bus_gen_i in bus_gen]
    
    pf_gen = pd.DataFrame({'bus':bus_gen, 'Vm':Vm, 'theta':theta, 'P':P, 'Q':Q,'Qmin':Qmin,'Qmax':Qmax,'Pmin':Pmin,'Pmax':Pmax,'Pg_i':Pg_i,'Qg_i':Qg_i})
    pf_gen['PF']=n_pf
    pf_gen['cos_phi']=np.cos(np.arctan(pf_gen['Q']/pf_gen['P']))

    return pf_bus, pf_load, pf_gen

#%%
def write_csv_psse_res(otput_name,bus_res_file,path):

    writer = pd.ExcelWriter(otput_name, engine='xlsxwriter')
    
    bus_res=pd.read_csv(path+bus_res_file)
    
    Vabs=bus_res[['I','VM']]
    Vang=bus_res[['I','VA']]
    
    Vabs.to_excel(writer, sheet_name='Vabs')
    Vang.to_excel(writer, sheet_name='Vang')
    
    # branches[['Pbranch']].to_excel(writer, sheet_name='Pbranch')
    # branches[['Qbranch']].to_excel(writer, sheet_name='Qbranch')
    
    writer.close()
    
#%%

def assign_gen(main_circuit,Generators,case):
    for gen in main_circuit.get_generators():
        bus_name=gen.bus._name
        #Snom=Generators.loc[Generators.query('BusName == @bus_name').index[0],'TOT']
        gen.Snom=Generators.loc[Generators.query('BusName == @bus_name').index[0],'Snom']
        gen.P=Generators.loc[Generators.query('BusName == @bus_name').index[0],'Pg_i']
        # gen.Pmax=Generators.loc[Generators.query('BusName == @bus_name').index[0],'TOT']
        # gen.Pmin=0
        gen.Qmax=Generators.loc[Generators.query('BusName == @bus_name').index[0],'Qmax']
        #0.9*Generators.loc[Generators.query('BusName == @bus_name').index[0],'TOT']
        gen.Qmin=Generators.loc[Generators.query('BusName == @bus_name').index[0],'Qmin']
        #gen.is_controlled=True
        gen.Pmax=Generators.loc[Generators.query('BusName == @bus_name').index[0],'Snom']*0.8
        gen.Pmin=0#-Generators.loc[Generators.query('BusName == @bus_name').index[0],'S_CIG']*0.8
        if case=='pf':
            gen.Vset=Generators.loc[Generators.query('BusName == @bus_name').index[0],'V']
        elif case=='opf':
            gen.Vset=1

def assign_StaticGen(main_circuit,Generators):
    for bus in main_circuit.get_buses():
        if bus.is_slack:
            bus_code=int(bus.code)
            gen=bus.generators[0]
            
            gen.Snom=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pmax']/0.8
            gen.P=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pg_i']
            gen.Qmax=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qmax']
            gen.Qmin=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qmin']
            gen.Pmax=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pmax']
            gen.Pmin=0
            gen.Vset=1
            
        elif len(bus.generators)!=0:
            
            bus_code=int(bus.code)
            gen_name=bus.generators[0].name
                        
            main_circuit.add_static_generator(bus, gce.StaticGenerator(gen_name, P=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pg_i'], Q=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qg_i']))#,power_factor=1)
            
            bus.generators=[]

def assign_load(main_circuit,T_Loads):
    for load in main_circuit.get_loads():
        bus_name=int(load.bus.code)
        load.P=T_Loads.loc[T_Loads.query('Num == @bus_name').index[0],'Pd_i']
        load.Q=T_Loads.loc[T_Loads.query('Num == @bus_name').index[0],'Qd_i']
    
    
        load.B=0
        load.Ir=0
        
def assign_Normal_or_StaticGen(main_circuit,Generators):
    for bus in main_circuit.get_buses():
        bus_code=int(bus.code)
        
        if bus_code in list(Generators['BusNum']):
            if bus.is_slack:
                gen=bus.generators[0]
                
                gen.Snom=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pmax']/0.8
                gen.P=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pg_i']
                gen.Qmax=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qmin']
                gen.Pmax=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=0
                gen.Vset=1
                
                
            elif Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Static']==1:
                gen_name=bus.generators[0].name
                            
                main_circuit.add_static_generator(bus, gce.StaticGenerator(gen_name, P=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pg_i'], Q=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qg_i']))#,power_factor=1)
                
                bus.generators=[]
                
            elif Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Static']==0:
                gen=bus.generators[0]
                
                gen.Snom=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pmax']/0.8
                gen.P=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pg_i']
                gen.Qmax=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Qmin']
                gen.Pmax=Generators.loc[Generators.query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=0
                gen.Vset=1