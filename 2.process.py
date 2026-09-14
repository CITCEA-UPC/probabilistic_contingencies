import argparse
import ast
import os
import sqlite3
import time
import config

import VeraGridEngine.api as vge
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import *
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_series_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
)

DB_FILE = config.DB_FILE

def load_contingency_from_db(contingency_id):
    """Load one contingency from the database by its primary key and returns a dictionary."""
    database_path = DB_FILE
    if not os.path.exists(database_path):
        raise FileNotFoundError(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        contingency = connection.execute(
            "SELECT * FROM contingency_results WHERE contingency_id = ?",
            (contingency_id,),
        ).fetchone()

    if contingency is None:
        raise ValueError(f"Contingency not found: {contingency_id}")

    contingency = dict(contingency)
    return contingency


def save_results_to_db(
    contingency_id,
    errors,
    powerflow_converged,
    stable,
    islands,
    execution_time,
    calculated,
):
    """Save the contingency information to a database file"""
    print(f"Saving contingency: {contingency_id}")

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            UPDATE contingency_results
            SET errors = ?,
                powerflow_converged = ?,
                stable = ?,
                islands = ?,
                execution_time = ?,
                calculated = ?
            WHERE contingency_id = ?
            """,
            (
                errors,
                powerflow_converged,
                stable,
                islands,
                execution_time,
                calculated,
                contingency_id,
            ),
        )

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

def run_small_signal_emt_analysis(grid, pf_results):
    emt_options = EmtOptions(
        time_step=1e-6,
        simulation_time=0.02,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralAD,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Auto,
        verbose=0,
    )

    driver = EmtSimulationDriver(grid=grid, options=emt_options, pf_results=pf_results)
    driver.run()
    emt_results = driver.results
    result = {
        "stable": emt_results,
        "error": False
    }
    return result

def calculate_contingency(contingency):
    """Calculate the contingency using VeraGridEngine and return the results."""
    tic = time.perf_counter()
    grid = vge.open_file(contingency["grid_path"])

    lines_to_deactivate = ast.literal_eval(contingency["lines"])
    generators_to_deactivate = ast.literal_eval(contingency["generators"])
    transformers_to_deactivate = ast.literal_eval(contingency["transformers"])

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    for line_id in lines_to_deactivate:
        grid.lines[line_id].active = False

    for generator_id in generators_to_deactivate:
        grid.generators[generator_id].active = False

    for transformer_id in transformers_to_deactivate:
        grid.transformers2w[transformer_id].active = False

    for line_id, line in enumerate(grid.lines):
        if line.active:
            line_emt_model = get_pi_line_emt_template(
                vf=grid.var_factory,
                phN=False,
                phA=True,
                phB=True,
                phC=True,
                name=f"{line.name}",
                numerical_damping_conductance=0.0,
            ).block
            set_emt_model(device=line, model=line_emt_model, var_factory=grid.var_factory)

    for generator_id, generator in enumerate(grid.generators):
        if generator.active:
            generator_emt_model = get_complete_generator_template_emt(
                vf=grid.var_factory,
                conventional_three_phase_base=True,
            ).block
            set_emt_model(device=generator, model=generator_emt_model, var_factory=grid.var_factory)

    for transformer_id, transformer in enumerate(grid.transformers2w):
        if transformer.active:
            transformer_emt_model = get_series_transformer_emt_template(
                vf=grid.var_factory,
                name=f"{transformer.name}",
                r=transformer.R,
                x=transformer.X,
                tap_module=transformer.tap_module,
            ).block
            set_emt_model(device=transformer, model=transformer_emt_model, var_factory=grid.var_factory)

    for load_id, load in enumerate(grid.loads):
        load_emt_model = get_shunt_rlc_combo_emt_template(
            vf=grid.var_factory,
            include_r=True,
            include_l=abs(load.Q) > 1.0e-15,
            include_c=False,
            phA=True,
            phB=True,
            phC=True,
            connection_type=ShuntConnectionType.FloatingStar,
            name=f"{load.name}_RL_emt",
        ).block
        set_emt_model(device=load, model=load_emt_model, var_factory=grid.var_factory)

    pf_results = vge.power_flow(grid)
    small_signal_emt_results = run_small_signal_emt_analysis(grid, pf_results)

    results = {
        "powerflow_converged": pf_results.converged,
        "stable": small_signal_emt_results["stable"],
        "islands": detect_islands(grid),
        "errors": False or pf_results.error or small_signal_emt_results["error"],
        "calculated": True,
    }

    results["execution_time"] = time.perf_counter() - tic
    return results


def main():
    parser = argparse.ArgumentParser(description="Process one contingency from the database.")
    parser.add_argument(
        "contingency_id",
        type=int,
        nargs="?",
        help="Primary key of the contingency to process",
    )
    args = parser.parse_args()

    if args.contingency_id is not None:
        contingency_id = args.contingency_id
    elif config.TEST_2_PROCESS:
        contingency_id = config.TEST_CONTINGENCY_ID
    else:
        parser.error("contingency_id is required when TEST_2_PROCESS is False")

    contingency = load_contingency_from_db(contingency_id)

    result = calculate_contingency(contingency)
    print(result)
    save_results_to_db(
        contingency_id=contingency_id,
        errors=result["errors"],
        powerflow_converged=result["powerflow_converged"],
        stable=result["stable"],
        islands=result["islands"],
        execution_time=result["execution_time"],
        calculated=result["calculated"],
    )
    

if __name__ == "__main__":
    main()


