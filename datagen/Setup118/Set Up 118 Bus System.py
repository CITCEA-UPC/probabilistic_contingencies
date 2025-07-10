#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import os
import pandas as pd
import numpy as np

from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

path='G:/Il mio Drive/Francesca 118 v2/additional-files-mti-118/additional-files-mti-118/'


# ## The System
# 
# ![image.png](attachment:image.png)
# 
# 113 buses with 28 Generators.
# 
# NREL-118: 118 bus with 54 Generators. [An Extended IEEE 118-Bus Test System With High Renewable Penetration]
# 
# Both systems are divided in 3 regions (called Areas in the figures)

# ### Data of the NREL-118 Bus 
# 
# #### Buses

# In[2]:


Buses=pd.read_csv(path+'Buses.csv')

for i in range(len(Buses)):
    Buses.loc[i,'Num']=int(Buses.loc[i,'Bus Name'][3:])

Buses=Buses.sort_values(by='Bus Name').reset_index(drop=True)
# Buses.loc[31,'Region']='R2'
# Buses.loc[111,'Region']='R2'

pd.DataFrame.to_excel(Buses,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/Buses.xlsx')

Buses


# #### Generators

# In[3]:


Generators=pd.read_excel(path+'Generators_red.xlsx')
#Generators=Generators.iloc[Generators.drop('Generator Name',axis=1).drop_duplicates(keep='first').index].reset_index(drop=True)

for i in range(len(Generators)):
    Generators.loc[i,'Num']=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Type']=Generators.loc[i,'Generator Name'][:-3]
    bus_num=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Generator Name'][:-3]
    Generators.loc[i,'Region']=list(Buses.query('Num == @bus_num')['Region'])[0]

Generators


# In[4]:


types_of_gens=Generators['Type'].unique()
print(types_of_gens)


# In[9]:


nodes_of_connections=Generators['Node of connection'].unique()
nodes_gen_cap=pd.DataFrame()
Generators=Generators.rename(columns={'Node of connection':'Node_of_connection'})

for n in range(0,len(nodes_of_connections)):
    node=nodes_of_connections[n]
    nodes_gen_cap.loc[n,'Node']=node
    nodes_gen_cap.loc[n,'Capacity']=sum(Generators.query('Node_of_connection == @node')['Max Capacity (MW)'])
    

Generators_NREL=pd.DataFrame()
for i in range(0,len(nodes_gen_cap)):
    Generators_NREL.loc[i,'BusNum']=int(nodes_gen_cap.loc[i,'Node'][4:])
    
Generators_NREL['Capacity']=nodes_gen_cap['Capacity']    


# #### Loads
# Hourly load consumption for one year, aggregated for system's region

# In[5]:


#get_ipython().run_line_magic('matplotlib', 'inline')

Loads=pd.DataFrame()

for zone in [1,2,3]:

    Loads_R=pd.read_csv('G:/Il mio Drive/Francesca 118 v2/input-files/Input files/RT/Load/LoadR'+str(zone)+'RT.csv')
    
    Loads_R["DATETIME"] = pd.to_datetime(Loads_R["DATETIME"])
    
    Loads_R=Loads_R.set_index(["DATETIME"]).sort_index()
    
    Loads['R'+str(zone)]=Loads_R
        
    fig=plt.figure()
    ax=fig.add_subplot()
    ax.plot(Loads_R.index,Loads_R['value'], linewidth=1)
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


# In[31]:


Buses=Buses.rename(columns={"Load Participation Factor": "Load_Participation_Factor"}) 
loads_nrel=Buses.query('Load_Participation_Factor !=0')

loads_nrel


# #### Wind, Solar, and Hydro Generation
# 
# Hourly generation (of each generator) for one year

# In[6]:


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


# In[7]:


Wind


# #### Summary: regions description

# In[8]:
    
NRES_SG=['CC NG', 'CT NG', 'CT Oil', 'ICE NG', 'ST Coal', 'ST NG', 'ST Other']
RES_SG=['Geo', 'Hydro','Biomass']
TOT_SG=['Geo', 'Hydro','Biomass', 'CC NG', 'CT NG', 'CT Oil', 'ICE NG', 'ST Coal', 'ST NG', 'ST Other']
CIG=['Wind','Solar']

reg_list=['R1','R2','R3']
regions=pd.DataFrame()
regions_gen_perc=pd.DataFrame()
for r in range(len(reg_list)):
    R=reg_list[r]
    regions.loc[r,'Region']=R
    regions_gen_perc.loc[r,'Region']=R
    buses_reg=list(np.array(Buses.query('Region == @R')['Num'],dtype=int))
    gen_reg=Generators.query('Num == @buses_reg')
    regions.loc[r,'N_gens']=len(gen_reg)    
    regions.loc[r,'Capacity (MW)']=sum(gen_reg['Max Capacity (MW)'])
    regions.loc[r,'Buses list']=str(buses_reg)
    regions.loc[r,'Num Bus']=len(buses_reg)
    regions.loc[r,'Peak Load (MW)']=Loads[R].max()
    regions.loc[r,'Min Load (MW)']=Loads[R].min()
    
    for t in types_of_gens:
        regions_gen_perc.loc[r,t]=sum(gen_reg.query('Type == @t')['Max Capacity (MW)'])/regions.loc[r,'Capacity (MW)']*100
    
    regions_gen_perc.loc[r,'NRES_SG']= sum(regions_gen_perc.loc[r,NRES_SG])
    regions_gen_perc.loc[r,'RES_SG']= sum(regions_gen_perc.loc[r,RES_SG])
    regions_gen_perc.loc[r,'CIG']= sum(regions_gen_perc.loc[r,CIG])
    
regions

#%%

def pie_plot(y,labels,title,labels_flag):
    fig=plt.figure()
        
    if labels_flag:
        p, tx, autotexts = plt.pie(y, labels=labels,textprops={'fontsize': 20},
                autopct="", shadow=True)
        for i, a in enumerate(autotexts):
            a.set_text("{0:.0f}".format(np.array(y)[i]))
    else:
        p, tx, autotexts = plt.pie(y, textprops={'fontsize': 20},
                autopct="", shadow=True)
        plt.legend(labels)
        
    plt.title(title,fontsize=20)
    
    fig.tight_layout

title='Peak Load (MW)'
y = regions[title]
mylabels = regions['Region']

pie_plot(y,mylabels,title,labels_flag=1)

title='Capacity (MW)'
y = regions[title]
mylabels = regions['Region']

pie_plot(y,mylabels,title,labels_flag=1)

for r in range(1,len(reg_list)+1):
    title='Region '+str(r)
    y = regions_gen_perc.loc[r-1,types_of_gens][regions_gen_perc.loc[r-1,types_of_gens]!=0]
    mylabels = y.index
    
    pie_plot(y,mylabels,title,labels_flag=0)
    

#%%
# ### Our 118-System
# 
# #### Generators

# In[39]:


#%%
fname='IEEE118busREE_Winter.raw'
path='G:/Il mio Drive/Francesca 118 v2/Onur/'

main_circuit = FileOpen(path+fname).open()

# Generation buses in ree system
generators=main_circuit.get_generators()

Generators_GC=pd.DataFrame()
for g in range(len(generators)):
    Generators_GC.loc[g,'Bus Name']=generators[g].bus._name
    Generators_GC.loc[g,'BusNum']=int(generators[g].bus.code)

# Generation buses that are in nrel but not in ree system
gen_bus_NREL_not_in_GC=list(set(Generators_NREL['BusNum'])-set(Generators_GC['BusNum']))

# Generation buses that are in ree but not in nrel system
gen_bus_GC_not_in_NREL=list(set(Generators_GC['BusNum'])-set(Generators_NREL['BusNum']))

# assign to each generators bus in ree the generators installed in the same bus of the nrel system    
for g in range(len(Generators_GC)):
    bus_gen=Generators_GC.loc[g,'BusNum']
    Generators_GC.loc[g,'Region']=list(Buses.query('Num == @bus_gen')['Region'])[0]
    aa=Generators.query('Num == @bus_gen')
    for t in types_of_gens:
        Generators_GC.loc[g,t+' (MW)']=sum(aa.query('Type == @t')['Max Capacity (MW)'])

# replace the genrators buses that are in ree but not in nrel with some of the nrel
Generators_GC.loc[Generators_GC.query('BusNum == 73').index,'Region']=list(Buses.query('Num == 74')['Region'])[0]  
aa=Generators.query('Num == 74')
for t in types_of_gens:
    Generators_GC.loc[Generators_GC.query('BusNum == 73').index,t+' (MW)']=sum(aa.query('Type == @t')['Max Capacity (MW)'])


Generators_GC

Generators.loc[Generators.query('Num == 74').index,'Num']=73


#%% REE regions
    
NRES_SG=['CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
RES_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)']
TOT_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)', 'CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
CIG=['Wind (MW)','Solar (MW)']

