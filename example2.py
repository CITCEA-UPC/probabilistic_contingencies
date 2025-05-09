import GridCalEngine.api as gce
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
import numpy as np

grid = gce.open_file('IEEE_14.xlsx')
options = gce.PowerFlowOptions()
nc=gce.compile_numerical_circuit_at(grid, t_idx=None)
results=multi_island_pf_nc(nc, options=options)
nc.passive_branch_data.active[0]=False
results2=multi_island_pf_nc(nc, options=options)

print(results.get_branch_df())
print(results2.get_branch_df())


'''results = gce.power_flow(grid)

# Forma 1
grid.lines[0].active=False
grid.transformers2w[0].G = 0
results_post = gce.power_flow(grid)

print(results.get_branch_df())
print(results_post.get_branch_df())

rx = gce.contingencies_ts()
'''
