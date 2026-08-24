import os
import sys
import numpy as np

#salloc -A bsc15 -q gp_debug -n 1 -c 20

ROOT = os.path.dirname(os.path.abspath(__file__))
VERAGRID_SRC = os.path.join(os.getcwd(), "VeraGrid", "src")
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

import VeraGridEngine.api as vge
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model

# PyCOMPSs imports
try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
    from pycompss.api.constraint import constraint
    print("PyCOMPSs imports OK")
except ImportError:
    from pycompss_dummies.api import compss_wait_on
    from pycompss_dummies.task import task
    from pycompss_dummies.constraint import constraint
    print("LOADING locals PyCOMPSs imports")

@task(returns=1)
def dummy(i):
    print("AFTER  ", i + 1, flush=True)
    return i + 1

def test_pycompss():
    print("## TESTING PYCOMPSS ##")
    futures = []
    for i in range(3):
        print("BEFORE ", i)
        futures.append(dummy(i))

    futures = compss_wait_on(futures)
    print(futures)

    print("########### PYCOMPSS OK ###########")

# Definitions
TEST = True

if TEST:
    GRID_NAME = "IEEE 9 Bus.gridcal"
    PATH = os.path.join(ROOT, "VeraGrid", "Grids_and_profiles", "grids", GRID_NAME)
else:
    GRID_NAME = "IEEE118busNREL.raw"
    #PATH = os.path.join(ROOT, "stability_analysis", "stability_analysis/data/raw",  GRID_NAME)
    PATH = os.path.join(ROOT, "temp_grids", GRID_NAME)
def run_small_signal_analysis2(grid) -> dict:
    pf_options = vge.PowerFlowOptions(solver_type=vge.SolverType.NR, verbose=False)
    power_flow = vge.PowerFlowDriver(grid=grid, options=pf_options)
    power_flow.run()
    pf_results = power_flow.results

    # RMS options are only used when ss_assessment_time > 0, because the driver
    # performs an RMS simulation from t=0 up to the assessment instant.
    rms_options = vge.RmsOptions(
        time_step=0.001,
        simulation_time=20.0,
        tolerance=1e-6,
        integration_method=vge.DynamicIntegrationMethod.DaeBackEuler,
        max_iter=1000,
        verbose=0,
    )
    # Case 1: assessment at t = 0 s (no RMS dynamic simulation is run).
    ss_options_t0 = vge.RmsSmallSignalStabilityOptions(
        ss_assessment_time=0.0,
        k=0,
        verbose=1,
    )
    small_signal_t0 = vge.SmallSignalStabilityRmsDriver(
    grid=grid,
    rms_options=rms_options,
    sss_options=ss_options_t0,
    pf_results=pf_results,
    )
    small_signal_t0.run_small_signal_stability()

    eigenvalues_t0 = small_signal_t0.results.eigenvalues
    participation_factors_t0 = small_signal_t0.results.participation_factors
    damping_ratios_t0 = small_signal_t0.results.damping_ratios
    conjugate_frequencies_t0 = small_signal_t0.results.conjugate_frequencies
    state_matrix_t0 = small_signal_t0.results.state_matrix

    # Case 2: assessment at t = 20 s.
    # The driver first runs the RMS simulation and then linearizes the system at t = 20 s.
    ss_options_t20 = vge.RmsSmallSignalStabilityOptions(
        ss_assessment_time=20.0,
        k=0,
        verbose=1,
    )

    small_signal_t20 = vge.SmallSignalStabilityRmsDriver(
        grid=grid,
        rms_options=rms_options,
        sss_options=ss_options_t20,
        pf_results=pf_results,
    )
    small_signal_t20.run_small_signal_stability()

    eigenvalues_t20 = small_signal_t20.results.eigenvalues
    participation_factors_t20 = small_signal_t20.results.participation_factors
    damping_ratios_t20 = small_signal_t20.results.damping_ratios
    conjugate_frequencies_t20 = small_signal_t20.results.conjugate_frequencies
    state_matrix_t20 = small_signal_t20.results.state_matrix

    return {
        "eigenvalues_t0": eigenvalues_t0,
        "participation_factors_t0": participation_factors_t0,
        "damping_ratios_t0": damping_ratios_t0,
        "conjugate_frequencies_t0": conjugate_frequencies_t0,
        "state_matrix_t0": state_matrix_t0,
        "eigenvalues_t20": eigenvalues_t20,
        "participation_factors_t20": participation_factors_t20,
        "damping_ratios_t20": damping_ratios_t20,
        "conjugate_frequencies_t20": conjugate_frequencies_t20,
        "state_matrix_t20": state_matrix_t20,

        }


