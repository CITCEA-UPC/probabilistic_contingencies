from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
#from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType

from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

import numpy as np
import pandas as pd
from os import path


def create_model(path_raw, name_raw=None):
    
    # GET GRID TOPOLOGY
    if name_raw is not None:
        raw_file = path.join(path_raw, name_raw)
    else:
        raw_file = path_raw
    grid = FileOpen(raw_file).open()
    return grid
    
def run_powerflow(grid,solver_type=SolverType.NR, Qconrol_mode=False):
            
    # RUN POWERFLOW
    #for solver_type in [SolverType.IWAMOTO, SolverType.NR, SolverType.LM, SolverType.FASTDECOUPLED]:
    
    print(solver_type)

    options = PowerFlowOptions(solver_type,
                               verbose=False,
                               initialize_with_existing_solution=False,
                               retry_with_other_methods=False,
                               ignore_single_node_islands = True,
                               control_q=Qconrol_mode,
                               tolerance = 1e-10)
                               #max_iter=2)
    
    pf = PowerFlowDriver(grid, options)
    pf.run()
    
    #print('Converged:', pf.convergence_reports[0].converged_[0])
    
    # grid.get_buses()
    return pf

