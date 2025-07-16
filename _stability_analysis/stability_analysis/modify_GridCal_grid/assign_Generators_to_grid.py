import numpy as np
import pandas as pd
import numpy as np
import GridCalEngine.api as gce
import random

def assign_StaticGen(GridCal_grid, d_raw_data, d_op):
    
    for bus in GridCal_grid.get_buses():
        if bus.is_slack:
            bus_code=int(bus.code)
            bus.generators=[]
            bus.static_generators=[]
            
            gen=gce.Generator()
            gen.gen_name=bus.name
            gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
            gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
            gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']
            gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']
            gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
            gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
            gen.Vset=1
            
            GridCal_grid.add_generator(bus,gen)
            
        elif len(bus.generators)!=0:
            
            bus_code=int(bus.code)
            bus.generators=[]
            bus.static_generators=[]
                         
            GridCal_grid.add_static_generator(bus, gce.StaticGenerator(bus.name, P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG'], Q=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'QG']))
                        
    
def assign_PV_or_StaticGen(GridCal_grid,d_raw_data,d_op):
    for bus in GridCal_grid.get_buses():
        bus_code=int(bus.code)
        
        if bus_code in list(d_raw_data['generator']['I']):
            if bus.is_slack:
                gen=bus.generators[0]

                gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
                gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']
                gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
                gen.Vset=1
                
            else:
                bus.generators=[]
                bus.static_generators=[]
                if d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'Static']==1:
                    gen_name=str(bus.code)#generators[0].name
                                
                    GridCal_grid.add_static_generator(bus, gce.StaticGenerator(gen_name, P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG'], Q=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'QG']))#,power_factor=1)
                                        
                elif d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'Static']==0:
                    gen_name=str(bus.code)#generators[0].name
                    
                    gen = gce.Generator(gen_name)#voltage_module=1.0,p_min=-Sn_vsc,p_max=Sn_vsc,Snom=Sn_vsc)
                    
                    gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
                    gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                    gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']#0.4*gen.P#
                    gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']#-0.4*gen.P#
                    gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
                    gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
                    gen.Vset=1
                    
                    GridCal_grid.add_generator(bus, gen)
                    
def assign_PV_or_StaticGen_read_original_grid(GridCal_grid,d_raw_data,d_op):
    for bus in GridCal_grid.get_buses():
        bus_code=int(bus.code)
        
        if bus_code in list(d_raw_data['generator']['I']):
            if bus.is_slack:
                gen=bus.generators[0]
                
                gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
                gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']
                gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
                gen.Vset=1
                
                
                
            elif d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'Static']==1:
                gen_name=bus.generators[0].name
                            
                GridCal_grid.add_static_generator(bus, gce.StaticGenerator(gen_name, P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG'], Q=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'QG']))#,power_factor=1)
                
                bus.generators=[]
                
            elif d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'Static']==0:
                gen=bus.generators[0]
                
                gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
                gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']
                gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
                gen.Vset=1 
                
def assign_PVGen(**kwargs):
    GridCal_grid=kwargs.get("GridCal_grid",None)
    d_raw_data=kwargs.get("d_raw_data",None)
    d_op=kwargs.get("d_op",None)
    voltage_profile_list=kwargs.get("voltage_profile_list",None)
    indx_id=kwargs.get("indx_id",None)
    V_set=kwargs.get("V_set",None)
     
    for gen in GridCal_grid.get_generators():
        bus=gen.bus
        bus_code=int(bus.code)
        
        if bus_code in list(d_raw_data['generator']['I']):
            if bus.is_slack:

                gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
                gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']
                # gen.Qmax=0.33*d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                # gen.Qmin=-0.33*d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
                gen.Pf=0.95

                if voltage_profile_list!=None:
                    idx=int(indx_id[np.where(indx_id[:,1]==bus_code),0])
                    gen.Vset=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'V']=voltage_profile_list[idx]
                
                elif V_set!=None:
                    gen.Vset=V_set
                
            else:
                                          
                gen_name=bus.code#generators[0].name
                
                
                gen.Snom=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Snom']
                gen.P=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Qmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmax']
                gen.Qmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Qmin']
                # gen.Qmax=0.33*d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                # gen.Qmin=-0.33*d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'PG']
                gen.Pmax=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmax']
                gen.Pmin=d_op['Generators'].loc[d_op['Generators'].query('BusNum == @bus_code').index[0],'Pmin']
                gen.Pf=0.95
                
                if voltage_profile_list!=None:
                    idx=int(indx_id[np.where(indx_id[:,1]==bus_code),0])
                    gen.Vset=d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'V']=voltage_profile_list[idx]
                
                elif V_set!=None:
                    gen.Vset=V_set
                
                
