#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")


# # Setup of the modified version of the 118bus system
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

# In[5]:


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


# In[7]:


Buses=Buses.rename(columns={"Load Participation Factor": "Load_Participation_Factor"}) 
loads_nrel=Buses.query('Load_Participation_Factor !=0')

loads_nrel


# ### Generators

# In[8]:


Generators=pd.read_excel('Generators_red.xlsx') #Reduced beacuse useless columns have been discarded

for i in range(len(Generators)):
    Generators.loc[i,'Num']=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Type']=Generators.loc[i,'Generator Name'][:-3]
    bus_num=int(Generators.loc[i,'Node of connection'][4:])
    Generators.loc[i,'Generator Name'][:-3]
    Generators.loc[i,'Region']=list(Buses.query('Num == @bus_num')['Region'])[0]

Generators


# In[9]:


types_of_gens=Generators['Type'].unique()
print(types_of_gens)


# In[10]:


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
    
Generators_NREL['Capacity [MW]']=nodes_gen_cap['Capacity']    
Generators_NREL


# #### Wind, Solar, and Hydro Generation
# Hourly generation (of each generator) for one year

# In[11]:


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


# In[12]:


Wind


# ### Summary: regions description

# In[13]:


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
        regions.loc[r,t]=sum(gen_reg.query('Type == @t')['Max Capacity (MW)'])
        
    regions.loc[r,'NRES_SG [MW]']= sum(regions.loc[r,NRES_SG])
    regions.loc[r,'RES_SG [MW]']= sum(regions.loc[r,RES_SG])
    regions.loc[r,'CIG [MW]']= sum(regions.loc[r,CIG])

    regions=regions.drop(types_of_gens,axis=1)

    regions_gen_perc.loc[r,'NRES_SG [MW]']= sum(regions_gen_perc.loc[r,NRES_SG])
    regions_gen_perc.loc[r,'RES_SG [MW]']= sum(regions_gen_perc.loc[r,RES_SG])
    regions_gen_perc.loc[r,'CIG [MW]']= sum(regions_gen_perc.loc[r,CIG])

    regions.loc[r,'NRES_SG [%]']= sum(regions_gen_perc.loc[r,NRES_SG])
    regions.loc[r,'RES_SG [%]']= sum(regions_gen_perc.loc[r,RES_SG])
    regions.loc[r,'CIG [%]']= sum(regions_gen_perc.loc[r,CIG])
    regions.loc[r,'TOT_SG [%]']= sum(regions_gen_perc.loc[r,NRES_SG+RES_SG])
    
regions


# In[14]:


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


# In[15]:


title='Peak Load (MW)'
y = regions[title]
mylabels = regions['Region']

pie_plot(y,mylabels,title,labels_flag=1)


# In[16]:


title='Capacity (MW)'
y = regions[title]
mylabels = regions['Region']

pie_plot(y,mylabels,title,labels_flag=1)


# In[17]:


for r in range(1,len(reg_list)+1):
    title='Region '+str(r)
    y = regions_gen_perc.loc[r-1,types_of_gens][regions_gen_perc.loc[r-1,types_of_gens]!=0]
    mylabels = y.index
    
    pie_plot(y,mylabels,title,labels_flag=0)


# ## Our 118-System (REE system)
# ### Generators

# In[18]:


#%% REE regions
#reg_list=['R1','R2','R3']
#regions_GC=pd.DataFrame()
#regions_GC_gen_perc=pd.DataFrame()

