import numpy as np

def compute_bus_admittance(num_buses, branches):
    # Initialize an empty bus admittance matrix
    Y_bus = np.zeros((num_buses, num_buses), dtype=complex)

    # Compute the admittance for each branch and update the Y_bus matrix
    for branch in branches:
        bus_from = int(branch.bus_from.code) - 1  # Assuming buses are 1-indexed
        bus_to = int(branch.bus_to.code) - 1    # Assuming buses are 1-indexed
        # print(bus_from)
        # print(bus_to)
        admittance = 1 / complex(branch.R, branch.X)  # Compute branch admittance

        # Add admittance to the diagonal elements
        Y_bus[bus_from][bus_from] += admittance
        Y_bus[bus_to][bus_to] += admittance

        # Subtract admittance from off-diagonal elements
        Y_bus[bus_from][bus_to] -= admittance
        Y_bus[bus_to][bus_from] -= admittance
        # print(Y_bus)

    return Y_bus