reg_list=['R1','R2','R3']
regions_GC=pd.DataFrame()
regions_GC_gen_perc=pd.DataFrame()
for r in range(len(reg_list)):
    R=reg_list[r]
    regions_GC.loc[r,'Region']=R
    regions_GC_gen_perc.loc[r,'Region']=R
    buses_reg=list(np.array(Generators_GC.query('Region == @R')['BusNum'],dtype=int))
    gen_reg=Generators_GC.query('Region == @R')
    regions_GC.loc[r,'N_gens']=(gen_reg[TOT_SG+CIG]!=0).sum().sum()
    regions_GC.loc[r,'Capacity (MW)']=gen_reg[TOT_SG].sum().sum()+gen_reg[CIG].sum().sum()
    regions_GC.loc[r,'Buses list']=str(buses_reg)
    regions_GC.loc[r,'Num Bus']=len(buses_reg)
     
    for t in TOT_SG+CIG:
        regions_GC_gen_perc.loc[r,t]=sum(gen_reg[t])/regions_GC.loc[r,'Capacity (MW)']*100
    
    regions_GC_gen_perc.loc[r,'NRES_SG']= sum(regions_GC_gen_perc.loc[r,NRES_SG])
    regions_GC_gen_perc.loc[r,'RES_SG']= sum(regions_GC_gen_perc.loc[r,RES_SG])
    regions_GC_gen_perc.loc[r,'CIG']= sum(regions_GC_gen_perc.loc[r,CIG])
    
