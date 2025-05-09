import math
import random
import GridCalEngine.api as gce

'''
30/04/2025

CONCEPTES
- Montecarlo
- PowerFlow
- OptimalPowerFlow
- Sobrecàrrega de línia
- RMS

PREGUNTES A RESPONDRE
- Probabilitat de que si cau aquest element falli tot el sistema.
- Probabilitat que si falla aquest element i aquest altre caigui tot el sistema.

QUÈ VOLDRAN VEURE A LA PRESENTACIÓ?
- Plots, molts plots

PRACTICA
- Simulació de Montecarlo
    - Fallada d'un component
    - PowerFlow
        - Convergeix?
            - NO -> APUNTO QUE HA FALLAT I GUARDO ESTADÍSTICA
            - SÍ
                - OptimalPowerFlow
                    - Hi han illes? Sí -> APUNTO QUE HA FALLAT I GUARDO ESTADÍSTICA
                    - No hi han illes -> Hi ha molta diferència amb el PowerFlow normal? Si canvia més d'un X%, hi han sobrecàrregues abans i després? -> HO REMARCO I GUARDO ESTADÍSTICA
                    - Tot ok -> APUNTO QUE TOT NICE I GUARDO ESTADÍSTICA
                    - Fallada d'un segon component
                    - PowerFlow
                        - Convergeix?
                            - NO -> APUNTO QUE HA FALLAT I GUARDO ESTADÍSTICA
                            - SÍ
                                - OptimalPowerFlow
                                    - Hi han illes? Sí -> APUNTO QUE HA FALLAT I GUARDO ESTADÍSTICA
                                    - No hi han illes -> Hi ha molta diferència amb el PowerFlow normal? Si canvia més d'un X%, hi han sobrecàrregues abans i després? -> HO REMARCO I GUARDO ESTADÍSTICA
                                    - Tot ok -> APUNTO QUE TOT NICE I GUARDO ESTADÍSTICA
                    

'''

def simulate_failure(element, sim_time):
    """
    Calculates the failure probability for an element (using an exponential distribution)
    and randomly decides if it fails during a given time interval.

    La probabilidad de failure se calcula como:
    p = 1 - e^(-sim_time/mttf)

    Parameters:
      - element: object has an attribute 'mttf' (in hours)
      - sim_time: simulation time interval in hours

    Returns:
      - True if the element fails, False otherwise.
    """
    p = 1 - math.exp(-sim_time / element.mttf)
    return random.random() < p


def check_line_overloads(results, grid):
    """
    Checks all lines in the grid for overload.
    Uses the 'loading' values in the results and the branch data from grid.get_branches().

    Returns:
      - A list of line indices that are overloaded (i.e. loading > 1).
    """
    overloaded_lines = []
    for idx, (loading, branch) in enumerate(zip(results.loading, grid.get_branches())):
        if loading > 1:
            overloaded_lines.append(idx)
    return overloaded_lines


def simulate_individual_failures(grid, sim_time):
    """
    Simulates the individual failure of each element in the grid over a given time interval (in hours)
    and immediately runs a power flow to evaluate system convergence.
    After each power flow, it checks if any lines are overloaded.

    Returns:
      - results: a dictionary with the results for each category.
        Each entry is a list of tuples (element_index, converged), corresponding to each element that failed.
      - overload_results: a list of tuples (failure_category, element_index, overloaded_lines),
        indicating which lines were overloaded after the power flow.
    """
    results = {
        'lines': [],
        'transformers2w': [],
        'generators': []
    }
    overload_results = []  # To record overload info for each power flow simulation
    grid.generators[0].enabled_dispatch = False # Esto es para que no se pueda modificar el valor del opf
    grid.generators[0].device_type
    # Simulation for each line failure
    for idx, line in enumerate(grid.lines):
        if simulate_failure(line, sim_time):
            line.active = False
            res = gce.power_flow(grid)
            conv = res.converged
            results['lines'].append((idx, conv))
            overloaded = check_line_overloads(res, grid)
            overload_results.append(('line_failure', idx, overloaded))
            line.active = True  # Restore original state

    # Simulation for each two-winding transformer failure
    for idx, transformer in enumerate(grid.transformers2w):
        if simulate_failure(transformer, sim_time):
            transformer.active = False
            res = gce.power_flow(grid)
            conv = res.converged
            results['transformers2w'].append((idx, conv))
            overloaded = check_line_overloads(res, grid)
            overload_results.append(('transformer_failure', idx, overloaded))
            transformer.active = True

    # Simulation for each generator failure
    for idx, generator in enumerate(grid.generators):
        if simulate_failure(generator, sim_time):
            generator.active = False
            res = gce.power_flow(grid)
            conv = res.converged
            results['generators'].append((idx, conv))
            overloaded = check_line_overloads(res, grid)
            overload_results.append(('generator_failure', idx, overloaded))
            generator.active = True

    '''
    
    ## NO ET SERVIRÀ (potser) però val la pena tenir-ho com a referència per a consultar coses
    
    nc = gce.compile_numerical_circuit_at(grid)
    res = gce.power_flow(grid) # Son inputs y no se tocan
    #nc.generator_data.p # Esto es la generación de los generadores
    #nc.load_data.S.real # Eso es la potencia activa de las cargas
    res_opf = gce.nonlinear_opf(grid)
    if res_opf.converged:
        #res_opf.Pg ## Esto es la generación de los generadores
        #res_opf.loading # Esto es el por unidad de carga de las ramas El abs donde es > 1 está sobrecargado
        print(res_opf.Pg*nc.Sbase - nc.generator_data.p) #Sba
    else:
        print("no converge, colega")
    # si linea sobrecarga, opf, sino estoy ok
    # https://gridcal.readthedocs.io/en/latest/rst_source/theory/investments_evaluation.html
    # en el opf mirar si hay lot saving si hay generation shading
    # en res, tendre voltage, etc'''
    return results, overload_results


