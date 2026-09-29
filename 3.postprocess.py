"""
3.postprocess.py — Índex de risc de vulnerabilitat i plots.

Llegeix la base de dades de resultats (config.DB_FILE) i calcula, per a cada
element de la xarxa (línies, transformadors i generadors), l'índex de risc de
vulnerabilitat definit a teoria.md:

    S_c ∈ {0, 1}                    severitat binària (1 = fallada del sistema)
    P_j ≈ λ_j                       pes relatiu (probabilitat anual de fallada)
    R_i^(1) = S_i                   risc N-1 (vulnerabilitat individual)
    R_i^(2) = Σ_{j≠i} P_j·S_{i,j}   risc N-2 (combinacions, sumant els 2 ordres)
    R_i = R_i^(1) + R_i^(2)         risc total
    RI  = normalitzat a [0,1] pel màxim global
    j*_i = argmax_j P_j·S_{i,j}     segon element més crític per a cada i

"Fallada del sistema" (severitat S=1) es defineix de forma estricta com:
    - formació d'illes (n_islands > 1), incloent busos aïllats,
    - no-convergència final del power flow (pf_not_converged, pf3_not_converged,
      pf3_error),
    - inestabilitat de petit senyal (status='ok' però stable=False),
    - errors (exception, emt_topology_error, small_signal_error).

Genera 4 plots a la carpeta plots/ (barres apilades N-1 + N-2):
    - risk_lines.png        (línies)
    - risk_transformers.png (transformadors)
    - risk_generators.png   (generadors)
    - risk_group.png        (tots els elements junts)
i desa les dades numèriques a plots/risk_index.csv.

Ús:
    python 3.postprocess.py
    python 3.postprocess.py --db /ruta/a/una_altra.db
"""

import argparse
import ast
import csv
import os
import sqlite3
from collections import defaultdict

import numpy as np
import matplotlib

matplotlib.use("Agg")  # per a entorns sense display (BSC)
import matplotlib.pyplot as plt

import config

DB_FILE = config.DB_FILE
PLOTS_DIR = os.path.join(config.ROOT, "plots")

# Taxes de fallada anuals per tipus d'element (P_j ≈ λ_j), valors genèrics.
LAMBDA = {
    "line": 0.05,
    "transformer": 0.02,
    "generator": 0.10,
}

TYPE_LABEL = {
    "line": "Line",
    "transformer": "Trafo",
    "generator": "Gen",
}

# Ordre canònic dels tipus (per ordenar els elements i les columnes).
TYPE_ORDER = {"line": 0, "transformer": 1, "generator": 2}

# Estats que impliquen "fallada del sistema" (severitat S=1).
FAILURE_STATUSES = {
    "isolated_buses",
    "pf_not_converged",
    "pf3_not_converged",
    "pf3_error",
    "exception",
    "emt_topology_error",
    "small_signal_error",
}


def element_key(e):
    """Clau d'ordenació per a un element (type, index)."""
    t, i = e
    return (TYPE_ORDER[t], i)


def element_label(e):
    """Etiqueta llegible d'un element (type, index)."""
    t, i = e
    return f"{TYPE_LABEL[t]} {i}"


def parse_elements(row):
    """Llista d'elements (type, index) desconnectats en una contingència."""
    elements = []
    for i in ast.literal_eval(row["lines"]):
        elements.append(("line", i))
    for i in ast.literal_eval(row["generators"]):
        elements.append(("generator", i))
    for i in ast.literal_eval(row["transformers"]):
        elements.append(("transformer", i))
    return elements


def severity(row):
    """Severitat binària S_c. None si la contingència encara està 'pending'."""
    status = row["status"]
    if status == "pending":
        return None

    # Criteri estricte: qualsevol formació d'illes (n_islands > 1) compta.
    if bool(row["islands"]):
        return 1
    if status in FAILURE_STATUSES:
        return 1
    if status == "ok":
        return 0 if bool(row["stable"]) else 1

    # Estat desconegut → conservador (fallada).
    return 1


