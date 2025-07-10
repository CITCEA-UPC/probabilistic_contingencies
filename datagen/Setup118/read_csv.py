import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import os
import pandas as pd
import numpy as np

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

from sklearn.metrics import r2_score  

#%%
Buses=pd.read_csv('Buses.csv')

for i in range(len(Buses)):
    Buses.loc[i,'Num']=int(Buses.loc[i,'Bus Name'][3:])

Buses=Buses.sort_values(by='Bus Name').reset_index(drop=True)
# Buses.loc[31,'Region']='R2'
# Buses.loc[111,'Region']='R2'


Generators=pd.read_excel('Generators_red.xlsx')
#Generators=Generators.iloc[Generators.drop('Generator Name',axis=1).drop_duplicates(keep='first').index].reset_index(drop=True)

for i in range(len(Generators)):
    Generators.loc[i,'Num']=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Type']=Generators.loc[i,'Generator Name'][:-3]
    bus_num=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Generator Name'][:-3]
    Generators.loc[i,'Region']=list(Buses.query('Num == @bus_num')['Region'])[0]


types_of_gens=Generators['Type'].unique()

reg_list=['R1','R2','R3']
regions=pd.DataFrame()
for r in range(len(reg_list)):
    R=reg_list[r]
    regions.loc[r,'Region']=R
    buses_reg=list(np.array(Buses.query('Region == @R')['Num'],dtype=int))
    gen_reg=Generators.query('Num == @buses_reg')
    regions.loc[r,'N_gens']=len(gen_reg)    
    regions.loc[r,'Capacity (MW)']=sum(gen_reg['Max Capacity (MW)'])
    regions.loc[r,'Buses list']=str(buses_reg)
    regions.loc[r,'Num Bus']=len(buses_reg)
    regions.loc[r,'Peak Load (MW)']=Loads[R].max()
    
    
# print(sum(Generators['Max Capacity (MW)'])) #paper says 24.6 GW   

# others=sum(gen_reg.query('Category !="Hydro"')['Max Capacity (MW)'])/1000
# aa=gen_reg.loc[gen_reg.query('Category =="Hydro"').drop('Generator Name',axis=1).drop_duplicates(keep='first').index,:]

# aa=list(gen_reg.query('Category =="Hydro"')['Max Capacity (MW)'])

# hydro=sum(aa['Max Capacity (MW)'])/1000


# others+hydro/2

#%%

Loads=pd.DataFrame()

for zone in [1,2,3]:

    Loads_R=pd.read_csv('G:/Il mio Drive/Francesca 118 v2/input-files/Input files/RT/Load/LoadR'+str(zone)+'RT.csv')
    
    Loads_R["DATETIME"] = pd.to_datetime(Loads_R["DATETIME"])
    
    Loads_R=Loads_R.set_index(["DATETIME"]).sort_index()
    
    Loads['R'+str(zone)]=Loads_R
        
    fig=plt.figure()
    ax=fig.add_subplot()
    ax.plot(Loads_R.index,Loads_R['value'], linewidth=1, label='Cleaned Meas.')
    plt.legend()
    ax.set_title('LOAD Region '+str(zone))  
    plt.xticks(rotation = 45) # Rotates X-Axis Ticks by 45-degrees
    ax.set_ylabel('Load [MW]')
    fig.tight_layout()
    
    fig=plt.figure()
    ax=fig.add_subplot()
    ax.boxplot(Loads)
    ax.set_ylabel('Load [MW]')
    plt.xticks([1, 2,3], list(Loads.columns))
    ax.grid()

    
#%%

from os import listdir
from os.path import isfile, join

def res_gen(res,df):
    path='G:/Il mio Drive/Francesca 118 v2/input-files/Input files/RT/'+res+'/'
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]

    onlyfiles=list(set(onlyfiles)-set(['.DS_Store']))
    
    for file in onlyfiles:
        df_i=pd.read_csv(path+file)
        
        df_i["DATETIME"] = pd.to_datetime(df_i["DATETIME"])
        
        df_i=df_i.set_index(["DATETIME"]).sort_index()
        
        df[file[:-6]]=df_i
        
    return df
        


    
