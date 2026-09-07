import os
import sys
import sqlite3
import argparse
import ast
import time

import config

ROOT = config.ROOT
VERAGRID_SRC = config.VERAGRID_SRC
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

import VeraGridEngine.api as vge

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


def save_results_to_db(contingency_id, errors, powerflow_converged, stable, islands, execution_time, calculated):
    """Save the contingency information to a database file"""
    print(f"Saving contingency: {contingency_id}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE contingency_results
        SET errors = ?,
            powerflow_converged = ?,
            stable = ?,
            islands = ?,
            execution_time = ?,
            calculated = ?
        WHERE contingency_id = ?
    ''', (errors, powerflow_converged, stable, islands, execution_time, calculated, contingency_id))
    conn.commit()
    conn.close()

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

def run_small_signal_analysis(grid):



    result = {
        "stable": True,
        "error": False
    }
    return result

def calculate_contingency(contingency):
    """Calculate the contingency using VeraGridEngine and return the results."""
    tic = time.perf_counter()
    grid = vge.open_file(contingency["grid_path"])

    for line_id, _ in enumerate(grid.lines): 
        grid.lines[line_id].active = False
    for generator_id, _ in enumerate(grid.generators): 
        grid.generators[generator_id].active = False
    for transformer_id, _ in enumerate(grid.transformers2w): 
        grid.transformers2w[transformer_id].active = False

    pf_results = vge.power_flow(grid)
    small_signal_results = run_small_signal_analysis(grid)

    results = {
        "powerflow_converged": pf_results.converged,
        "stable": small_signal_results["stable"],
        "islands": detect_islands(grid),
        "errors": False or pf_results.error or small_signal_results["error"],
        "calculated": True,
    }

    results["execution_time"] = time.perf_counter() - tic
    return results



def save_results_to_db(contingency_id, errors, powerflow_converged, stable, islands, execution_time, calculated):
    """Save the contingency information to a database file"""
    print(f"Saving contingency: {contingency_id}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE contingency_results
        SET errors = ?,
            powerflow_converged = ?,
            stable = ?,
            islands = ?,
            execution_time = ?,
            calculated = ?
        WHERE contingency_id = ?
    ''', (errors, powerflow_converged, stable, islands, execution_time, calculated, contingency_id))
    conn.commit()
    conn.close()
    


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
    elif config.TEST:
        contingency_id = config.TEST_CONTINGENCY_ID
    else:
        parser.error("contingency_id is required when TEST is False")

    contingency = load_contingency_from_db(contingency_id)
    print(contingency)

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