# def assign_V_to_PVGen(GridCal_grid,d_raw_data):
#     vmin=0.95
#     vmax=1.05
#     list_of_code_bus_gen=[]
#     list_of_idx_bus_gen=[]
#     gen_buses=list(d_raw_data['generator']['I'])
#     AdjMat=GridCal_grid.get_adjacent_matrix()
#     i=0
#     gen=GridCal_grid.get_generators()[i]
#     bus=gen.bus
#     # if bus.is_slack:
#     #     i=i+1
#     #     gen=GridCal_grid.get_generators()[i]
#     #     bus=gen.bus

#     bus_code=int(bus.code)    
    
#     v_parent=[random.uniform(0.95,1.05)]
    
#     list_of_code_bus_gen.append(bus_code)
    
#     d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'V']=v_parent
    
#     bus_list=[bus]
#     while len(list_of_code_bus_gen)!=len(d_raw_data['generator']):
        
#         for bus in bus_list:
        
#             idx_bus = [i for i, b in enumerate(GridCal_grid.get_buses()) if b == bus][0]
#             list_of_idx_bus_gen.append(idx_bus)
#             idx_close_buses= list(set(GridCal_grid.get_adjacent_buses(AdjMat,idx_bus).astype(int))-set(list_of_idx_bus_gen))
#             close_buses_with_gen=[GridCal_grid.get_buses()[i] for i in idx_close_buses if len(GridCal_grid.get_buses()[i].generators)!=0]
            
#             if len(close_buses_with_gen)!=0:
                
                
            
#             code_close_buses_with_gen=[int(bus.code) for bus in close_buses_with_gen]
#             code_close_buses_with_gen=list(set(code_close_buses_with_gen)-set(list_of_code_bus_gen))
            
#             v_child=[random.uniform(-0.02, 0.02)+v_parent[i] for i in range(len(code_close_buses_with_gen))]
            
#             for i in range(len(v_child)):
#                 if v_child[i] <vmin:
#                     v_child[i]=vmin
#                 if  v_child[i]>vmax:
#                     v_child[i]=vmax
            
            
#             list_of_code_bus_gen.extend(code_close_buses_with_gen)
#             v_parent=v_child
#             for i in range(len(v_child)):
#                 bus_code=code_close_buses_with_gen[i]
#                 d_raw_data['generator'].loc[d_raw_data['generator'].query('I == @bus_code').index[0],'V']=v_parent[i]
            
#             bus_list=close_buses_with_gen
   
def PQ_area_NationalGrid(d_pf, d_raw_data):
    # bus_cosphi_violation=list(d_pf['pf_gen'].query('cosphi < 0.8')['bus'])
    # # conversion=d_pf['pf_gen'].query('cosphi < 0.8')['Q']/d_pf['pf_gen'].query('cosphi < 0.8')['P']
    # # diff=abs(np.tan(np.arccos(0.95))-conversion)
    
    # P_pu=d_raw_data['generator'].query('I == @bus_cosphi_violation')['PG']/d_raw_data['generator'].query('I == @bus_cosphi_violation')['MBASE']
    
    # Q_pu=d_pf['pf_gen'].query('bus == @bus_cosphi_violation')['Q']*100/d_raw_data['generator'].query('I == @bus_cosphi_violation')['MBASE']
   
    
    cosphi_violation=d_pf['pf_gen'].query('cosphi < 0.8')
    for i in cosphi_violation.index:
        cosphi_i=cosphi_violation.loc[i,'cosphi']
        Q_i=cosphi_violation.loc[i,'Q']*100
        P_i=Q_i/(np.tan(np.arccos(cosphi_i)-np.arccos(0.8)))
        bus_i=cosphi_violation.loc[i,'bus']
        
        P_pu=P_i/d_raw_data['generator'].query('I == @bus_i')['MBASE']

        