def REE_regions(reg_list,regions_GC=pd.DataFrame(),regions_GC_gen_perc=pd.DataFrame()):
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
            regions_GC.loc[r,t]=sum(gen_reg[t])
            
        regions_GC_gen_perc.loc[r,'NRES_SG [%]']= sum(regions_GC_gen_perc.loc[r,NRES_SG])
        regions_GC_gen_perc.loc[r,'RES_SG [%]']= sum(regions_GC_gen_perc.loc[r,RES_SG])
        regions_GC_gen_perc.loc[r,'CIG [%]']= sum(regions_GC_gen_perc.loc[r,CIG])
    
        regions_GC.loc[r,'NRES_SG [MW]']= sum(regions_GC.loc[r,NRES_SG])
        regions_GC.loc[r,'RES_SG [MW]']= sum(regions_GC.loc[r,RES_SG])
        regions_GC.loc[r,'CIG [MW]']= sum(regions_GC.loc[r,CIG])
    
        regions_GC=regions_GC.drop(TOT_SG+CIG,axis=1)
    
        regions_GC.loc[r,'NRES_SG [%]']= sum(regions_GC_gen_perc.loc[r,NRES_SG])
        regions_GC.loc[r,'RES_SG [%]']= sum(regions_GC_gen_perc.loc[r,RES_SG])
        regions_GC.loc[r,'CIG [%]']= sum(regions_GC_gen_perc.loc[r,CIG])
        regions_GC.loc[r,'TOT_SG [%]']= sum(regions_GC_gen_perc.loc[r,NRES_SG+RES_SG])

    return regions_GC, regions_GC_gen_perc

#%% reduced capacity in percentage

def adjust_demand(regions_GC, regions_NREL):

    cap_ree=regions_GC['Capacity (MW)']
    cap_nrel=regions['Capacity (MW)']
    print('REE system capacity = {%f} NREL system capacity',cap_ree/cap_nrel)
    
    peak_load_nrel=regions['Peak Load (MW)']
    min_load_nrel=regions['Min Load (MW)']
    
    peak_load_ree=peak_load_nrel*cap_ree/cap_nrel
    min_load_ree=min_load_nrel*cap_ree/cap_nrel
    
    regions_GC['Peak Load (MW)']=peak_load_ree
    regions_GC['Min Load (MW)']=min_load_ree
    
    return regions_GC


# In[19]:


from GridCalEngine.IO.file_handler import FileOpen

fname='IEEE118busREE_Winter_Solved_mod_PQ_91Loads.raw'
path='../../stability_analysis/stability_analysis/data/raw/'

main_circuit = FileOpen(path+fname).open()

# Generation buses in ree system
generators=main_circuit.get_generators()

Generators_GC=pd.DataFrame()
for g in range(len(generators)):
    Generators_GC.loc[g,'Bus Name']=generators[g].bus._name
    Generators_GC.loc[g,'BusNum']=int(generators[g].bus.code)

# assign to each generator bus in REE system the generators installed in the same bus of the NREL system    

types_of_gens=Generators['Type'].unique()

for g in range(len(Generators_GC)):
    bus_gen=Generators_GC.loc[g,'BusNum']
    Generators_GC.loc[g,'Region']=list(Buses.query('Num == @bus_gen')['Region'])[0]
    aa=Generators.query('Num == @bus_gen')
    for t in types_of_gens:
        Generators_GC.loc[g,t+' (MW)']=sum(aa.query('Type == @t')['Max Capacity (MW)'])

Generators_GC


# In[20]:


# Generation buses that are in REE system but not in NREL system
gen_bus_GC_not_in_NREL=list(set(Generators_GC['BusNum'])-set(Generators_NREL['BusNum']))

gen_bus_GC_not_in_NREL


# In[21]:


# Generation buses that are in NREL system but not in REE system
gen_bus_NREL_not_in_GC=list(set(Generators_NREL['BusNum'])-set(Generators_GC['BusNum']))
gen_bus_NREL_not_in_GC


# In[22]:


# replace the generators buses that are in REE system but not in NREL system with some of the NREL:
#assign to gen at bus 73 of REE system the gen at bus 74 of NREL system
Generators_GC.loc[Generators_GC.query('BusNum == 73').index,'Region']=list(Buses.query('Num == 74')['Region'])[0]  
aa=Generators.query('Num == 74')
for t in types_of_gens:
    Generators_GC.loc[Generators_GC.query('BusNum == 73').index,t+' (MW)']=sum(aa.query('Type == @t')['Max Capacity (MW)'])