Solar=pd.DataFrame()
Wind=pd.DataFrame()
Hydro=pd.DataFrame()
    
Solar=res_gen('Solar',Solar)
Wind=res_gen('Wind',Wind)
Hydro=res_gen('Hydro',Wind)

#%%

others_gen=pd.read_csv('G:/Il mio Drive/Francesca 118 v2/input-files/Input files/Others/GenOut.csv')
others_gen=others_gen.sort_values(by=['Year','Month','Day','Period','Name']) # 1= out of service


#%%
fname='IEEE118busREE_Winter.raw'
path='G:/Il mio Drive/Francesca 118 v2/Onur/'

main_circuit = FileOpen(path+fname).open()

generators=main_circuit.get_generators()

Generators_GC=pd.DataFrame()
for g in range(len(generators)):
    Generators_GC.loc[g,'Bus Name']=generators[g].bus._name
    Generators_GC.loc[g,'Bus Num']=int(generators[g].bus.code)
    
for g in range(len(Generators_GC)):
    bus_gen=Generators_GC.loc[g,'Bus Num']
    Generators_GC.loc[g,'Region']=list(Buses.query('Num == @bus_gen')['Region'])[0]
    aa=Generators.query('Num == @bus_gen')
    for t in types_of_gens:
        Generators_GC.loc[g,t+' (MW)']=sum(aa.query('Type == @t')['Max Capacity (MW)'])

missing_gen=pd.DataFrame()
m_gen_list=list(set(Generators['Num'].unique())-set(Generators_GC['Bus Num'].unique()))
missing_gen['Bus Num']=m_gen_list
    
missing_gen['Region']=list(Buses.query('Num == @m_gen_list')['Region'])

missing_capacity=pd.DataFrame()
for r in range(len(reg_list)):
    R=reg_list[r]
    bus_miss_gen=list(missing_gen.query('Region == @R')['Bus Num'])
    gen_miss_reg=Generators.query('Num == @bus_miss_gen')
    missing_capacity.loc[r,'Region']=R
    for t in types_of_gens:
        missing_capacity.loc[r,t+' (MW)']=sum(gen_miss_reg.query('Type == @t')['Max Capacity (MW)'])
        
for r in range(len(reg_list)):
    R=reg_list[r]
    gen_reg=Generators_GC.query('Region == @R')
    ind_gen_reg=gen_reg.index
    n_gen_reg=len(gen_reg)
    
    miss_cap_reg=missing_capacity.query('Region == @R')
    miss_cap_gen=miss_cap_reg.drop('Region',axis=1)/n_gen_reg
    
    for t in types_of_gens:
        Generators_GC.loc[ind_gen_reg,t+' (MW)']=Generators_GC.loc[ind_gen_reg,t+' (MW)']+float(miss_cap_gen[t+' (MW)'])

#%%
NRES_SG=['Biomass (MW)', 'CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
RES_SG=['Geo (MW)', 'Hydro (MW)']
TOT_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)', 'CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
CIG=['Wind (MW)','Solar (MW)']

Generators_GC['NRES_SG']=Generators_GC[NRES_SG].sum(axis=1)
Generators_GC['RES_SG']=Generators_GC[RES_SG].sum(axis=1)
Generators_GC['TOT_SG']=Generators_GC[TOT_SG].sum(axis=1)
Generators_GC['CIG']=Generators_GC[CIG].sum(axis=1)


for r in range(len(reg_list)):
    R=reg_list[r]
    regions.loc[r,'Capacity Our Sys']=Generators_GC.query('Region == @R')[['TOT_SG','CIG']].sum(axis=1).sum(axis=0)
    Generators_GC.query('Region == @R')[['TOT_SG']].sum(axis=0)