def run_small_signal_analysis(grid) -> dict:
    """Run power flow and small-signal analysis with ``RmsProblemMultilinear``."""
    pf_results = vge.power_flow(grid, vge.PowerFlowOptions(tolerance=1e-5))
    if not pf_results.converged:
        raise RuntimeError("Power flow did not converge")

    rms_options = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20,
        problem_type=vge.RmsProblemTypes.Multilinear,
    )
    problem = vge.RmsProblemMultilinear(grid=grid, options=rms_options, pf_results=pf_results)

    ss_options = vge.RmsSmallSignalStabilityOptions(ss_assessment_time=0, verbose=0)
    ss_options.k = problem.get_states_number() + problem.get_diff_var_number()
    driver = vge.SmallSignalStabilityRmsDriver(
        grid=vge.MultiCircuit(Sbase=grid.Sbase),
        rms_options=rms_options,
        sss_options=ss_options,
        pf_results=pf_results,
    )
    driver.problem = problem
    driver.k = ss_options.k
    driver.run()

    eigenvalues = driver.results.eigenvalues
    finite = eigenvalues[np.isfinite(eigenvalues) & (np.abs(eigenvalues) < 1e6)]
    stable = bool(np.all(np.real(finite) <= 0.0)) if len(finite) else False
    margin = float(np.max(np.real(finite))) if len(finite) else float("nan")

    print(f"RmsProblemMultilinear states={problem.get_states_number()} diff_vars={problem.get_diff_var_number()}")
    print(f"Finite eigenvalues={len(finite)} stable={stable} margin={margin:.6e}")

    return {
        "problem": problem,
        "pf_results": pf_results,
        "eigenvalues": finite,
        "participation_factors": driver.results.participation_factors,
        "stable": stable,
        "margin": margin,
    }