regions_GC


#%%
NRES_SG=['CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
RES_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)']
TOT_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)', 'CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
CIG=['Wind (MW)','Solar (MW)']

Generators_GC['NRES_SG']=Generators_GC[NRES_SG].sum(axis=1)
Generators_GC['RES_SG']=Generators_GC[RES_SG].sum(axis=1)
Generators_GC['Pmax_TOT_SG']=Generators_GC[TOT_SG].sum(axis=1)
Generators_GC['Pmax_CIG']=Generators_GC[CIG].sum(axis=1)
Generators_GC['Pmax_TOT']=Generators_GC['Pmax_CIG']+Generators_GC['Pmax_TOT_SG']

#pd.DataFrame.to_excel(Generators_GC,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/Generators_GC_Red.xlsx')

# Generators_GC



# In[40]: generators buses in nrel and not in ree

missing_gen=pd.DataFrame()
m_gen_list=list(set(Generators['Num'].unique())-set(Generators_GC['BusNum'].unique()))
missing_gen['Bus Num']=m_gen_list
    
missing_gen['Region']=list(Buses.query('Num == @m_gen_list')['Region'])
missing_gen

#%% type of generator in the missing generation buses

for ii in range(0,len(missing_gen)):
    gen=missing_gen.loc[ii,'Bus Num']
    types=Generators.query('Num == @gen')['Type'].unique()
    for gen_type in types:
        missing_gen.loc[ii,gen_type]=Generators.query('Num == @gen and Type == @gen_type')['Max Capacity (MW)'].sum()

#capacity of the cig installed in the missing generation buses
missing_cig=missing_gen[['Region','Bus Num','Wind','Solar']]
#cig installed in the ree generation buses
gen_GC_cig=Generators_GC[['Region','BusNum','Wind (MW)','Solar (MW)']].sort_values(by='Region').reset_index(drop=True)
gen_GC_cig['CIG']=gen_GC_cig['Wind (MW)']+gen_GC_cig['Solar (MW)']

bus_num_GC=list(Generators_GC['BusNum'])
generators_nrel_cig_missing=Generators.query('Type == "Wind" or Type == "Solar" and Num != @bus_num_GC')

