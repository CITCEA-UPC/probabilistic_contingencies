"""Vulnerabilitat amb diagnòstics desconeguts i límits de risc brut.

Ús: python risk_analysis.py [--db results.db] [--out carpeta]
     python risk_analysis.py --n2-counting rows  # comparació per files

Per defecte, cada conjunt de desconnexions N−2 es compta una sola vegada.
Els límits no són intervals de confiança: assignen severitat 0/1 als casos
sense diagnòstic. No es normalitzen per màxims globals diferents.
"""

import argparse
import ast
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from contingencies.result_diagnostics import STABLE_MAX_REAL_PART, classify

from contingencies.paths import PLOTS_DIR
LAMBDA = {"line": 0.05, "transformer": 0.02, "generator": 0.10}
TYPE_ORDER = {"line": 0, "transformer": 1, "generator": 2}
TYPE_LABEL = {"line": "Line", "transformer": "Trafo", "generator": "Gen"}


def element_key(element):
    return TYPE_ORDER[element[0]], element[1]


def element_label(element):
    return f"{TYPE_LABEL[element[0]]} {element[1]}"


def parse_elements(row):
    elements = []
    for column, kind in (("lines", "line"), ("generators", "generator"),
                         ("transformers", "transformer")):
        ids = ast.literal_eval(row[column])
        if not isinstance(ids, list) or any(type(i) is not int or i < 0 for i in ids):
            raise ValueError(f"IDs invàlids: contingència {row['contingency_id']}, {column}")
        elements.extend((kind, i) for i in ids)
    if row["level"] not in (1, 2) or len(elements) != row["level"] or len(set(elements)) != len(elements):
        raise ValueError(f"Definició invàlida: contingència {row['contingency_id']}")
    return tuple(sorted(elements, key=element_key))