def set_models(grid) -> None:
    """Attach phasor RMS models to buses, generators, branches, loads, and shunts."""
    def ensure_unique_device_names(devices, prefix: str) -> None:
        seen: dict[str, int] = {}
        for i, dev in enumerate(devices):
            base = str(dev.name).strip() if getattr(dev, "name", None) else f"{prefix}_{i}"
            if base not in seen:
                seen[base] = 0
                dev.name = base
            else:
                seen[base] += 1
                dev.name = f"{base}_{seen[base]}"

    ensure_unique_device_names(list(grid.generators), "gen")
    ensure_unique_device_names(list(grid.lines), "line")
    ensure_unique_device_names(list(grid.transformers2w), "trafo")
    ensure_unique_device_names(list(grid.loads), "load")
    ensure_unique_device_names(list(grid.shunts), "shunt")

    for bus in grid.buses:
        if bus.rms_model.empty():
            vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)

    for igen, gen in enumerate(grid.generators):
        if not gen.active or not gen.rms_model.empty():
            continue
        model = vge.get_complete_generator_template_phasor(grid.var_factory, name=f"Gen{igen}").block
        #model = vge.get_complete_generator_templatgete_phasor(grid.var_factory, name=f"Gen{igen}").block
        model = vge.to_implicit(model, grid.var_factory)
        set_rms_model(device=gen, model=model, var_factory=grid.var_factory)

    for line in grid.lines:
        if not line.active or not line.rms_model.empty():
            continue
        model = vge.get_line_phasor_rms_template(grid.var_factory, name=line.name).block
        model = vge.to_implicit(model, grid.var_factory)
        set_rms_model(device=line, model=model, var_factory=grid.var_factory)

    for load in grid.loads:
        if not load.active or not load.rms_model.empty():
            continue
        model = vge.get_load_phasor_current_rms_template(grid.var_factory, name=load.name).block
        set_rms_model(device=load, model=model, var_factory=grid.var_factory)

    for trafo in grid.transformers2w:
        if not trafo.active or not trafo.rms_model.empty():
            continue
        model = vge.initialize_trafo_rms(trafo, grid.var_factory, use_phasor_template=True).block
        model = vge.to_implicit(model, grid.var_factory)
        set_rms_model(device=trafo, model=model, var_factory=grid.var_factory)

    for shunt in grid.shunts:
        if not shunt.active or not shunt.rms_model.empty():
            continue
        model = vge.get_shunt_template(grid.var_factory, name=shunt.name, phasor=True).block
        model = vge.to_implicit(model, grid.var_factory)
        set_rms_model(device=shunt, model=model, var_factory=grid.var_factory)

    print("Attached RMS phasor models")


def detect_islands(grid):
    """
    Detecta si hay islas, es decir elementos aislados
    """

    nc = vge.compile_numerical_circuit_at(grid, t_idx=None)
    '''
    options = gce.PowerFlowOptions()
    results = multi_island_pf_nc(nc, options=options)
    #print(results)'''
    islas_list = nc.split_into_islands()

    return len(islas_list) > 1

if __name__ == "__main__":
    print(PATH)
    grid = vge.open_file(PATH)
    num_lines = len(grid.lines)
    print(f"Number of lines: {num_lines}")
    num_generators = len(grid.generators)
    print(f"Number of generators: {num_generators}")
    num_transformers = len(grid.transformers2w) + len(grid.transformers3w)
    print(f"Number of transformers: {num_transformers}")
    num_loads = len(grid.loads)
    print(f"Number of loads: {num_loads}")

    test_pycompss()

    # SET MODELS
    # TODO: Preguntar Pablo
    #set_models(grid)


    # Power FLOW
    pf_results = vge.power_flow(grid, vge.PowerFlowOptions(tolerance=1e-5, verbose=False)) 
    print('PF Converged:', pf_results.converged, 'error:', pf_results.error)
    #print(pf_results.get_bus_df())
    #print(pf_results.get_branch_df())

    # OPTIMAL POWER FLOW
    opf_options = vge.OptimalPowerFlowOptions(mip_solver=vge.MIPSolvers.HIGHS, verbose=False)
    opf_driver = vge.OptimalPowerFlowDriver(grid=grid, options=opf_options)
    opf_driver.run()
    print('OPF Converged:', opf_driver.results.converged, 'error:', opf_driver.results.error)

    # ESTABILITAT
    error1, error2 = False, False
    try:
        results = run_small_signal_analysis(grid)
    except Exception as e:
        error1 = True
        print(f"Error occurred a small_signal: {e}")
        try:
            results = run_small_signal_analysis2(grid)
        except Exception as e:
            error2 = True
            print(f"Error occurred a small_signal2: {e}")
    if error1 and error2:
        print("Both small signal analysis methods failed. Setting dummies")

    results = {
        'grid_name': GRID_NAME,
        'errors': True,
        'case_id': 1,
        'level': 'single',
        'type_combo': 'line',
        'elements': [
            {'type': 'line', 'id': 1}
        ],
        'gce.powerflow_converged': 'Dummy',
        'gce.run_powerflow_converged': 'Dummy',
        'stability': 'Dummy',
        'islands': detect_islands(grid)
    }
    print(results)

