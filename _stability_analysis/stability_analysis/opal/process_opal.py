'''
dades_json = {'SM1': ['1.04'], 
              'SM2': ['163000000', '1.025'], 
              'SM3': ['85000000', '1.025'], 
              'Ld5': ['125000000', '50000000'], 
              'Ld6': ['90000000', '30000000'], 
              'Ld8': ['100000000', '35000000'], 
              'Breaker1': [1.0, 1.0, 1.0], 
              'Breaker2': [1.0, 1.0, 1.0], 
              'Breaker3': [1.0, 1.0, 1.0]}

1)  Necessito que el nom sigui "ELEMENT" + "BUS" --> ah, ja ho és xdddd
    Vale és una miiiica lio aixo. Si tinc 3 elements de generació a un bus.. em donará
    el total o no? Perquè ara assumeixo que n'hi ha només un en el GridCal, i després ja reparteixo.
    A males sumo totes les que siguin del mateix bus (!)

2) Com podem modificar el codi perquè jo pugui llegir quan vulgui. 
   Almenys que no hagi d'estar corrent tot el rato

3) Noms breakers --> per ara, considero que només hi ha breakers a les línies

    LINIES: "Breaker" + "num_linia"

    Si els elements de generació han de tenir breakers, hauria de ser tipo:

    LINIES:    "Breaker" + "_line"    + "num_linia" --> Breaker_line2
    GENERACIÓ: "Breaker" + "_element" + "bus"       --> Breaker_SM1, Breaker_trafo2

'''

import re
from stability_analysis.preprocess import state_switches
from stability_analysis import opal

def update_OP_from_RT(d_grid, d_grid_0, GridCal_grid, data_old = 'None'):

    T_buses = d_grid['T_buses']    
    Sbase = GridCal_grid.Sbase    

    # Receive data from OPAL
    dades_json = opal.receive_lfdata() 
    
    for key,value in dades_json.items():
        match = re.match(r'([A-Za-z]+)(\d+)', key)
        element = match.group(1)
        bus = match.group(2)
        
        # Update OP of each element
        match element:
            case 'SM':
                # V
                GridCal_grid.buses[T_buses.index[T_buses['bus'] == bus].values[0]].controlled_generators[0].Vset = value[0]
                if not bus in d_grid['T_global']['ref_bus'].unique(): #not slack
                    # P
                    GridCal_grid.buses[T_buses.index[T_buses['bus'] == bus].values[0]].controlled_generators[0].P = value[0]/Sbase
                
            case 'Ld':
                # P
                GridCal_grid.buses[T_buses.index[T_buses['bus'] == bus].values[0]].loads.P = value[0]/Sbase
                # Q
                GridCal_grid.buses[T_buses.index[T_buses['bus'] == bus].values[0]].loads.Q = value[0]/Sbase
                
            case 'Breaker': # Update state of switches (open/close lines)
            
                """
                NOT FINISHED
                """
            
                if data_old == 'None': 
                    # first received data. set breaker states without comparing with previous state
                    if 0 in value:      
                                     
                        # Identify the line? bus from --> bus_to / Identify the element
                        # ...
                        
                        d_grid = state_switches.set_breaker_state("line", 3, "open", d_grid, d_grid_0)  # open line 3
                        GridCal_grid.lines[2].active = 0 # Update in GridCal
                
                else:                
                    # check if breaker state has changed between data_old and dades_json 
                    # ...
                    
                    # Identify the line? bus from --> bus_to / Identify the element
                    # ...
                    
                    d_grid = state_switches.set_breaker_state("line", 3, "close", d_grid, d_grid_0)  # close line 3
                    GridCal_grid.lines[2].active = 1  #Update in GridCal
                
            case _:
                print("Element " + element + " not recognized")
        
        
    data_old = dades_json    
    return d_grid, GridCal_grid, data_old