Generators_GC


# In[23]:


NRES_SG=['CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
RES_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)']
TOT_SG=['Geo (MW)', 'Hydro (MW)','Biomass (MW)', 'CC NG (MW)', 'CT NG (MW)', 'CT Oil (MW)', 'ICE NG (MW)', 'ST Coal (MW)', 'ST NG (MW)', 'ST Other (MW)']
CIG=['Wind (MW)','Solar (MW)']

Generators_GC['NRES_SG']=Generators_GC[NRES_SG].sum(axis=1)
Generators_GC['RES_SG']=Generators_GC[RES_SG].sum(axis=1)
Generators_GC['Pmax_TOT_SG']=Generators_GC[TOT_SG].sum(axis=1)
Generators_GC['Pmax_CIG']=Generators_GC[CIG].sum(axis=1)
Generators_GC['Pmax_TOT']=Generators_GC['Pmax_CIG']+Generators_GC['Pmax_TOT_SG']
Generators_GC


# In[24]:


reg_list=['R1','R2','R3']
regions_GC, regions_GC_gen_perc = REE_regions(reg_list)
regions_GC


# In[25]:


#%% reduced capacity in percentage

regions_GC = adjust_demand(regions_GC, regions)
regions_GC


# ## Create OperationData excel
# The columns Bus Name BusNum Pmax_TOT_SG Pmax_CIG Pmax_TOT are used in the OperationData_IEEE_118bus.xslx Generators sheet. Using these values, the following data are obtained:
# 
# - Snom = Pmax/0.95
# - Pmin = Snom*0.2
# - Qmax = 0.33*Pmax
# - Qmin = -0.33*Pmax

# In[26]:


columns_order=['BusName','BusNum','Snom_SG','Snom_CIG','Snom','Pmax','Pmin','Qmax','Qmin','Region','Pmax_SG','Pmax_CIG','Pmin_SG','Pmin_CIG']
path='C:\\Users/Francesca/miniconda3/envs/gridcal_original/stability_analysis/stability_analysis/data/cases/'
def create_OpDataExcel(Buses, columns_order, path):

    T_Loads=Buses.query('Load_Participation_Factor !=00')
    T_Loads['Load_Participation_Factor']=T_Loads['Load_Participation_Factor']/3
    T_Buses=Buses[['Bus Name','Region']]

    T_Gen=Generators_GC[['BusNum','Pmax_CIG']]
    T_Gen['BusName']=Generators_GC[['Bus Name']]
    T_Gen['Pmax_SG']=Generators_GC['Pmax_TOT_SG']
    T_Gen['Pmax']=np.array(T_Gen[['Pmax_SG']])+np.array(T_Gen[['Pmax_CIG']])
    T_Gen['Snom']=T_Gen['Pmax']/0.95
    T_Gen['Snom_SG']=T_Gen['Pmax_SG']/0.95
    T_Gen['Snom_CIG']=T_Gen['Pmax_CIG']/0.95
    T_Gen['Pmin']=T_Gen['Snom']*0.2
    T_Gen['Pmin_SG']=T_Gen['Snom_SG']*0.2
    T_Gen['Pmin_CIG']=T_Gen['Snom_CIG']*0.2
    T_Gen['Qmax']=T_Gen['Pmax']*0.33
    T_Gen['Qmin']=-T_Gen['Pmin']*0.33
    T_Gen['Region']=Generators_GC['Region']    
    T_Gen=T_Gen[columns_order]

    ncig=len(T_Gen.query('Snom_CIG!=0'))
    
    filename='OperationData_IEEE_118_NCIG'+str(ncig)+'.xlsx'

    with pd.ExcelWriter(path+filename, engine='openpyxl') as writer:
        T_Loads.to_excel(writer, sheet_name='Loads', index=False)
        T_Buses.to_excel(writer, sheet_name='Buses', index=False)
        T_Gen.to_excel(writer, sheet_name='Generators', index=False)
    return T_Gen