def load_rows(db_file):
    """Obre només en lectura: un camí erroni no crea una BD buida."""
    with sqlite3.connect(Path(db_file).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM contingency_results ORDER BY contingency_id")]


def merge_scenario(elements, rows):
    diagnoses = [classify(row) for row in rows]
    known = {diagnosis for diagnosis, _ in diagnoses if diagnosis != "unknown"}
    if len(known) > 1:
        diagnosis, reason = "unknown", "conflicting_results"
    elif known:
        diagnosis = next(iter(known))
        reason = "+".join(sorted({r for d, r in diagnoses if d == diagnosis}))
    else:
        diagnosis = "unknown"
        reason = "+".join(sorted({r for _, r in diagnoses})) or "missing_scenario"
    return {"elements": elements, "level": len(elements), "diagnosis": diagnosis,
            "reason": reason, "source_ids": [row["contingency_id"] for row in rows]}


def prepare_scenarios(rows, n2_counting="unique"):
    """Agrupa duplicats i inclou com a desconegudes les combinacions absents.

    L'univers d'elements és el que apareix a la BD. No es poden detectar
    dispositius que no apareguin en cap definició de contingència.
    """
    if n2_counting not in ("unique", "rows"):
        raise ValueError("n2_counting ha de ser unique o rows")
    grids = {(row.get("grid_name"), row.get("grid_path")) for row in rows}
    if len(grids) > 1:
        raise ValueError("La BD conté diverses xarxes; analitza-les per separat.")
    groups = defaultdict(list)
    for row in rows:
        groups[parse_elements(row)].append(row)
    elements = sorted({e for group in groups for e in group}, key=element_key)
    scenarios = []
    for i, a in enumerate(elements):
        scenarios.append(merge_scenario((a,), groups.get((a,), [])))
        for b in elements[i + 1:]:
            pair = (a, b)
            members = groups.get(pair, [])
            if n2_counting == "unique":
                scenarios.append(merge_scenario(pair, members))
            else:
                # Mode històric: cada fila N−2 contribueix per separat.
                scenarios.extend(merge_scenario(pair, [row]) for row in members)
                scenarios.extend(merge_scenario(pair, []) for _ in range(max(0, 2 - len(members))))
    return elements, scenarios


def compute_risk_index(rows, n2_counting="unique"):
    elements, scenarios = prepare_scenarios(rows, n2_counting)
    results = {e: {"R1_lower": 0.0, "R1_upper": 0.0, "R2_lower": 0.0, "R2_upper": 0.0,
                   "n1_total": 0, "n1_known": 0, "n2_total": 0, "n2_known": 0,
                   "weight_total": 0.0, "weight_known": 0.0,
                   "jstar_lower": None, "jstar_upper": None,
                   "jstar_lower_weight": 0.0, "jstar_upper_weight": 0.0}
               for e in elements}
    for scenario in scenarios:
        els = scenario["elements"]
        level = scenario["level"]
        diagnosis = scenario["diagnosis"]
        lower = int(diagnosis == "failure")
        upper = int(diagnosis != "stable")
        known = diagnosis != "unknown"
        for e in els:
            r = results[e]
            partner = next((other for other in els if other != e), None)
            weight = 1.0 if level == 1 else LAMBDA[partner[0]]
            r[f"R{level}_lower"] += weight * lower
            r[f"R{level}_upper"] += weight * upper
            r[f"n{level}_total"] += 1
            r[f"n{level}_known"] += int(known)
            r["weight_total"] += weight
            r["weight_known"] += weight * known
            if level == 2:
                for bound, severity in (("lower", lower), ("upper", upper)):
                    contribution = weight * severity
                    if contribution > r[f"jstar_{bound}_weight"]:
                        r[f"jstar_{bound}"] = partner
                        r[f"jstar_{bound}_weight"] = contribution
    for r in results.values():
        r["R_lower"] = r["R1_lower"] + r["R2_lower"]
        r["R_upper"] = r["R1_upper"] + r["R2_upper"]
        r["total"] = r["n1_total"] + r["n2_total"]
        r["known"] = r["n1_known"] + r["n2_known"]
        r["unknown"] = r["total"] - r["known"]
        r["coverage"] = r["known"] / r["total"]
        r["coverage_n1"] = r["n1_known"] / r["n1_total"]
        r["coverage_n2"] = r["n2_known"] / r["n2_total"] if r["n2_total"] else None
        r["weighted_coverage"] = r["weight_known"] / r["weight_total"]
    return elements, results, scenarios


def save_csv(elements, results, path):
    columns = list(next(iter(results.values()))) if results else []
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "index", "label", *columns])
        writer.writeheader()
        for e in elements:
            row = dict(results[e], type=e[0], index=e[1], label=element_label(e))
            for field in ("jstar_lower", "jstar_upper"):
                row[field] = element_label(row[field]) if row[field] else ""
            writer.writerow(row)


