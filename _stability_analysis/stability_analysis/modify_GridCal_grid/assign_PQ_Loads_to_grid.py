def assign_PQ_load(GridCal_grid,d_raw_data):
    for load in GridCal_grid.get_loads():
        bus_name=int(load.bus.code)
        load.P=d_raw_data['load'].loc[d_raw_data['load'].query('I == @bus_name').index[0],'PL']
        load.Q=d_raw_data['load'].loc[d_raw_data['load'].query('I == @bus_name').index[0],'QL']
    
    
        load.B=0
        load.Ir=0