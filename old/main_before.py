import random
import GridCalEngine.api as gce
from collections import defaultdict

def run_power_flow_and_check(grid):
    """
    Runs a power flow on the given grid and returns:
      - converged (bool): whether the power flow converged
      - overloaded (bool): whether any branch loading > 1.0
      - loadings (list of float): per-branch loading values (pu)
    """
    result = gce.power_flow(grid)
    if not result.converged:
        return False, False, []
    loadings = result.loading
    overloaded = any(l > 1.0 for l in loadings)
    return True, overloaded, loadings

def collect_components(grid):
    """
    Returns a flat list of all elements that can fail:
      [('line', index, line_obj), ('transformer', index, tr_obj), ('generator', index, gen_obj), ...]
    """
    components = []
    for idx, line in enumerate(grid.lines):
        components.append(('line', idx, line))
    for idx, tx in enumerate(grid.transformers2w):
        components.append(('transformer', idx, tx))
    for idx, gen in enumerate(grid.generators):
        components.append(('generator', idx, gen))
    return components

def simulate_contingencies(grid_file, num_iterations, p_fail):
    """
    Performs Monte Carlo contingency analysis:
      - grid_file: path to the .gridcal network file
      - num_iterations: number of Monte Carlo runs
      - p_fail: probability that any given component fails in a run

    Returns a dictionary with two phases: 'single' and 'double'.
    Each phase has:
      - runs: how many times we attempted that contingency
      - failures: how many times the system collapsed
      - details: list of dicts with keys:
          type  -> 'line'|'transformer'|'generator'
          index -> component index
          reason-> 'no_converge'|'overload'
          pct   -> max overload percentage (only if reason=='overload')
      - tested_per_element: counts of how many times each element was taken down
      - nonconv_per_element: counts of how many times that led to non-convergence
    """
    stats = {
        'single': {
            'runs': 0, 'failures': 0, 'details': [],
            'tested_per_element': defaultdict(int),
            'nonconv_per_element': defaultdict(int)
        },
        'double': {
            'runs': 0, 'failures': 0, 'details': [],
            'tested_per_element': defaultdict(int),
            'nonconv_per_element': defaultdict(int)
        },
    }

    for _ in range(num_iterations):
        grid = gce.open_file(grid_file)
        all_comps = collect_components(grid)

        # --- First contingency (single failure) ---
        comp1 = random.choice(all_comps)
        key1 = (comp1[0], comp1[1])
        if random.random() < p_fail:
            stats['single']['runs'] += 1
            stats['single']['tested_per_element'][key1] += 1

            comp1[2].active = False
            conv1, ovld1, loads1 = run_power_flow_and_check(grid)

            if not conv1:
                stats['single']['failures'] += 1
                stats['single']['nonconv_per_element'][key1] += 1
                stats['single']['details'].append({
                    'type': comp1[0],
                    'index': comp1[1],
                    'reason': 'no_converge'
                })
                print(f"[CRITICAL Level 1] {comp1[0]} {comp1[1]} caused non-convergence")
                continue

            if ovld1:
                pct1 = max(loads1) * 100
                stats['single']['failures'] += 1
                stats['single']['details'].append({
                    'type': comp1[0],
                    'index': comp1[1],
                    'reason': 'overload',
                    'pct': pct1
                })
                continue
        else:
            continue

        # --- Second contingency (double failure) ---
        remaining = [c for c in all_comps if c != comp1]
        comp2 = random.choice(remaining)
        key2 = (comp2[0], comp2[1])
        if random.random() < p_fail:
            stats['double']['runs'] += 1
            stats['double']['tested_per_element'][key2] += 1

            comp2[2].active = False
            conv2, ovld2, loads2 = run_power_flow_and_check(grid)

            if not conv2:
                stats['double']['failures'] += 1
                stats['double']['nonconv_per_element'][key2] += 1
                stats['double']['details'].append({
                    'type': comp2[0],
                    'index': comp2[1],
                    'reason': 'no_converge'
                })
                print(f"[CRITICAL Level 2] {comp2[0]} {comp2[1]} caused non-convergence")
            elif ovld2:
                pct2 = max(loads2) * 100
                stats['double']['failures'] += 1
                stats['double']['details'].append({
                    'type': comp2[0],
                    'index': comp2[1],
                    'reason': 'overload',
                    'pct': pct2
                })

    return stats

if __name__ == "__main__":
    GRID_FILE = '../grids/IEEE118_opf.gridcal'
    N_SIMULATIONS = 10
    FAILURE_PROBABILITY = 1  # 100% chance of any component failing

    results = simulate_contingencies(GRID_FILE, N_SIMULATIONS, FAILURE_PROBABILITY)

    # Print overall summary
    for phase in ['single', 'double']:
        runs = results[phase]['runs']
        fails = results[phase]['failures']
        collapse_rate = (fails / runs * 100) if runs else 0.0
        print(f"{phase.capitalize()} contingency: {runs} attempts → {fails} collapses ({collapse_rate:.2f}%)")

    # Print detailed failure info
    print("\nSingle-contingency failures:")
    for detail in results['single']['details']:
        if detail['reason'] == 'no_converge':
            print(f" - {detail['type']} {detail['index']}: did not converge")
        else:
            print(f" - {detail['type']} {detail['index']}: overload {detail['pct']:.1f}%")

    print("\nDouble-contingency failures:")
    for detail in results['double']['details']:
        if detail['reason'] == 'no_converge':
            print(f" - {detail['type']} {detail['index']}: did not converge")
        else:
            print(f" - {detail['type']} {detail['index']}: overload {detail['pct']:.1f}%")

    # Print critical elements statistics
    print("\nCritical elements statistics (P[non-converge | component fails]):")
    for phase in ['single', 'double']:
        print(f"\n{phase.capitalize()} level:")
        tested = results[phase]['tested_per_element']
        nonconv = results[phase]['nonconv_per_element']
        for comp, t in tested.items():
            nc = nonconv.get(comp, 0)
            pct = (nc / t * 100) if t else 0.0
            # ahora mostramos all, incluso si pct == 0
            print(f" - {comp[0].capitalize()} {comp[1]}: {pct:.2f}% ({nc}/{t})")