def plot_risk(elements, results, title, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(elements, key=lambda e: (-results[e]["R_lower"], -results[e]["R_upper"], element_key(e)))
    y = list(range(len(ordered)))
    lower1 = [results[e]["R1_lower"] for e in ordered]
    lower2 = [results[e]["R2_lower"] for e in ordered]
    lower = [results[e]["R_lower"] for e in ordered]
    gap = [results[e]["R_upper"] - results[e]["R_lower"] for e in ordered]
    fig, ax = plt.subplots(figsize=(11, max(3.5, 0.4 * len(ordered))))
    ax.barh(y, lower1, label="N−1: contribució confirmada", color="tab:blue")
    ax.barh(y, lower2, left=lower1, label="N−2: contribució confirmada", color="tab:orange")
    ax.barh(y, gap, left=lower, facecolor="none", edgecolor="gray", hatch="///",
            label="Contribució possible dels desconeguts")
    ax.set_yticks(y, [f"{element_label(e)} ({results[e]['coverage']:.0%})" for e in ordered])
    ax.invert_yaxis()
    ax.set_xlabel("Risc brut: límit inferior + marge fins al límit superior")
    ax.set_ylabel("Element (cobertura de diagnòstic)")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=1)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run_analysis(db_file, out_dir=None, n2_counting="unique"):
    """Genera CSV, resum i gràfics de tota la BD; retorna el resum.

    Es crida al mestre després d'esperar totes les tasques. La BD s'obre
    només en lectura; els casos encara pendents es mantenen desconeguts.
    """
    db = Path(db_file).resolve()
    rows = load_rows(db)
    elements, results, scenarios = compute_risk_index(rows, n2_counting)
    if not rows:
        print(f"No s’han trobat contingències a {db}")
        return
    out = Path(out_dir) if out_dir else PLOTS_DIR / "risk_analysis" / db.stem
    out.mkdir(parents=True, exist_ok=True)
    save_csv(elements, results, out / "risk_index.csv")
    with (out / "scenarios.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["elements", "level", "diagnosis", "reason", "source_ids"])
        writer.writeheader()
        for scenario in scenarios:
            writer.writerow(dict(scenario, elements=" + ".join(map(element_label, scenario["elements"])),
                                 source_ids=json.dumps(scenario["source_ids"])))
    counts = Counter(s["diagnosis"] for s in scenarios)
    summary = {"database": str(db), "n2_counting": n2_counting, "source_rows": len(rows),
               "row_statuses": dict(Counter(row["status"] for row in rows)),
               "row_diagnoses": dict(Counter(classify(row)[0] for row in rows)),
               "assessed_cases": len(scenarios), "diagnoses": dict(counts),
               "unknown_reasons": dict(Counter(s["reason"] for s in scenarios if s["diagnosis"] == "unknown")),
               "coverage": 1 - counts["unknown"] / len(scenarios),
               "missing_cases": sum(not s["source_ids"] for s in scenarios),
               "weights": LAMBDA, "stable_max_real_part": STABLE_MAX_REAL_PART,
               "scope": "Univers d’elements observats a la BD; combinacions absents incloses com a desconegudes.",
               "duplicate_policy": "N−1 agrupades; N−2 segons n2_counting. Diagnòstics concloents contradictoris: desconegut. Un diagnòstic concloent concordant preval sobre duplicats no avaluats.",
               "interpretation": "Límits de risc brut per severitat 0/1 dels desconeguts; sense normalització ni rànquing definitiu."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for kind, filename in (("line", "risk_lines.png"), ("transformer", "risk_transformers.png"),
                           ("generator", "risk_generators.png"), (None, "risk_group.png")):
        group = [e for e in elements if kind is None or e[0] == kind]
        if group:
            plot_risk(group, results, f"Vulnerabilitat — límits i cobertura (N−2: {n2_counting})", out / filename)
    print(f"Files de la BD: {len(rows)}; casos analitzats (N−2: {n2_counting}): {len(scenarios)}")
    print(f"Fallada: {counts['failure']}; estables: {counts['stable']}; desconeguts: {counts['unknown']}")
    print(f"Cobertura global: {summary['coverage']:.1%}; casos absents: {summary['missing_cases']}")
    print("Límits de risc brut per element (sense rànquing definitiu):")
    for e in elements:
        r = results[e]
        print(f"  {element_label(e):>8}: [{r['R_lower']:.3f}, {r['R_upper']:.3f}]  cobertura={r['coverage']:.1%}")
    print(f"CSV, resum i gràfics desats a {out}")

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", help="BD de resultats (per defecte config.DB_FILE)")
    parser.add_argument("--out", help="Carpeta de sortida (per defecte outputs/plots/risk_analysis/<nom BD>)")
    parser.add_argument("--n2-counting", choices=("unique", "rows"), default="unique",
                        help="unique: una vegada per parella; rows: comptatge històric per files")
    args = parser.parse_args()
    if args.db is None:
        import config
        args.db = config.DB_FILE
    try:
        run_analysis(args.db, args.out, args.n2_counting)
    except (sqlite3.Error, ValueError, KeyError, SyntaxError, OSError) as exc:
        parser.exit(1, f"No s’ha pogut generar l’anàlisi de risc: {exc}\n")


if __name__ == "__main__":
    main()