def load_rows(db_file):
    """Carrega totes les files de contingency_results com a llista de dicts."""
    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM contingency_results")]


def normalize(values):
    """Normalitza un dict element→valor pel seu màxim (0 si el màxim és 0)."""
    if not values:
        return {}
    m = max(values.values())
    if m <= 0:
        return {k: 0.0 for k in values}
    return {k: v / m for k, v in values.items()}


def compute_risk_index(rows):
    """
    Calcula els índexs de risc per element a partir de les files de la BD.

    Returns:
        tuple: (elements, resultats, pending_count) on
            elements: llista ordenada d'elements (type, index)
            resultats: dict element -> dict amb R1, R2, R, RI1, RI2, RI, jstar
            pending_count: nombre de contingències encara no calculades
    """
    severity_by_id = {}
    pending_count = 0
    for row in rows:
        s = severity(row)
        severity_by_id[row["contingency_id"]] = s
        if s is None:
            pending_count += 1

    # Registre d'elements: unió de tots els elements que apareixen.
    all_elements = set()
    for row in rows:
        for e in parse_elements(row):
            all_elements.add(e)
    all_elements = sorted(all_elements, key=element_key)

    r1 = defaultdict(float)
    r2 = defaultdict(float)
    jstar = {}  # element -> (element_partner, producte P_j·S)

    for row in rows:
        els = parse_elements(row)
        s = severity_by_id[row["contingency_id"]]

        if row["level"] == 1:
            # N-1: un únic element.
            if len(els) == 1 and s is not None:
                r1[els[0]] = s

        elif row["level"] == 2:
            # N-2: dos elements. Cada fila (ordre) contribueix per separat
            # a la vulnerabilitat de cadascun dels dos elements.
            if len(els) != 2 or s is None:
                continue
            a, b = els

            r2[a] += LAMBDA[b[0]] * s
            r2[b] += LAMBDA[a[0]] * s

            prod_a = LAMBDA[b[0]] * s
            if a not in jstar or prod_a > jstar[a][1]:
                jstar[a] = (b, prod_a)
            prod_b = LAMBDA[a[0]] * s
            if b not in jstar or prod_b > jstar[b][1]:
                jstar[b] = (a, prod_b)

    # Normalitzacions (RI^(1), RI^(2) i RI total) pel màxim global.
    ri1 = normalize({e: r1[e] for e in all_elements})
    ri2 = normalize({e: r2[e] for e in all_elements})
    total = {e: r1[e] + r2[e] for e in all_elements}
    ri_total = normalize(total)

    results = {}
    for e in all_elements:
        partner, prod = jstar.get(e, (None, 0.0))
        results[e] = {
            "R1": r1[e],
            "R2": r2[e],
            "R": total[e],
            "RI1": ri1[e],
            "RI2": ri2[e],
            "RI": ri_total[e],
            "jstar": partner,
            "jstar_weighted": prod,
        }

    return all_elements, results, pending_count


def plot_stacked(labels, n1, n2, title, filename, out_dir):
    """
    Gràfic de barres horitzontals apilades: N-1 (sota) + N-2 (sobre).

    Els valors n1 i n2 es donen normalitzats pel màxim global, de manera que
    l'alçada total de cada barra és l'índex de risc total normalitzat RI.
    """
    # Ordena de més crític a menys (per RI total descendent).
    order = np.argsort(-(np.asarray(n1) + np.asarray(n2)))
    labels = [labels[i] for i in order]
    n1 = [n1[i] for i in order]
    n2 = [n2[i] for i in order]

    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9, max(3.0, 0.35 * len(labels))))

    ax.barh(y, n1, color="tab:blue", label="N-1")
    ax.barh(y, n2, left=n1, color="tab:orange", label="N-2")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()  # el més crític a dalt
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Índex de risc normalitzat (RI)")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    path = os.path.join(out_dir, filename)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    print(f"Plot desat: {path}")


