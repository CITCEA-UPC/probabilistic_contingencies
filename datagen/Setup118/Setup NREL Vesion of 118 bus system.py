#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")


# # Setup of the NREL version of the 118bus system
# 
# Setup of the system:
# - Define synchronous generation and converter-interfaced generation installed capacity
# - Define peak and minimum load demand
# - Define lines and transformers ratings
# - Define system topology
# 
# The topology of the system is the one of the 118bus system studied in the REE project:
# - Actual number of buses = 113
# - Number of generation units = 28
# - Each generation unit has a synchronous generator, a grid-following converter, and a grid-forming converter
# 
# ![IEEE-118-bus-test-system.png](attachment:IEEE-118-bus-test-system.png) 
# ![unidad de generacion.png](attachment:bcd397e6-0897-4079-a873-6f6ae82abc59.png)
# 
# Generation capacity, demand range, and elements ratings are obtained by adapting the data provided by NREL in [1]. Such data cannot be directly applied to our 118 bus system (but need to be rearranged), as the NREL 118bus system presents different characteristics:
# - Actual number of buses = 118
# - Number of generation units = 54
# - Not all the generation unit have converter-interfaced generation
# - Very large generation capacity, leading problems to power flow convergence
# 
# The following part of the notebook at first shows the setup of the NREL 118bus system. Then, it explains how data of the NREL 118bus system have been adapted to our REE system.
# 
# ## References
# [1] Pena, Ivonne, Carlo Brancucci Martinez-Anido, and Bri-Mathias Hodge. "An extended IEEE 118-bus test system with high renewable penetration." IEEE Transactions on Power Systems 33.1 (2017): 281-289.
# 

# ## NREL-118bus System 
# ### Buses
# 

# In[2]:


Buses=pd.read_csv('Buses.csv')
Buses


# In[3]:


for i in range(len(Buses)):
    Buses.loc[i,'Num']=int(Buses.loc[i,'Bus Name'][3:])

Buses=Buses.sort_values(by='Bus Name').reset_index(drop=True)

#pd.DataFrame.to_excel(Buses,'G:/Il mio Drive/Francesca 118 v2/Operation/tool_ree/tool_ree/Buses.xlsx')

Buses


# ### Loads
# Hourly load consumption for one year, aggregated for system's region

# In[4]:


Loads=pd.DataFrame()

for zone in [1,2,3]:

    Loads_R=pd.read_csv('./input-files/Input files/RT/Load/LoadR'+str(zone)+'RT.csv')
    
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


# In[5]:


Buses=Buses.rename(columns={"Load Participation Factor": "Load_Participation_Factor"}) 
loads_nrel=Buses.query('Load_Participation_Factor !=0')

loads_nrel


# ### Generators

# In[6]:


Generators=pd.read_excel('Generators_red.xlsx') #Reduced beacuse useless columns have been discarded

for i in range(len(Generators)):
    Generators.loc[i,'Num']=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Type']=Generators.loc[i,'Generator Name'][:-3]
    bus_num=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Generator Name'][:-3]
    Generators.loc[i,'Region']=list(Buses.query('Num == @bus_num')['Region'])[0]

Generators

#%% Hydro data from plexos xsl
plexos_data=pd.read_excel('plexos-export.xls',sheet_name='Properties')
hydro_plants=[hydro for hydro in plexos_data['child_object'].unique() if hydro.startswith('Hydro')]
Generators=Generators.rename(columns={'Generator Name':'GeneratorName'})

for hydro_plant in hydro_plants:
    max_capacity= plexos_data.query('child_object == @hydro_plant and property == "Max Capacity"')['value'].max()
    Generators.loc[Generators.query('GeneratorName == @hydro_plant').index[0],'Max Capacity (MW)']=max_capacity
    
# In[7]:


types_of_gens=Generators['Type'].unique()
print(types_of_gens)


# In[8]:

nodes_of_connections=Generators['Node of connection'].unique()
Generators=Generators.rename(columns={'Node of connection':'Node_of_connection'})

Generators_NREL=pd.DataFrame()

for i in range(0,len(nodes_of_connections)):
    node=nodes_of_connections[i]
    bus=int(node[4:])
    Generators_NREL.loc[i,'BusNum']=bus
    Generators_NREL.loc[i,'Region']=list(Buses.query('Num == @bus')['Region'])[0]
    for t in types_of_gens:
        Generators_NREL.loc[i,t+' (MW)']=sum(Generators.query('Node_of_connection==@node and Type == @t')['Max Capacity (MW)'])

