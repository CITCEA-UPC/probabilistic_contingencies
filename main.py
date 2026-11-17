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

El mestre carrega les definicions i les envia a les ``@task``. Els workers
només calculen: no llegeixen ni escriuen SQLite. El mestre espera els
resultats (``compss_wait_on``) per lots i els desa en transaccions amb
``contingencies.storage``. ``--batch-size`` controla quants resultats es
desen a cada lot (per defecte 256), sense limitar la concurrència de tasques.
Els lots confirmats es conserven si l'execució s'interromp. Després del
càlcul, imprimeix un resum i genera els informes de risc
de tota la BD (CSV, JSON i gràfics, amb N−2 úniques). ``--skip-risk`` omet
aquests informes; ``--preprocess`` continua generant només la BD.
Amb ``--ids``, l’informe inclou també la resta de la BD i la seva cobertura.
Si no queden tasques pendents, es regeneren igualment els informes.

Selecció de contingències per al PROCESS (per ordre de prioritat):

    --ids 1,2,3   →  només les contingències indicades
    --all         →  TOTES (reprocessa també les ja calculades)
    --pending     →  només les que tenen status='pending'

Ús:
    python main.py                     # pipeline complet: genera la BD + processa tot
    python main.py --preprocess        # només genera la BD
    python main.py --pending           # només processa les 'pending'
    python main.py --all               # reprocessa TOTES (sense regenerar)
    python main.py --ids 1,2,3         # calcula aquests IDs i informa de tota la BD
    python main.py --ids 13 --skip-risk # depura un cas sense generar informes
    python main.py --pending --risk-out outputs/plots/prova # selecciona la carpeta d’informes

En local (sense PyCOMPSs instal·lat) s'importa el paquet ``contingencies.pycompss_dummies``,
que executa les ``@task`` en sèrie; al BSC es fa servir PyCOMPSs real i les
tasques es distribueixen en paral·lel pels nodes/cores.
"""

import argparse
import os
import sqlite3
import sys

# local_exec.sh força els dummies per depurar en un únic procés, fins i tot
# si PyCOMPSs està instal·lat. Al BSC es mantenen els imports del runtime real.
if os.environ.get("CONTINGENCIES_LOCAL") == "1":
    from contingencies.pycompss_dummies.task import task
    from contingencies.pycompss_dummies.api import compss_wait_on, compss_delete_object
    from contingencies.pycompss_dummies.constraint import constraint
else:
    try:
        from pycompss.api.task import task
        from pycompss.api.api import compss_wait_on, compss_delete_object
        from pycompss.api.constraint import constraint
    except ImportError:
        from contingencies.pycompss_dummies.task import task
        from contingencies.pycompss_dummies.api import compss_wait_on, compss_delete_object
        from contingencies.pycompss_dummies.constraint import constraint

import config
from contingencies import contingency, storage

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
    os.makedirs(os.path.dirname(config.DB_FILE), exist_ok=True)
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

# Cores que ocupa cada @task. Es pot sobreescriure amb la variable d'entorn
# COMPUTING_UNITS (p. ex. COMPUTING_UNITS=8). El càlcul de VeraGrid és
# monofil, així que 1 és el valor "natural" (màxima concurrència: tantes
# tasques com cores per node). Si les tasques consumeixen molta memòria i vols
# limitar quantes corren alhora per node, puja aquest valor: amb
# computing_units=8 i 112 cores/node corren ~14 tasques per node en lloc de 112.
COMPUTING_UNITS = os.environ.get("COMPUTING_UNITS", "1")


@constraint(computing_units=COMPUTING_UNITS)
@task(returns=1)
def process_contingency_task(definition):
    """Worker sense accés a SQLite; retorna l'ID juntament amb el resultat."""
    return {
        "contingency_id": definition["contingency_id"],
        "result": contingency.process_contingency(definition),
    }


def process_selected_contingencies(ids, batch_size):
    """Envia les tasques i desa els resultats al mestre per lots atòmics."""
    definitions = storage.load_definitions(config.DB_FILE, ids)
    futures = [process_contingency_task(definition) for definition in definitions]
    n_ok = 0
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        batch = futures[start:end]
        results = compss_wait_on(batch)
        storage.save_results(config.DB_FILE, results, expected_ids=ids[start:end])
        n_ok += sum(item["result"].get("status") == contingency.STATUS_OK for item in results)
        compss_delete_object(*batch)
        futures[start:end] = [None] * len(batch)
        print(f"Committed {min(end, len(ids))}/{len(ids)} contingency results.")
    return n_ok, len(ids) - n_ok


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def select_contingency_ids(args):
    """
    Determina els IDs a processar segons --ids / --all / --pending.

    Prioritat: --ids > --all > --pending (que és també el comportament per
    defecte quan no es passa cap flag).
    """
    if args.ids:
        return list(dict.fromkeys(int(i) for i in args.ids.split(",")))

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
    parser.add_argument(
        "--skip-risk",
        action="store_true",
        help="Skip risk reports after processing (useful for debugging one case).",
    )
    parser.add_argument(
        "--risk-out",
        default=None,
        help="Risk report folder (default: outputs/plots/risk_analysis/<database name>).",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Use a separate SQLite database instead of config.DB_FILE (also applies to preprocess).",
    )
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=256,
        help="Results per SQLite transaction on the master (default: 256; does not limit task concurrency).",
    )
    args = parser.parse_args()
    if args.db is not None:
        config.DB_FILE = os.path.abspath(os.path.expanduser(args.db))

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
    if ids:
        print(f"Launching {len(ids)} contingency task(s)...")

        n_ok, n_fail = process_selected_contingencies(ids, args.batch_size)
        print(f"Done: {len(ids)} contingency(ies) processed "
              f"({n_ok} ok, {n_fail} other).")
    else:
        print("No contingencies to process.")

    if not args.skip_risk:
        from risk_analysis import run_analysis

        print("Generating risk reports from the entire database (unique N-2 pairs)...")
        try:
            run_analysis(config.DB_FILE, out_dir=args.risk_out)
        except Exception:
            print("Risk report generation failed; simulation results remain saved in the database.",
                  file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
