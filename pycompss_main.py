"""
Punt d'entrada PyCOMPSs per processar contingències en paral·lel.

Cada contingència es processa com una ``@task`` que escriu directament el
resultat a la base de dades SQLite (cicle ``load -> calculate -> save`` de
``contingency.process_contingency``). El mestre només llança les tasques,
espera que acabin (``compss_wait_on``) i imprimeix un resum.

Selecció de contingències (per ordre de prioritat):

    --ids 1,2,3   →  només les contingències indicades
    --all         →  TOTES (reprocessa també les ja calculades)
    --pending     →  només les que tenen status='pending'
    (sense flags) →  igual que --pending (comportament per defecte)

Ús:
    python pycompss_main.py
    python pycompss_main.py --pending
    python pycompss_main.py --all
    python pycompss_main.py --ids 1,2,3

En local (sense PyCOMPSs instal·lat) s'importa el paquet ``pycompss_dummies``,
que executa les ``@task`` en sèrie; al BSC es fa servir PyCOMPSs real i les
tasques es distribueixen en paral·lel pels nodes/cores.
"""

import argparse
import sqlite3

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
        description="Process contingencies in parallel with PyCOMPSs."
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
        help="Process only 'pending' contingencies (default behaviour).",
    )
    args = parser.parse_args()

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
