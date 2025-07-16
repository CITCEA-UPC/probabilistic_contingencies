from stability_analysis.preprocess import preprocess_data

def set_breaker_state(element, number, new_state, grid, grid_0):
    
    """
    Open/Close a breaker
    
    Args:
        element: (str) name of element: "line", "TH", ...
        number: (int) number of element in initial topology table
                
    """   
    
    if new_state == "open":
        new_state = 0
    elif new_state == "close":
        new_state = 1
    else:
        print("New state not recognized")
        
    state = "CLOSED" if new_state else "OPEN"
    

    if element == "line":
        name = 'T_NET'
        name_0 = 'T_NET_0'
        bus_from = grid_0[name_0].loc[grid_0[name_0].number == 1, 'bus_from'].values[0]
        bus_to = grid_0[name_0].loc[grid_0[name_0].number == 1, 'bus_to'].values[0]
        
        grid_0[name_0].loc[grid_0[name_0].number == number, 'state'] = new_state
        print("LINE number " + str(number) + ", from bus " + str(bus_from) + " to bus " + str(bus_to) + ", is now " + state)     
        grid[name] = grid_0[name_0][grid_0[name_0].state == 1]

    elif element == "trafo":
        name = 'T_trafo'
        name_0 = 'T_trafo_0'
        bus_from = grid_0[name_0].loc[grid_0[name_0].number == 1, 'bus_from'].values[0]
        bus_to = grid_0[name_0].loc[grid_0[name_0].number == 1, 'bus_to'].values[0]
        
        grid_0[name_0].loc[grid_0[name_0].number == number, 'state'] = new_state
        print("LINE number " + str(number) + ", from bus " + str(bus_from) + " to bus " + str(bus_to) + ", is now " + state)     
        grid[name] = grid_0[name_0][grid_0[name_0].state == 1]

    elif element == "DC_line":
        if new_state:
            grid_0['T_DC_NET_0'].loc[grid_0['T_DC_NET_0'].number == number, 'state'] = 1
        else:
            grid_0['T_DC_NET_0'].loc[grid_0['T_DC_NET_0'].number == number, 'state'] = 0
        grid['T_DC_NET'] = grid_0['T_DC_NET_0'][grid_0['T_DC_NET_0'].state == 1]

    elif element == "load":
        if new_state:
            grid_0['T_load_0'].loc[grid_0['T_load_0'].number == number, 'state'] = 1
        else:
            grid_0['T_load_0'].loc[grid_0['T_load_0'].number == number, 'state'] = 0
        grid['T_load'] = grid_0['T_load_0'][grid_0['T_load_0'].state == 1]

    elif element == "TH":
        if new_state:
            grid_0['T_TH_0'].loc[grid_0['T_TH_0'].number == number, 'state'] = 1
        else:
            grid_0['T_TH_0'].loc[grid_0['T_TH_0'].number == number, 'state'] = 0
        grid['T_TH'] = grid_0['T_TH_0'][grid_0['T_TH_0'].state == 1]

    elif element == "SG":
        if new_state:
            grid_0['T_SG_0'].loc[grid_0['T_SG_0'].number == number, 'state'] = 1
        else:
            grid_0['T_SG_0'].loc[grid_0['T_SG_0'].number == number, 'state'] = 0
        grid['T_SG'] = grid_0['T_SG_0'][grid_0['T_SG_0'].state == 1]

    elif element == "VSC":
        if new_state:
            grid_0['T_VSC_0'].loc[grid_0['T_VSC_0'].number == number, 'state'] = 1
        else:
            grid_0['T_VSC_0'].loc[grid_0['T_VSC_0'].number == number, 'state'] = 0
        grid['T_VSC'] = grid_0['T_VSC_0'][grid_0['T_VSC_0'].state == 1]

    elif element == "MMC":
        if new_state:
            grid_0['T_MMC_0'].loc[grid_0['T_MMC_0'].number == number, 'state'] = 1
        else:
            grid_0['T_MMC_0'].loc[grid_0['T_MMC_0'].number == number, 'state'] = 0
        grid['T_MMC'] = grid_0['T_MMC_0'][grid_0['T_MMC_0'].state == 1]

    elif element == "user":
        if new_state:
            grid_0['T_user_0'].loc[grid_0['T_user_0'].number == number, 'state'] = 1
        else:
            grid_0['T_user_0'].loc[grid_0['T_user_0'].number == number, 'state'] = 0
        grid['T_user'] = grid_0['T_user_0'][grid_0['T_user_0'].state == 1]

    else:
        print("Breaker name not found")
        
    grid['T_NET'] = preprocess_data.remove_parallel_lines(grid['T_NET'] )
    grid['T_trafo'] = preprocess_data.remove_parallel_lines(grid['T_trafo'])

    return grid