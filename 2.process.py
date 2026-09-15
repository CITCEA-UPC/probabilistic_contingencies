"""
Script per processar contingències individuals de la base de dades.

Aquest script carrega una contingència específica (definida per línies, generadors
i transformadors desactivats), executa un power flow i una simulació EMT per determinar
si el sistema és estable després de la contingència.

Ús:
    python 2.process.py <contingency_id>
    python 2.process.py  # si TEST_2_PROCESS=True a config.py
"""

import argparse
import ast
import os
import sqlite3
import time
import config

# Imports de VeraGridEngine per a simulacions
import VeraGridEngine.api as vge
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import *

# Templates per crear models EMT de cada tipus d'element
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_series_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

# Enumeracions per configurar la simulació EMT
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
)

DB_FILE = config.DB_FILE

def load_contingency_from_db(contingency_id):
    """
    Carrega una contingència de la base de dades pel seu ID.
    
    Args:
        contingency_id: ID primari de la contingència a carregar
        
    Returns:
        dict: Diccionari amb les dades de la contingència (grid_path, lines, generators, transformers)
        
    Raises:
        FileNotFoundError: Si no existeix la base de dades
        ValueError: Si no es troba la contingència amb l'ID especificat
    """
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
    """
    Guarda els resultats de la contingència a la base de dades.
    
    Args:
        contingency_id: ID de la contingència
        errors: Boolean, True si hi ha hagut errors
        powerflow_converged: Boolean, True si el power flow ha convergit
        stable: Boolean, True si el sistema és estable (EMT convergit)
        islands: Boolean, True si hi ha illes o busos aïllats
        execution_time: Temps d'execució en segons
        calculated: Boolean, True si s'ha calculat la contingència
    """
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
    Detecta si hi ha illes al grid (grups de busos aïllats entre si).
    
    Utilitza el circuit numèric de VeraGridEngine per dividir la xarxa
    en illes. Si hi ha més d'una illa, retorna True.
    
    Args:
        grid: Objecte MultiCircuit de VeraGridEngine
        
    Returns:
        bool: True si hi ha més d'una illa, False altrament
    """
    nc = vge.compile_numerical_circuit_at(grid, t_idx=None)
    islas_list = nc.split_into_islands()

    return len(islas_list) > 1


def get_buses_with_few_connections(grid):
    """
    Retorna el conjunt de busos que tenen menys de 2 connexions actives.
    
    L'EMT requereix que cada fase d'un bus tingui almenys 2 elements connectats.
    Busos amb 0 o 1 connexió causarien errors de "floating phases".
    
    Compta tant branques (línies, transformadors, VSC, etc.) com injeccions
    (generadors i càrregues) per determinar el nombre total de connexions actives.
    
    Args:
        grid: Objecte MultiCircuit de VeraGridEngine
        
    Returns:
        set: Conjunt de busos amb menys de 2 connexions actives
    """
    bus_connection_count = {}

    # Comptar branques actives connectades a cada bus
    for branch in grid.get_branches_iter(add_vsc=True, add_switch=True, add_hvdc=True):
        if branch.active:
            bus_connection_count[branch.bus_from] = bus_connection_count.get(branch.bus_from, 0) + 1
            bus_connection_count[branch.bus_to] = bus_connection_count.get(branch.bus_to, 0) + 1

    # Comptar generadors actius connectats a cada bus
    for gen in grid.generators:
        if gen.active:
            bus_connection_count[gen.bus] = bus_connection_count.get(gen.bus, 0) + 1

    # Comptar càrregues actives connectades a cada bus
    for load in grid.loads:
        if load.active:
            bus_connection_count[load.bus] = bus_connection_count.get(load.bus, 0) + 1

    # Retornar busos amb menys de 2 connexions
    return {bus for bus in grid.buses if bus_connection_count.get(bus, 0) < 2}

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
    stable = bool(emt_results.well_initialized.all()) and bool(emt_results.converged.all())
    result = {
        "stable": stable,
        "error": False
    }
    return result

def calculate_contingency(contingency):
    """Calculate the contingency using VeraGridEngine and return the results."""
    tic = time.perf_counter()
    grid = vge.open_file(contingency["grid_path"])

    # Desactivar els elements de la contingència
    for line_id in ast.literal_eval(contingency["lines"]):
        grid.lines[line_id].active = False
    for gen_id in ast.literal_eval(contingency["generators"]):
        grid.generators[gen_id].active = False
    for trafo_id in ast.literal_eval(contingency["transformers"]):
        grid.transformers2w[trafo_id].active = False

    # Detectar busos problemàtics (menys de 2 connexions actives)
    # Aquests busos causarien errors EMT per "floating phases"
    problematic_buses = get_buses_with_few_connections(grid)
    has_islands = len(problematic_buses) > 0 or detect_islands(grid)

    pf_results = vge.power_flow(grid)

    # Si el PF no convergeix, no fer EMT
    if not pf_results.converged:
        return {
            "powerflow_converged": pf_results.converged,
            "stable": False,
            "islands": has_islands,
            "errors": False,
            "calculated": True,
            "execution_time": time.perf_counter() - tic,
        }

    # Crear models EMT només per a elements actius i busos no problemàtics
    for bus in grid.buses:
        if bus not in problematic_buses:
            get_bus_emt_template(grid, bus)

    for line in grid.lines:
        if line.active:
            model = get_pi_line_emt_template(
                vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True,
                name=f"{line.name}", numerical_damping_conductance=0.0,
            ).block
            set_emt_model(device=line, model=model, var_factory=grid.var_factory)

    for gen in grid.generators:
        if gen.active and gen.bus not in problematic_buses:
            model = get_complete_generator_template_emt(
                vf=grid.var_factory, conventional_three_phase_base=True,
            ).block
            set_emt_model(device=gen, model=model, var_factory=grid.var_factory)

    for trafo in grid.transformers2w:
        if trafo.active:
            model = get_series_transformer_emt_template(
                vf=grid.var_factory, name=f"{trafo.name}",
                r=trafo.R, x=trafo.X, tap_module=trafo.tap_module,
            ).block
            set_emt_model(device=trafo, model=model, var_factory=grid.var_factory)

    for load in grid.loads:
        if load.active and load.bus not in problematic_buses:
            model = get_shunt_rlc_combo_emt_template(
                vf=grid.var_factory, include_r=True,
                include_l=abs(load.Q) > 1.0e-15, include_c=False,
                phA=True, phB=True, phC=True,
                connection_type=ShuntConnectionType.FloatingStar,
                name=f"{load.name}_RL_emt",
            ).block
            set_emt_model(device=load, model=model, var_factory=grid.var_factory)

    emt_results = run_small_signal_emt_analysis(grid, pf_results)

    return {
        "powerflow_converged": pf_results.converged,
        "stable": emt_results["stable"],
        "islands": has_islands,
        "errors": not pf_results.converged or emt_results["error"],
        "calculated": True,
        "execution_time": time.perf_counter() - tic,
    }


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

    try:
        result = calculate_contingency(contingency)
    except Exception as e:
        print(f"Error processing contingency {contingency_id}: {e}")
        result = {
            "powerflow_converged": False,
            "stable": False,
            "islands": False,
            "errors": True,
            "calculated": True,
            "execution_time": 0.0,
        }

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