#%%

n_cig_missing_gc_reg=len(gen_GC_cig.query('CIG==0'))

n_cig_gen_x_bus=int(np.ceil(len(generators_nrel_cig_missing)/n_cig_missing_gc_reg))

jj=0
for ii in gen_GC_cig.query('CIG==0').index:#len(generators_nrel_cig_missing_reg),n_cig_gen_x_bus):
    
    try:
        gens_cap=generators_nrel_cig_missing.loc[generators_nrel_cig_missing.index[jj:jj+n_cig_gen_x_bus],['Generator Name','Max Capacity (MW)','Category']]
    except:
        gens_cap=generators_nrel_cig_missing.loc[generators_nrel_cig_missing.index[jj:],['Generator Name','Max Capacity (MW)','Category']]
        
    for cat in gens_cap['Category'].unique():
        gen_GC_cig.loc[ii,cat+' (MW)']=gens_cap.query('Category ==@cat')['Max Capacity (MW)'].sum()
    
    gen_GC_cig.loc[ii,'Added Gens']=str(list(gens_cap['Generator Name']))
    
    jj=jj+n_cig_gen_x_bus

gen_GC_cig['CIG']=gen_GC_cig['Wind (MW)']+gen_GC_cig['Solar (MW)']

#%%

# for r in range(0,len(reg_list)):
#     R=reg_list[r]
    
#     generators_nrel_cig_missing_reg=generators_nrel_cig_missing.query('Region == @R')
    
#     n_cig_missing_gc_reg=len(gen_GC_cig.query('Region == @R  and CIG==0'))
    
#     n_cig_gen_x_bus=int(np.floor(len(generators_nrel_cig_missing_reg)/n_cig_missing_gc_reg))
    
#     jj=0
#     for ii in gen_GC_cig.query('Region == @R  and CIG==0').index:#len(generators_nrel_cig_missing_reg),n_cig_gen_x_bus):
#         gens_cap=generators_nrel_cig_missing_reg.loc[generators_nrel_cig_missing_reg.index[jj:jj+n_cig_gen_x_bus],['Generator Name','Max Capacity (MW)','Category']]
        
#         for cat in gens_cap['Category'].unique():
#             gen_GC_cig.loc[ii,cat+' (MW)']=gens_cap.query('Category ==@cat')['Max Capacity (MW)'].sum()
        
#         gen_GC_cig.loc[ii,'Added Gens']=str(list(gens_cap['Generator Name']))
        
#         jj=jj+n_cig_gen_x_bus
        
#%% put the added cig capacity in the general Generators_GC df

for bus in gen_GC_cig['BusNum']:
    bus= int(bus)
    Generators_GC.loc[Generators_GC.query('BusNum == @bus').index,'Solar (MW)']=gen_GC_cig.loc[gen_GC_cig.query('BusNum == @bus').index[0],'Solar (MW)']
    Generators_GC.loc[Generators_GC.query('BusNum == @bus').index,'Wind (MW)']=gen_GC_cig.loc[gen_GC_cig.query('BusNum == @bus').index[0],'Wind (MW)']
    
Generators_GC['Pmax_CIG']=Generators_GC[CIG].sum(axis=1)
Generators_GC['Pmax_TOT']=Generators_GC['Pmax_CIG']+Generators_GC['Pmax_TOT_SG']

