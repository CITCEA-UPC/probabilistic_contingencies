"""Accés SQLite del mestre. Els workers reben definicions i retornen resultats."""

import json
import sqlite3
from pathlib import Path

DB_TIMEOUT = 60
DEFINITION_COLUMNS = ("contingency_id", "grid_name", "grid_path", "lines",
                      "generators", "transformers", "level")
RESULT_COLUMNS = ("errors", "powerflow_converged", "stable", "islands",
                  "execution_time", "calculated", "isolated_buses", "n_islands",
                  "status", "error_message", "eigenvalues", "opf_needed", "opf_converged")


def load_definitions(db_file, ids):
    """Carrega definicions en l'ordre demanat i valida tots els IDs abans de calcular.

    Només llegeix les columnes de definició. Fragmenta les consultes per no
    superar el límit de paràmetres SQLite amb desenes de milers d'IDs.
    """
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate contingency IDs")
    definitions = {}
    uri = Path(db_file).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=DB_TIMEOUT) as conn:
        conn.row_factory = sqlite3.Row
        for start in range(0, len(ids), 900):
            chunk = ids[start:start + 900]
            placeholders = ','.join('?' for _ in chunk)
            query = f"SELECT {','.join(DEFINITION_COLUMNS)} FROM contingency_results WHERE contingency_id IN ({placeholders})"
            definitions.update((row['contingency_id'], dict(row)) for row in conn.execute(query, chunk))
    missing = [cid for cid in ids if cid not in definitions]
    if missing:
        raise ValueError(f"Contingencies not found: {missing[:20]}")
    return [definitions[cid] for cid in ids]


def save_results(db_file, results, expected_ids):
    """Desa un lot complet en una transacció, validant la correspondència dels IDs.

    Si falta un resultat, hi ha IDs inesperats/duplicats o falla una escriptura,
    no es desa cap fila del lot. Els lots anteriors ja confirmats es conserven.
    """
    ids = [item['contingency_id'] for item in results]
    if (len(ids) != len(expected_ids) or len(set(ids)) != len(ids)
            or set(ids) != set(expected_ids)):
        raise ValueError("Result IDs do not match the submitted batch")
    if not results:
        return
    values = []
    for item in results:
        result = item['result']
        # Valida també les claus opcionals abans d'obrir la transacció:
        # un resultat incomplet no ha de deixar dades antigues barrejades.
        row = [result[column] for column in RESULT_COLUMNS]
        row[RESULT_COLUMNS.index('isolated_buses')] = json.dumps(result['isolated_buses'] or [])
        values.append((*row, item['contingency_id']))
    assignments = ','.join(f'{name}=?' for name in RESULT_COLUMNS)
    uri = Path(db_file).resolve().as_uri() + "?mode=rw"
    with sqlite3.connect(uri, uri=True, timeout=DB_TIMEOUT) as conn:
        cursor = conn.executemany(
            f"UPDATE contingency_results SET {assignments} WHERE contingency_id=?", values)
        if cursor.rowcount != len(results):
            raise ValueError("Some contingency rows disappeared before saving the batch")
