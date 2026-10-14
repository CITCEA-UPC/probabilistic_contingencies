"""
main.py — punt d'entrada del pipeline de contingències amb PyCOMPSs.

Modes d'ús:

  1. PIPELINE COMPLET (sense flags, comportament per defecte): genera la base
     de dades (preprocess) i tot seguit processa totes les contingències
     'pending' en paral·lel. Si ``config.CLEAR_DB_ON_START`` és True, esborra
     la BD existent abans de regenerar-la.

  2. PREPROCESS (flag ``--preprocess``): NOMÉS genera la base de dades i surt
     (no llança cap tasca). Útil per generar-la en un pas separat.

  3. PROCESS (flags ``--ids`` / ``--all`` / ``--pending``): processa una
     selecció de contingències sense regenerar la base de dades (assumeix que
     ja existeix).

Cada contingència es processa com una ``@task`` que escriu directament el
resultat a la BD (cicle ``load -> calculate -> save`` de
``contingency.process_contingency``). El mestre llança les tasques, espera que
acabin (``compss_wait_on``) i imprimeix un resum.

Selecció de contingències per al PROCESS (per ordre de prioritat):

    --ids 1,2,3   →  només les contingències indicades
    --all         →  TOTES (reprocessa també les ja calculades)
    --pending     →  només les que tenen status='pending'

Ús:
    python main.py                     # pipeline complet: genera la BD + processa tot
    python main.py --preprocess        # només genera la BD
    python main.py --pending           # només processa les 'pending'
    python main.py --all               # reprocessa TOTES (sense regenerar)
    python main.py --ids 1,2,3         # només unes quantes (a posteriori)

En local (sense PyCOMPSs instal·lat) s'importa el paquet ``pycompss_dummies``,
que executa les ``@task`` en sèrie; al BSC es fa servir PyCOMPSs real i les
tasques es distribueixen en paral·lel pels nodes/cores.
"""

import argparse
import os
import sqlite3
import sys

# PyCOMPSs imports (amb fallback als dummies per provar en local sense COMPSs)
try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
    from pycompss.api.constraint import constraint
except ImportError:
    from pycompss_dummies.task import task
    from pycompss_dummies.api import compss_wait_on
    from pycompss_dummies.constraint import constraint

import config
import contingency

# config.py ja injecta VeraGrid_TenSyGrid/src a sys.path.
import VeraGridEngine.api as vge


# =============================================================================
# PREPROCESS — generació de la base de dades de contingències
# =============================================================================

# Esquema de la taula de resultats: les columnes de definició les omple el
# preprocess; les de resultat les omple contingency.py en processar cada
# contingència. Vegeu docs/buses_aislados_emt.md.
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
    ("isolated_buses", "TEXT"),
    ("n_islands", "INTEGER"),
    ("status", "TEXT"),
    ("error_message", "TEXT"),
    ("eigenvalues", "TEXT"),
    ("opf_needed", "BOOLEAN"),
    ("opf_converged", "BOOLEAN"),
]


def ensure_schema(conn):
    """
    Crea la taula 'contingency_results' si no existeix i hi afegeix les
    columnes que faltin (migració lleugera per a bases de dades antigues).
    """
    columns_sql = ",\n".join(f"    {name} {decl}" for name, decl in RESULT_COLUMNS)
    conn.execute(f"CREATE TABLE IF NOT EXISTS contingency_results (\n{columns_sql}\n)")

    existing = {row[1] for row in conn.execute("PRAGMA table_info(contingency_results)")}
    for name, decl in RESULT_COLUMNS:
        if name not in existing and "PRIMARY KEY" not in decl:
            conn.execute(f"ALTER TABLE contingency_results ADD COLUMN {name} {decl}")
    conn.commit()


def check_database_and_tables():
    """
    Crea la base de dades i la taula 'contingency_results' si no existeixen.

    Returns:
        sqlite3.Connection: Connexió oberta sobre la base de dades.
    """
    if not os.path.exists(config.DB_FILE):
        print("Creating results.db...")
        with open(config.DB_FILE, "w") as f:
            f.write("")

    conn = sqlite3.connect(config.DB_FILE)
    ensure_schema(conn)
    return conn