def save_csv(elements, results, path):
    """Desa els índexs de risc per element en un CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "type", "index", "label",
            "R1", "R2", "R",
            "RI1", "RI2", "RI",
            "jstar", "jstar_weighted",
        ])
        for e in elements:
            r = results[e]
            partner = r["jstar"]
            writer.writerow([
                e[0], e[1], element_label(e),
                f"{r['R1']:.6g}", f"{r['R2']:.6g}", f"{r['R']:.6g}",
                f"{r['RI1']:.6g}", f"{r['RI2']:.6g}", f"{r['RI']:.6g}",
                element_label(partner) if partner else "",
                f"{r['jstar_weighted']:.6g}",
            ])
    print(f"Dades desades: {path}")


def main():
    parser = argparse.ArgumentParser(description="Índex de risc de vulnerabilitat.")
    parser.add_argument("--db", type=str, default=DB_FILE,
                        help="Camí a la base de dades (per defecte config.DB_FILE)")
    parser.add_argument("--out", type=str, default=PLOTS_DIR,
                        help="Carpeta on desar plots i CSV (per defecte plots/)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    rows = load_rows(args.db)
    if not rows:
        print(f"No s'han trobat files a {args.db}")
        return

    elements, results, pending = compute_risk_index(rows)

    # Max global (per normalitzar les barres apilades correctament).
    max_total = max((results[e]["R"] for e in elements), default=0.0)

    # Agrupa per tipus.
    by_type = defaultdict(list)
    for e in elements:
        by_type[e[0]].append(e)

    for t, title, filename in [
        ("line", "Risc de vulnerabilitat — Línies", "risk_lines.png"),
        ("transformer", "Risc de vulnerabilitat — Transformadors", "risk_transformers.png"),
        ("generator", "Risc de vulnerabilitat — Generadors", "risk_generators.png"),
    ]:
        group = by_type.get(t, [])
        if not group:
            print(f"Avís: cap element de tipus '{t}'; es salta el plot {filename}.")
            continue
        labels = [element_label(e) for e in group]
        n1 = [results[e]["R1"] / max_total if max_total else 0.0 for e in group]
        n2 = [results[e]["R2"] / max_total if max_total else 0.0 for e in group]
        plot_stacked(labels, n1, n2, title, filename, args.out)

    # Plot grupal (tots els elements).
    labels = [element_label(e) for e in elements]
    n1 = [results[e]["R1"] / max_total if max_total else 0.0 for e in elements]
    n2 = [results[e]["R2"] / max_total if max_total else 0.0 for e in elements]
    plot_stacked(labels, n1, n2, "Risc de vulnerabilitat — Tots els elements",
                 "risk_group.png", args.out)

    # CSV amb les dades.
    save_csv(elements, results, os.path.join(args.out, "risk_index.csv"))

    # Resum per consola.
    n_lines = len(by_type.get("line", []))
    n_trafos = len(by_type.get("transformer", []))
    n_gens = len(by_type.get("generator", []))
    print("-" * 60)
    print(f"Elements: {len(elements)}  (línies={n_lines}, "
          f"transformadors={n_trafos}, generadors={n_gens})")
    if pending:
        print(f"AVÍS: {pending} contingències encara 'pending' (excloses del càlcul).")
        print("      Torna a executar 3.postprocess.py quan acabi el processament.")
    print("Top-5 elements més crítics (per RI total):")
    top = sorted(elements, key=lambda e: results[e]["RI"], reverse=True)[:5]
    for e in top:
        r = results[e]
        partner = element_label(r["jstar"]) if r["jstar"] else "-"
        print(f"  {element_label(e):>8}  RI={r['RI']:.3f}  "
              f"(N-1={r['R1']:.1f}, N-2={r['R2']:.3f})  j*={partner}")
    print("-" * 60)


if __name__ == "__main__":
    main()