NRES_SG=['CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
RES_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)']
TOT_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)', 'CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
CIG=['Wind (MW)','Solar (MW)']

Generators_NREL['NRES_SG']=Generators_NREL[NRES_SG].sum(axis=1)
Generators_NREL['RES_SG']=Generators_NREL[RES_SG].sum(axis=1)
Generators_NREL['Pmax_TOT_SG']=Generators_NREL[TOT_SG].sum(axis=1)
Generators_NREL['Pmax_CIG']=Generators_NREL[CIG].sum(axis=1)
Generators_NREL['Pmax_TOT']=Generators_NREL['Pmax_CIG']+Generators_NREL['Pmax_TOT_SG']
Generators_NREL

# In[11]:

def regions_description(reg_list,Generators, Loads, Buses, regions=pd.DataFrame(),regions_gen_perc=pd.DataFrame(), regions_red=pd.DataFrame()):
    for r in range(len(reg_list)):
        R=reg_list[r]
        regions.loc[r,'Region']=R
        regions_gen_perc.loc[r,'Region']=R
        gen_reg=Generators.query('Region == @R')
        regions.loc[r,'N_gens']=len(gen_reg)
        regions.loc[r,'N_Wind']=len(gen_reg.query('Type == "Wind"'))
        regions.loc[r,'N_Solar']=len(gen_reg.query('Type == "Solar"'))
        
        
        buses_reg=[int(bus.replace('node','')) for bus in gen_reg['Node_of_connection'].unique()]
        regions.loc[r,'Buses list']=str(buses_reg)
        regions.loc[r,'Num_Bus_gen']=len(buses_reg)
        
        
        regions.loc[r,'Capacity (MW)']=gen_reg['Max Capacity (MW)'].sum()
     
        regions.loc[r,'Peak Load (MW)']=Loads[R].max()
        regions.loc[r,'Min Load (MW)']=Loads[R].min()
    
         
        for t in types_of_gens:#TOT_SG+CIG:
            regions_gen_perc.loc[r,t+' [%]']=sum(gen_reg.query('Type == @t')['Max Capacity (MW)'])/regions.loc[r,'Capacity (MW)']*100
            regions.loc[r,t+' [MW]']=sum(gen_reg.query('Type == @t')['Max Capacity (MW)'])
            
        regions_gen_perc.loc[r,'NRES_SG [%]']= sum(regions_gen_perc.loc[r,NRES_SG_perc])
        regions_gen_perc.loc[r,'RES_SG [%]']= sum(regions_gen_perc.loc[r,RES_SG_perc])
        regions.loc[r,'TOT_SG [%]']= sum(regions_gen_perc.loc[r,TOT_SG_perc])
        regions_gen_perc.loc[r,'CIG [%]']= sum(regions_gen_perc.loc[r,CIG_perc])
    
        regions.loc[r,'NRES_SG [MW]']= sum(regions.loc[r,NRES_SG])
        regions.loc[r,'RES_SG [MW]']= sum(regions.loc[r,RES_SG])
        regions.loc[r,'TOT_SG [MW]']= sum(regions.loc[r,TOT_SG])
        regions.loc[r,'CIG [MW]']= sum(regions.loc[r,CIG])
        
        regions.loc[r,'NRES_SG [%]']= regions_gen_perc.loc[r,'NRES_SG [%]']
        regions.loc[r,'RES_SG [%]']= regions_gen_perc.loc[r,'RES_SG [%]']
        regions.loc[r,'CIG [%]']= regions_gen_perc.loc[r,'CIG [%]'] 
        regions.loc[r,'TOT_SG [%]']= regions.loc[r,'TOT_SG [%]']

        regions_red=regions.drop(TOT_SG+CIG,axis=1)

    return regions, regions_gen_perc, regions_red

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
    
#%%

NRES_SG=['CC NG [MW]', 'CT NG [MW]', 'CT Oil [MW]', 'ICE NG [MW]', 'ST Coal [MW]', 'ST NG [MW]', 'ST Other [MW]']
RES_SG=['Geo [MW]', 'Hydro [MW]','Biomass [MW]']
TOT_SG=['Geo [MW]', 'Hydro [MW]','Biomass [MW]', 'CC NG [MW]', 'CT NG [MW]', 'CT Oil [MW]', 'ICE NG [MW]', 'ST Coal [MW]', 'ST NG [MW]', 'ST Other [MW]']
CIG=['Wind [MW]','Solar [MW]']