if __name__ == "__main__":
    # Load the grid (ensure that 'IEEE_14.xlsx' is in the correct path)
    #grid = gce.open_file('IEEE_14.xlsx')
    grid = gce.open_file('IEEE118_opf.gridcal')

    # Assign MTTF to each type of element (values in hours)
    for line in grid.lines:
        line.mttf = 5000
        # (Note: line.limit is not used here since overload checking uses loading values)
    for transformer in grid.transformers2w:
        transformer.mttf = 7000
    for generator in grid.generators:
        generator.mttf = 10000

    # Define the simulation time interval in hours (e.g., 5000 hours)
    sim_time = 5000

    # Number of Monte Carlo simulations
    N = 2

    # Overall accumulators for failure and convergence statistics
    total_failures = {
        'lines': 0,
        'transformers2w': 0,
        'generators': 0
    }
    total_convergence = {
        'lines': 0,
        'transformers2w': 0,
        'generators': 0
    }
    # Overload statistics: count how many times each line is overloaded (keyed by line index)
    overload_counts = {}

    # Per-element failure statistics (to identify critical elements)
    failure_counts = {
        'lines': {},
        'transformers2w': {},
        'generators': {}
    }
    non_conv_counts = {
        'lines': {},
        'transformers2w': {},
        'generators': {}
    }

    # Run Monte Carlo simulations
    for i in range(N):
        results, overload_results = simulate_individual_failures(grid, sim_time)
        # Update overall failure and convergence counts for each category
        for category in results:
            total_failures[category] += len(results[category])
            for (elem_idx, converged) in results[category]:
                if converged:
                    total_convergence[category] += 1
                failure_counts[category][elem_idx] = failure_counts[category].get(elem_idx, 0) + 1
                if not converged:
                    non_conv_counts[category][elem_idx] = non_conv_counts[category].get(elem_idx, 0) + 1
        # Update overload counts from each power flow simulation
        for failure_category, elem_idx, overloaded_lines in overload_results:
            for line_idx in overloaded_lines:
                overload_counts[line_idx] = overload_counts.get(line_idx, 0) + 1

    print(f"Results after {N} Monte Carlo simulations (interval of {sim_time} hour/s):\n")
    for category in total_failures:
        if total_failures[category] > 0:
            conv_rate = total_convergence[category] / total_failures[category] * 100
            print(
                f"Category {category}: {total_failures[category]} simulated failures - Overall convergence rate: {conv_rate:.2f}%")
        else:
            print(f"Category {category}: No failures were registered.")

    # Calculate the total number of power flow simulations performed (sum of all simulated failures)
    total_pf_simulations = sum(total_failures.values())
    print("\nOverload statistics for lines:")
    if total_pf_simulations > 0:
        for line_idx in range(len(grid.lines)):
            count = overload_counts.get(line_idx, 0)
            overload_rate = (count / total_pf_simulations) * 100
            print(
                f"Line {line_idx}: overloaded in {count} power flow simulations ({overload_rate:.2f}% of all simulations)")
    else:
        print("No power flow simulations were performed.")

    # Identify and report critical elements (those with high non-convergence ratio)
    critical_threshold = 80.0  # Define the threshold (in percent)
    print(f"\nCritical elements (non-convergence ratio >= {critical_threshold:.1f}%):")
    for category in failure_counts:
        critical_elements = []
        for elem_idx in sorted(failure_counts[category].keys()):
            count = failure_counts[category][elem_idx]
            non_conv = non_conv_counts[category].get(elem_idx, 0)
            ratio = (non_conv / count) * 100
            if ratio >= critical_threshold:
                critical_elements.append(f"Element {elem_idx} ({ratio:.2f}%)")
        if critical_elements:
            print(f"{category}: {', '.join(critical_elements)}")
        else:
            print(f"{category}: None")
