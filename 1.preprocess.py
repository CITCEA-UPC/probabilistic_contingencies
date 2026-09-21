"""
Script per generar la base de dades de contingències.

Enumera totes les contingències N-1 i N-2 (línies, generadors i
transformadors) del grid configurat a config.py i les desa a la taula
'contingency_results' amb 'status= 'pending''.

Aquest script ha de ser ràpid (s'executa en sèrie abans de llançar el
processament paral·lel): només insereix les definicions de les
contingències, sense cap càlcul sobre el grid. Les columnes de resultat
('isolated_buses', 'n_islands', 'status', 'error_message', etc.) les omple
2.process.py, que és el que detecta els busos aïllats i classifica cada
contingència en entorn paral·lel. Vegeu docs/buses_aislados_emt.md.

Ús:
    python 1.preprocess.py
"""

import os
import sqlite3
import sys

import config

ROOT = config.ROOT
DB_FILE = config.DB_FILE
GRID_NAME = config.GRID_NAME
PATH = config.GRID_PATH
VERAGRID_SRC = config.VERAGRID_SRC
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

import VeraGridEngine.api as vge

# Esquema de la taula de resultats: les columnes de definició les omple
# aquest script; les de resultat (incloses les noves per detectar busos
# aïllats) les omple 2.process.py en processar cada contingència.
# Vegeu docs/buses_aislados_emt.md.
RESULT_COLUMNS = [
    ("contingency_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("grid_name", "TEXT"),
    ("grid_path", "TEXT NOT NULL"),
    ("lines", "TEXT"),
    ("generators", "TEXT"),
    ("transformers", "TEXT"),
    ("level", "INTEGER"),
    ("errors", "BOOLEAN"),
    ("powerflow_converged", "BOOLEAN"),
    ("stable", "BOOLEAN"),
    ("islands", "BOOLEAN"),
    ("execution_time", "REAL"),
    ("calculated", "BOOLEAN DEFAULT FALSE"),
    # Columnes afegides per detectar i classificar els casos de busos aïllats:
    #   isolated_buses: llista JSON amb els noms dels busos amb menys de 2
    #                   connexions actives després d'aplicar la contingència.
    #   n_islands:      nombre d'illes del circuit numèric post-contingència.
    #   status:         classificació del resultat ('pending', 'ok',
    #                   'isolated_buses', 'pf_not_converged',
    #                   'pf3_not_converged', 'emt_topology_error',
    #                   'small_signal_error', 'exception').
    #   error_message:  missatge d'error associat, si n'hi ha.
    #   eigenvalues:    llista JSON de parells [real, imag] amb els
    #                   autovalors de Floquet (domini s) dels modes
    #                   dominants; NULL si no s'han calculat.
    ("isolated_buses", "TEXT"),
    ("n_islands", "INTEGER"),
    ("status", "TEXT"),
    ("error_message", "TEXT"),
    ("eigenvalues", "TEXT"),
]


def ensure_schema(conn):
    """
    Crea la taula 'contingency_results' si no existeix i hi afegeix les
    columnes que faltin (migració lleugera per a bases de dades creades amb
    versions anteriors del preprocess).

    Args:
        conn: Connexió sqlite3 oberta sobre la base de dades de resultats.
    """
    columns_sql = ",\n".join(f"    {name} {decl}" for name, decl in RESULT_COLUMNS)
    conn.execute(f"CREATE TABLE IF NOT EXISTS contingency_results (\n{columns_sql}\n)")

    existing = {row[1] for row in conn.execute("PRAGMA table_info(contingency_results)")}
    for name, decl in RESULT_COLUMNS:
        if name not in existing and "PRIMARY KEY" not in decl:
            conn.execute(f"ALTER TABLE contingency_results ADD COLUMN {name} {decl}")
    conn.commit()


if config.TEST_1_PREPROCESS:
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print("Database file deleted")


def save_contingency(conn, name, path, lines, generators, transformers, level):
    """
    Desa la definició d'una contingència a la base de dades.

    Només insereix la definició (elements desconnectats i nivell) amb
    'status= 'pending''; les columnes de resultat, inclosa la detecció de
    busos aïllats, les omple 2.process.py en processar-la.

    Args:
        conn: Connexió sqlite3 oberta sobre la base de dades.
        name: Nom del grid.
        path: Camí al fitxer del grid.
        lines: Índexs de línies desactivades.
        generators: Índexs de generadors desactivats.
        transformers: Índexs de transformadors desactivats.
        level: Nivell de la contingència (1 = N-1, 2 = N-2).
    """
    print(
        f"Saving contingency: {name} - Level {level} - Lines: {lines} - "
        f"Generators: {generators} - Transformers: {transformers}"
    )
    conn.execute(
        """
        INSERT INTO contingency_results
            (grid_name, grid_path, lines, generators, transformers, level, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, str(path), str(lines), str(generators), str(transformers), level,
         "pending"),
    )


def check_database_and_tables():
    """
    Crea la base de dades i la taula 'contingency_results' si no existeixen,
    i hi afegeix les columnes que faltin (migració de BD antigues).

    Returns:
        sqlite3.Connection: Connexió oberta sobre la base de dades.
    """
    if not os.path.exists(DB_FILE):
        print("Creating results.db...")
        with open(DB_FILE, "w") as f:
            f.write("")

    conn = sqlite3.connect(DB_FILE)
    ensure_schema(conn)
    return conn


def main():
    conn = check_database_and_tables()
    print(PATH)
    grid = vge.open_file(PATH)
    print(f"Number of lines: {len(grid.lines)}")
    print(f"Number of generators: {len(grid.generators)}")
    print(f"Number of transformers: {len(grid.transformers2w) + len(grid.transformers3w)}")
    print(f"Number of loads: {len(grid.loads)}")

    def save(lines, generators, transformers, level):
        save_contingency(conn, GRID_NAME, PATH, lines, generators, transformers, level)

    # Lines 1 and 2 levels
    for line_id_1, _ in enumerate(grid.lines):
        save([line_id_1], [], [], 1)
        for line_id_2, _ in enumerate(grid.lines):
            if line_id_1 != line_id_2:
                save([line_id_1, line_id_2], [], [], 2)
        for generator_id, _ in enumerate(grid.generators):
            save([line_id_1], [generator_id], [], 2)
        for transformer_id, _ in enumerate(grid.transformers2w):
            save([line_id_1], [], [transformer_id], 2)

    # Generators 1 and 2 levels
    for generator_id_1, _ in enumerate(grid.generators):
        save([], [generator_id_1], [], 1)
        for generator_id_2, _ in enumerate(grid.generators):
            if generator_id_1 != generator_id_2:
                save([], [generator_id_1, generator_id_2], [], 2)
        for line_id, _ in enumerate(grid.lines):
            save([line_id], [generator_id_1], [], 2)
        for transformer_id, _ in enumerate(grid.transformers2w):
            save([], [generator_id_1], [transformer_id], 2)

    # Transformers 1 and 2 levels
    for transformer_id_1, _ in enumerate(grid.transformers2w):
        save([], [], [transformer_id_1], 1)
        for transformer_id_2, _ in enumerate(grid.transformers2w):
            if transformer_id_1 != transformer_id_2:
                save([], [], [transformer_id_1, transformer_id_2], 2)
        for line_id, _ in enumerate(grid.lines):
            save([line_id], [], [transformer_id_1], 2)
        for generator_id, _ in enumerate(grid.generators):
            save([], [generator_id], [transformer_id_1], 2)

    conn.commit()
    conn.close()

    with sqlite3.connect(DB_FILE) as summary_conn:
        total = summary_conn.execute("SELECT COUNT(*) FROM contingency_results").fetchone()[0]
    print(f"Total contingencies: {total}")


if __name__ == "__main__":
    main()
