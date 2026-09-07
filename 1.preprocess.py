import os
import sys
import sqlite3

import config

ROOT = config.ROOT
DB_FILE = config.DB_FILE
GRID_NAME = config.GRID_NAME
PATH = config.GRID_PATH
VERAGRID_SRC = config.VERAGRID_SRC
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

import VeraGridEngine.api as vge


if config.TEST_1_PREPROCESS:
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    print("Database file deleted")

def save_contingency(name, path, lines, generators, transformers, level):
    """Save the contingency information to a database file"""
    print(
        f"Saving contingency: {name} - Level {level} - Lines: {lines} - "
        f"Generators: {generators} - Transformers: {transformers}"
    )
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contingency_results (grid_name, grid_path, lines, generators, transformers, level)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, str(path), str(lines), str(generators), str(transformers), level))
    conn.commit()
    conn.close()

 
def check_database_and_tables():
    """Check if exists a file called results.db in the current directory. If not, create it."""
    if not os.path.exists(DB_FILE):
        print("Creating results.db...")
        with open(DB_FILE, "w") as f:
            f.write("")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contingency_results
        (
            contingency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grid_name TEXT,
            grid_path TEXT NOT NULL,
            lines TEXT,
            generators TEXT,
            transformers TEXT,
            level INTEGER,
            errors BOOLEAN,
            powerflow_converged BOOLEAN,
            stable BOOLEAN,
            islands BOOLEAN,
            execution_time REAL,
            calculated BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    conn.close()

def main():
    check_database_and_tables()
    print(PATH)
    grid = vge.open_file(PATH)
    print(f"Number of lines: {len(grid.lines)}")
    print(f"Number of generators: {len(grid.generators)}")
    print(f"Number of transformers: {len(grid.transformers2w) + len(grid.transformers3w)}")
    print(f"Number of loads: {len(grid.loads)}")

    # Lines 1 and 2 levels
    for line_id_1, _ in enumerate(grid.lines):
        save_contingency(GRID_NAME, PATH, [line_id_1], [], [], 1)
        for line_id_2, _ in enumerate(grid.lines):
            if line_id_1 != line_id_2:
                save_contingency(GRID_NAME, PATH, [line_id_1, line_id_2], [], [], 2)
        for generator_id, _ in enumerate(grid.generators):
            save_contingency(GRID_NAME, PATH, [line_id_1], [generator_id], [], 2)
        for transformer_id, _ in enumerate(grid.transformers2w):
            save_contingency(GRID_NAME, PATH, [line_id_1], [], [transformer_id], 2)

    # Generators 1 and 2 levels
    for generator_id_1, _ in enumerate(grid.generators):
        save_contingency(GRID_NAME, PATH, [], [generator_id_1], [], 1)
        for generator_id_2, _ in enumerate(grid.generators):
            if generator_id_1 != generator_id_2:
                save_contingency(GRID_NAME, PATH, [], [generator_id_1, generator_id_2], [], 2)
        for line_id, _ in enumerate(grid.lines):
            save_contingency(GRID_NAME, PATH, [line_id], [generator_id_1], [], 2)
        for transformer_id, _ in enumerate(grid.transformers2w):
            save_contingency(GRID_NAME, PATH, [], [generator_id_1], [transformer_id], 2)

    for transformer_id_1, _ in enumerate(grid.transformers2w):
        save_contingency(GRID_NAME, PATH, [], [], [transformer_id_1], 1)
        for transformer_id_2, _ in enumerate(grid.transformers2w):
            if transformer_id_1 != transformer_id_2:
                save_contingency(GRID_NAME, PATH, [], [], [transformer_id_1, transformer_id_2], 2)
        for line_id, _ in enumerate(grid.lines):
            save_contingency(GRID_NAME, PATH, [line_id], [], [transformer_id_1], 2)
        for generator_id, _ in enumerate(grid.generators):
            save_contingency(GRID_NAME, PATH, [], [generator_id], [transformer_id_1], 2)

if __name__ == "__main__":
    main()