pd.DataFrame.to_excel(Generators_GC,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/Generators_GC_CIG.xlsx')

#%%
regions_gen_nrel=regions_gen_perc.copy(deep=True)
for r in range(len(reg_list)):
    cap=regions.loc[r,'Capacity (MW)']
    for col in regions_gen_nrel.columns[1:]:
        regions_gen_nrel.loc[r,col]=cap*regions_gen_nrel.loc[r,col]/100
        

regions_gen_nrel['Peak Load (MW)']=regions['Peak Load (MW)']

regions_gen_nrel['Min Load (MW)']=regions['Min Load (MW)']

pd.DataFrame.to_csv(regions_gen_nrel,'regions_gen_nrel.csv')

#%% Summary of NREL regions

regions['NRES_SG']=regions_gen_nrel['NRES_SG']
regions['RES_SG']=regions_gen_nrel['RES_SG']
regions['CIG']=regions_gen_nrel['CIG']

pd.DataFrame.to_csv(regions,'regions_nrel_summary.csv')

#%% Summary od REE regions

regions_GC=pd.DataFrame()
regions_GC_gen_perc=pd.DataFrame()
for r in range(len(reg_list)):
    R=reg_list[r]
    regions_GC.loc[r,'Region']=R
    regions_GC_gen_perc.loc[r,'Region']=R
    buses_reg=list(np.array(Generators_GC.query('Region == @R')['BusNum'],dtype=int))
    gen_reg=Generators_GC.query('Region == @R')
    regions_GC.loc[r,'N_gens']=(gen_reg[TOT_SG+CIG]!=0).sum().sum()
    regions_GC.loc[r,'Capacity (MW)']=gen_reg[TOT_SG].sum().sum()+gen_reg[CIG].sum().sum()
    regions_GC.loc[r,'Buses list']=str(buses_reg)
    regions_GC.loc[r,'Num Bus']=len(buses_reg)
     
    for t in TOT_SG+CIG:
        regions_GC_gen_perc.loc[r,t]=sum(gen_reg[t])/regions_GC.loc[r,'Capacity (MW)']*100
    
    regions_GC_gen_perc.loc[r,'NRES_SG']= sum(regions_GC_gen_perc.loc[r,NRES_SG])
    regions_GC_gen_perc.loc[r,'RES_SG']= sum(regions_GC_gen_perc.loc[r,RES_SG])
    regions_GC_gen_perc.loc[r,'CIG']= sum(regions_GC_gen_perc.loc[r,CIG])
    
regions_GC

#%% reduced capacity in percentage

cap_ree=regions_GC['Capacity (MW)']
cap_nrel=regions['Capacity (MW)']

peak_load_nrel=regions['Peak Load (MW)']
min_load_nrel=regions['Min Load (MW)']

peak_load_ree=peak_load_nrel*cap_ree/cap_nrel
min_load_ree=min_load_nrel*cap_ree/cap_nrel

regions_GC['Peak Load (MW)']=peak_load_ree
regions_GC['Min Load (MW)']=min_load_ree

pd.DataFrame.to_excel(regions_GC,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/regions_GC_summary_CIG.xlsx')

#%%
title='Peak Load (MW)'
y = regions_GC[title]
mylabels = regions_GC['Region']

pie_plot(y,mylabels,title,labels_flag=1)

title='Capacity (MW)'
y = regions_GC[title]
mylabels = regions_GC['Region']

pie_plot(y,mylabels,title,labels_flag=1)
types_of_gens=TOT_SG+CIG
for r in range(1,len(reg_list)+1):
    title='Region '+str(r)
    y = regions_GC_gen_perc.loc[r-1,types_of_gens][regions_GC_gen_perc.loc[r-1,types_of_gens]!=0]
    mylabels = y.index
    
    pie_plot(y,mylabels,title,labels_flag=0)

   
# In[41]:


# missing_capacity=pd.DataFrame()
# for r in range(len(reg_list)):
#     R=reg_list[r]
#     bus_miss_gen=list(missing_gen.query('Region == @R')['Bus Num'])
#     gen_miss_reg=Generators.query('Num == @bus_miss_gen')
#     missing_capacity.loc[r,'Region']=R
#     for t in types_of_gens:
#         missing_capacity.loc[r,t+' (MW)']=sum(gen_miss_reg.query('Type == @t')['Max Capacity (MW)'])

# missing_capacity['TOT']=missing_capacity.drop('Region',axis=1).sum(axis=1)

# for r in range(0,len(reg_list)):
#     R=reg_list[r]
#     tot_cap_reg=Generators.query('Region == @R')['Max Capacity (MW)'].sum()
#     missing_capacity.loc[r,'%miss_cap']=missing_capacity.loc[r,'TOT']/tot_cap_reg
     

# missing_capacity

# #%% Reduce load
# for r in range(len(reg_list)):
#     regions.loc[r,'Red_Peak_Load']= regions.loc[r, 'Peak Load (MW)']*(1-missing_capacity.loc[r,'%miss_cap'])
#     regions.loc[r,'Red_Min_Load']= regions.loc[r, 'Min Load (MW)']*(1-missing_capacity.loc[r,'%miss_cap'])
 


# #%%

# # # In[42]: Add missing capacity


# # for r in range(len(reg_list)):
# #     R=reg_list[r]
# #     gen_reg=Generators_GC.query('Region == @R')
# #     ind_gen_reg=gen_reg.index
# #     n_gen_reg=len(gen_reg)
    
# #     miss_cap_reg=missing_capacity.query('Region == @R')
# #     miss_cap_gen=miss_cap_reg.drop('Region',axis=1)/n_gen_reg
    
# #     for t in types_of_gens:
# #         Generators_GC.loc[ind_gen_reg,t+' (MW)']=Generators_GC.loc[ind_gen_reg,t+' (MW)']+float(miss_cap_gen[t+' (MW)'])



# # In[43]:


# for r in range(len(reg_list)):
#     R=reg_list[r]
#     regions.loc[r,'Capacity Our Sys']=Generators_GC.query('Region == @R')[['Pmax_TOT']].sum(axis=1).sum(axis=0)
#     regions.loc[r,'TOT_SG']=float(Generators_GC.query('Region == @R')[['Pmax_TOT_SG']].sum(axis=0))
#     regions.loc[r,'CIG']=float(Generators_GC.query('Region == @R')[['Pmax_CIG']].sum(axis=0))
    
#     gen_reg=Generators_GC.query('Num == @buses_reg')

# pd.DataFrame.to_excel(regions,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/regions_summary_Red.xlsx')
    
# regions


# # In[34]:

# loads=main_circuit.get_loads()

# Loads_GC=[]
# for load in loads:
#     Loads_GC.append(int(load.bus.code))

# Loads_GC=pd.DataFrame(Loads_GC)
# Loads_GC.columns=['BusNum']    

# loads_nrel_not_in_gc=list(set(loads_nrel['Num'])-set(Loads_GC['BusNum']))
# loads_gc_not_in_nrel=list(set(Loads_GC['BusNum'])-set(loads_nrel['Num']))

# loads_nrel.loc[loads_nrel.query('Num == 39').index,'Num']=37

# pd.DataFrame.to_excel(loads_nrel,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/Loads_Red.xlsx')


# ## Operation Study
# 
# Solve a small-signal stability-constrained OPF that computes the ganeration dispatch and the GFOR/GFOL power generation mix that provide an optimal (min power losses, min generation cost, etc...) and stable solution.
# 
# The small-signal constraint is formulated as a regression that is a function of the demand (loads power) and control variables (P, Q of generators, V and Theta of buses). To train this regression data have to be generated in system operating space.
# 
# 

# ![space-2.png](attachment:space-2.png)

# 
# - Fixed grid topology:
# 
#     - Fixed maximum capacity at the generation buses (= total maximum capacity at the generation unit G) 
#     - Fixed maximum capacity of the SG
#     - Fixed maximum capacity of the CIG = sum of GFOR and GFOL maximum capacity
# 
# ![unidad%20de%20generacion.png](attachment:unidad%20de%20generacion.png)
# 
# - Change the operating point:
# 
#     - Power injected by the SG
#     - Power injected by the GFOR converter -->
#     - Power injected by the GFOL converter -->
#     
#     --> change the installed power of GFOR and GFOL coherently  
#    

# #### Define the operating space to be explored
# 
# Dimensions:
# 
# - Dimensions D=[P_G1, P_G2,P_G3,%G_SG,%G_gfm, K_1,...,K_N] ; (P_G1=P_L1,P_G2=P_L2,P_G3=P_L3)
# 
# - Upper bounds: ub=[P_L1^max,P_L2^max,P_L3^max,100%,100%,K_1^max,...,K_N^max]
# 
# - Lower bounds: ub=[P_L1^min,P_L2^min,P_L3^min,0%,0%,K_1^min,...,K_N^min]
# 
# Variables:
# 
# - P_Gi=[P_gen1,...P_genN]; ub=[P_gen1^max,...,P_genN^max]; ub=[0,...,0]
# 
# 
# 
# 
# 

# In[ ]:





# In[ ]:





# In[ ]:




