import numpy as np
import pandas as pd
import numpy as np
import GridCalEngine.api as gce

def assign_slack_bus(GridCal_grid, slack_bus):
    for bus in GridCal_grid.get_buses():
        if bus.code==str(slack_bus):
            bus.is_slack=True
        else: 
            bus.is_slack=False
    
        