NRES_SG_perc=['CC NG [%]', 'CT NG [%]', 'CT Oil [%]', 'ICE NG [%]', 'ST Coal [%]', 'ST NG [%]', 'ST Other [%]']
RES_SG_perc=['Geo [%]', 'Hydro [%]','Biomass [%]']
TOT_SG_perc=['Geo [%]', 'Hydro [%]','Biomass [%]', 'CC NG [%]', 'CT NG [%]', 'CT Oil [%]', 'ICE NG [%]', 'ST Coal [%]', 'ST NG [%]', 'ST Other [%]']
CIG_perc=['Wind [%]','Solar [%]']


reg_list=['R1','R2','R3']
regions=pd.DataFrame()
regions_gen_perc=pd.DataFrame()

regions, regions_gen_perc, regions_red= regions_description(reg_list, Generators, Loads, Buses)


# ### Summary: regions description

# In[12]:


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


# In[13]:


title='Peak Load (MW)'
y = regions[title]
mylabels = regions['Region']

pie_plot(y,mylabels,title,labels_flag=1)


# In[14]:


title='Capacity (MW)'
y = regions[title]
mylabels = regions['Region']

pie_plot(y,mylabels,title,labels_flag=1)


# In[15]:


for r in range(1,len(reg_list)+1):
    title='Region '+str(r)
    y = regions_gen_perc.loc[r-1,types_of_gens][regions_gen_perc.loc[r-1,types_of_gens]!=0]
    mylabels = y.index
    
    pie_plot(y,mylabels,title,labels_flag=0)




# ## Create OperationData excel
# The columns Bus Name BusNum Pmax_TOT_SG Pmax_CIG Pmax_TOT are used in the OperationData_IEEE_118bus.xslx Generators sheet. Using these values, the following data are obtained:
# 
# - Snom = Pmax/0.95
# - Pmin = Snom*0.2
# - Qmax = 0.33*Pmax
# - Qmin = -0.33*Pmax

# In[26]:


columns_order=['BusNum','Snom_SG','Snom_CIG','Snom','Pmax','Pmin','Qmax','Qmin','Region','Pmax_SG','Pmax_CIG','Pmin_SG','Pmin_CIG']#'BusName',
path='../../stability_analysis/stability_analysis/data/cases/'
def create_OpDataExcel(Buses, Generators_sys, columns_order, path):

    T_Loads=Buses.query('Load_Participation_Factor !=00')
    T_Loads['Load_Participation_Factor']=T_Loads['Load_Participation_Factor']/3
    T_Buses=Buses[['Bus Name','Region']]

    T_Gen=Generators_sys[['BusNum','Pmax_CIG']]
    # T_Gen['BusName']=Generators_sys[['BusName']]
    T_Gen['Pmax_SG']=Generators_sys['Pmax_TOT_SG']
    T_Gen['Pmax']=np.array(T_Gen[['Pmax_SG']])+np.array(T_Gen[['Pmax_CIG']])
    T_Gen['Snom']=T_Gen['Pmax']/0.95
    T_Gen['Snom_SG']=T_Gen['Pmax_SG']/0.95
    T_Gen['Snom_CIG']=T_Gen['Pmax_CIG']/0.95
    T_Gen['Pmin']=T_Gen['Snom']*0.2
    T_Gen['Pmin_SG']=T_Gen['Snom_SG']*0.2
    T_Gen['Pmin_CIG']=T_Gen['Snom_CIG']*0.2
    T_Gen['Qmax']=T_Gen['Pmax']*0.33
    T_Gen['Qmin']=-T_Gen['Pmin']*0.33
    T_Gen['Region']=Generators_sys['Region']    
    T_Gen=T_Gen[columns_order]

    #ncig=len(T_Gen.query('Snom_CIG!=0'))
    
    filename='OperationData_IEEE_118_NREL.xlsx'

    with pd.ExcelWriter(path+filename, engine='openpyxl') as writer:
        T_Loads.to_excel(writer, sheet_name='Loads', index=False)
        T_Buses.to_excel(writer, sheet_name='Buses', index=False)
        T_Gen.to_excel(writer, sheet_name='Generators', index=False)
    return T_Gen


# In[28]:


T_Gen = create_OpDataExcel(Buses, Generators_NREL, columns_order, path)
T_Gen

#%%

# #### Wind, Solar, and Hydro Generation
# Hourly generation (of each generator) for one year

# In[9]:


from os import listdir
from os.path import isfile, join

def res_gen(res,df):
    path='./input-files/Input files/RT/'+res+'/'
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


# In[10]:


Wind

# ## Additional CIG
# Some generation units do not have CIG. Therefore, to these unit it is assigned the CIG installed capacity of some CIG of the NREL system, not present in REE system.