def save_contingency(conn, name, path, lines, generators, transformers, level):
    """
    Desa la definició d'una contingència a la base de dades.

    Només insereix la definició (elements desconnectats i nivell) amb
    'status= 'pending''; les columnes de resultat les omple
    contingency.process_contingency en processar-la.
    """
    print(
        f"Saving contingency: {name} - Level {level} - Lines: {lines} - "
        f"Generators: {generators} - Transformers: {transformers}"
    )
    # Desa el camí RELATIU al ROOT del repo, perquè la BD sigui portable entre
    # màquines (local, BSC, etc.). contingency.resolve_grid_path el reconverteix.
    relative_path = os.path.relpath(path, config.ROOT)
    conn.execute(
        """
        INSERT INTO contingency_results
            (grid_name, grid_path, lines, generators, transformers, level, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, relative_path, str(lines), str(generators), str(transformers), level,
         "pending"),
    )


def run_preprocess():
    """
    Genera (o regenera) la base de dades de contingències.

    Enumera totes les contingències N-1 i N-2 del grid de config.py i les
    insereix amb status='pending'. Si config.CLEAR_DB_ON_START és True, esborra
    la BD existent abans de començar.
    """
    if getattr(config, "CLEAR_DB_ON_START", False) and os.path.exists(config.DB_FILE):
        os.remove(config.DB_FILE)
        print("Deleted existing database (CLEAR_DB_ON_START = True).")

    conn = check_database_and_tables()
    grid = vge.open_file(config.GRID_PATH)
    print(f"Number of lines: {len(grid.lines)}")
    print(f"Number of generators: {len(grid.generators)}")
    print(f"Number of transformers: {len(grid.transformers2w) + len(grid.transformers3w)}")
    print(f"Number of loads: {len(grid.loads)}")

    def save(lines, generators, transformers, level):
        save_contingency(conn, config.GRID_NAME, config.GRID_PATH,
                         lines, generators, transformers, level)

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

    with sqlite3.connect(config.DB_FILE) as summary_conn:
        total = summary_conn.execute(
            "SELECT COUNT(*) FROM contingency_results"
        ).fetchone()[0]
    print(f"Total contingencies: {total}")


# =============================================================================
# PROCESS — les @task
# =============================================================================

@constraint(computing_units="1")
@task(returns=1)
def process_contingency_task(contingency_id):
    """
    Tasca PyCOMPSs: calcula una contingència i n'escriu el resultat a la BD.

    ``computing_units="1"`` indica que cada tasca ocupa un sol core (el càlcul
    de VeraGrid és monofil), de manera que se'n poden executar tantes com
    cores disponibles en paral·lel.

    Args:
        contingency_id: ID primari de la contingència a processar.

    Returns:
        dict: El resultat desat a la base de dades (per al resum del mestre).
    """
    return contingency.process_contingency(contingency_id)


def select_contingency_ids(args):
    """
    Determina els IDs a processar segons --ids / --all / --pending.

    Prioritat: --ids > --all > --pending (que és també el comportament per
    defecte quan no es passa cap flag).
    """
    if args.ids:
        return [int(i) for i in args.ids.split(",")]

    where = "" if args.all else "WHERE status = 'pending'"
    with sqlite3.connect(config.DB_FILE) as conn:
        rows = conn.execute(
            f"SELECT contingency_id FROM contingency_results {where} ORDER BY contingency_id"
        )
        return [row[0] for row in rows]


def main():
    parser = argparse.ArgumentParser(
        description="Probabilistic contingency analysis with PyCOMPSs."
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Generate the contingencies database and exit (no tasks launched).",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated list of contingency IDs to process (e.g. '1,2,3').",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Reprocess ALL contingencies (including already calculated ones).",
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help="Process only 'pending' contingencies (skip the preprocess).",
    )
    args = parser.parse_args()

    # --preprocess: NOMÉS genera la BD i surt.
    if args.preprocess:
        run_preprocess()
        return

    # Pipeline complet per defecte (sense cap flag de selecció): genera la BD
    # i després processa les contingències.
    if not (args.ids or args.all or args.pending):
        run_preprocess()

    if not os.path.exists(config.DB_FILE):
        print(f"Database not found: {config.DB_FILE}", file=sys.stderr)
        print("Run with --preprocess first to generate it.", file=sys.stderr)
        return

    ids = select_contingency_ids(args)
    if not ids:
        print("No contingencies to process.")
        return

    print(f"Launching {len(ids)} contingency task(s)...")

    # Llança totes les @task (retornen un future amb PyCOMPSs real, o el
    # resultat directe amb els dummies) i espera que acabin.
    futures = [process_contingency_task(cid) for cid in ids]
    results = compss_wait_on(futures)

    n_ok = sum(1 for r in results if r.get("status") == contingency.STATUS_OK)
    n_fail = len(results) - n_ok
    print(f"Done: {len(results)} contingency(ies) processed "
          f"({n_ok} ok, {n_fail} other).")


if __name__ == "__main__":
    main()