# In[28]:


# T_Gen = create_OpDataExcel(Buses, columns_order, path)
# T_Gen


# ## Additional CIG
# Some generation units do not have CIG. Therefore, to these unit it is assigned the CIG installed capacity of some CIG of the NREL system, not present in REE system.

# In[27]:


missing_gen=pd.DataFrame()
m_gen_list=list(set(Generators['Num'].unique())-set(Generators_GC['BusNum'].unique()))
missing_gen['Bus Num']=m_gen_list
    
missing_gen['Region']=list(Buses.query('Num == @m_gen_list')['Region'])
missing_gen


# In[28]:


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
generators_nrel_cig_missing


# In[29]:


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


# In[30]:


gen_GC_cig


# In[34]:


#%% put the added cig capacity in the general Generators_GC df
for ibus in gen_GC_cig.index[~gen_GC_cig['Added Gens'].isna()]:#gen_GC_cig['BusNum']:
    bus= int(gen_GC_cig.loc[ibus,'BusNum'])
    Generators_GC.loc[Generators_GC.query('BusNum == @bus').index,'Solar (MW)']=gen_GC_cig.loc[gen_GC_cig.query('BusNum == @bus').index[0],'Solar (MW)']
    Generators_GC.loc[Generators_GC.query('BusNum == @bus').index,'Wind (MW)']=gen_GC_cig.loc[gen_GC_cig.query('BusNum == @bus').index[0],'Wind (MW)']
    
    Generators_GC['Pmax_CIG']=Generators_GC[CIG].sum(axis=1)
    Generators_GC['Pmax_TOT']=Generators_GC['Pmax_CIG']+Generators_GC['Pmax_TOT_SG']
    Generators_GC


    # In[90]:
    
    
    headers=regions_GC_gen_perc.columns
    headers2=[i.replace('(MW)','[%]') for i in headers]
    regions_GC_gen_perc.columns=headers2
    regions_GC_gen_perc
    

# In[91]:
    
    
    #%% Summary of NREL regions
    regions
    
    
    # Proporcionate the load peak and minimum demand od NREL system to the capacity of the REE system.
    
    # In[92]:
    
    
    #%% reduced capacity in percentage
    regions_GC = adjust_demand(regions_GC, regions)


    # In[70]:
    
    
    # title='Peak Load (MW)'
    # y = regions_GC[title]
    # mylabels = regions_GC['Region']
    
    # pie_plot(y,mylabels,title,labels_flag=1)
    
    # title='Capacity (MW)'
    # y = regions_GC[title]
    # mylabels = regions_GC['Region']
    
    # pie_plot(y,mylabels,title,labels_flag=1)
    # types_of_gens=[i.replace('(MW)','[%]') for i in TOT_SG+CIG]
    # for r in range(1,len(reg_list)+1):
    #     title='Region '+str(r)
    #     y = regions_GC_gen_perc.loc[r-1,types_of_gens][regions_GC_gen_perc.loc[r-1,types_of_gens]!=0]
    #     mylabels = y.index
        
    #     pie_plot(y,mylabels,title,labels_flag=0)
    
    
    # In[71]:
    
    
    Generators_GC
    

    # ## Summary
    # ### NREL System
    
    # In[72]:
    
    
    regions
    
    
    # ## Our System
    
    # In[93]:
    
    
    regions_GC=regions_GC[regions.columns]
    regions_GC
    
    
    # In[ ]:
    
    columns_order=['BusName','BusNum','Snom_SG','Snom_CIG','Snom','Pmax','Pmin','Qmax','Qmin','Region','Pmax_SG','Pmax_CIG','Pmin_SG','Pmin_CIG']
    path='../../stability_analysis/stability_analysis/data/cases/'

    T_Gen = create_OpDataExcel(Buses, columns_order, path)
    # T_Gen

    

