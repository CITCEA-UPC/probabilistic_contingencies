"""Inspecció dels modes de Floquet desats per a una contingència.

Ús:
    python modal_analysis.py 13
    python modal_analysis.py 13 --db outputs/databases/results_IEEE_9_Bus.db --no-show
    python modal_analysis.py 13 --no-show --save outputs/plots/modal_analysis/modes_13.png

Mostra només els modes calculats, no tot l'espectre del sistema. La franja
propera a l'eix usa el mateix llindar absolut que el pipeline; no certifica
que els modes siguin exactament marginals ni que el signe sigui soroll.
"""

import argparse
import math
import sqlite3
import sys
from pathlib import Path

from contingencies.result_diagnostics import STABLE_MAX_REAL_PART, classify, parse_eigenvalues

CLASS_STABLE = "stable"
CLASS_NEAR_AXIS = "near_axis"
CLASS_UNSTABLE = "unstable"


def classify_modes(eigenvalues):
    """Mode estable si Re < -tol; proper a l'eix si |Re| <= tol; inestable si Re > tol."""
    return [CLASS_UNSTABLE if z.real > STABLE_MAX_REAL_PART else
            CLASS_STABLE if z.real < -STABLE_MAX_REAL_PART else CLASS_NEAR_AXIS
            for z in eigenvalues]


def mode_metrics(eigenvalue):
    """Freqüència [Hz] i amortiment; amortiment indefinit per a lambda=0."""
    magnitude = abs(eigenvalue)
    return abs(eigenvalue.imag) / (2 * math.pi), (-eigenvalue.real / magnitude if magnitude else None)


def format_bool(value):
    return "desconegut" if value is None else str(bool(value))


def topology_description(row):
    n = row.get("n_islands")
    if n is not None:
        if n > 1:
            return f"{n} illes: fragmentació"
        if n == 1:
            return "1 illa: xarxa connectada"
        return f"{n} illes: topologia no determinada"
    if row.get("islands") == 1:
        return "fragmentació (nombre d’illes desconegut)"
    return "desconeguda"


def modal_description(eigenvalues):
    if eigenvalues is None:
        return "desconegut: no hi ha modes desats"
    if CLASS_UNSTABLE in classify_modes(eigenvalues):
        return "hi ha modes inestables segons el llindar del pipeline"
    return "cap mode calculat supera el llindar d’inestabilitat"


def load_result_from_db(contingency_id, db_file):
    """Llegeix un cas sense crear ni modificar la BD."""
    with sqlite3.connect(Path(db_file).resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM contingency_results WHERE contingency_id = ?", (contingency_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"No existeix la contingència {contingency_id}")
    return dict(row)


def print_summary(row, eigenvalues):
    diagnosis, reason = classify(row)
    print(f"Contingència {row['contingency_id']} — {row['grid_name']}")
    print(f"  lines={row['lines']} generators={row['generators']} transformers={row['transformers']} level={row['level']}")
    print(f"  status={row.get('status')} stable (BD)={format_bool(row.get('stable'))} errors={format_bool(row.get('errors'))}")
    print(f"  PF convergit={format_bool(row.get('powerflow_converged'))} OPF necessari={format_bool(row.get('opf_needed'))} OPF convergit={format_bool(row.get('opf_converged'))}")
    print(f"  Topologia: {topology_description(row)}")
    print(f"  Busos rebutjats pel filtre EMT (camp isolated_buses): {row.get('isolated_buses')}")
    print(f"  Diagnòstic per al risc: {diagnosis} ({reason})")
    print(f"  Modes: {modal_description(eigenvalues)}")
    print(f"  Llindar compartit: Re(lambda) > {STABLE_MAX_REAL_PART:g} 1/s")
    if row.get("error_message"):
        print(f"  Error desat: {row['error_message']}")
    if eigenvalues is None:
        print("No es pot concloure estabilitat modal a partir de l’absència de modes.")
        return
    print("S’inspeccionen només els modes desats; l’espectre complet no està certificat.")
    if row.get("status") != "ok" or row.get("errors"):
        print("Els modes es mostren per inspecció; l’estat del càlcul no acredita una anàlisi completa vàlida.")
    print("Modes ordenats per part real descendent (índex original conservat):")
    print(f"{'mode':>4} {'Re(lambda)':>14} {'Im(lambda)':>14} {'f [Hz]':>10} {'zeta':>10} classe")
    classes = classify_modes(eigenvalues)
    for i in sorted(range(len(eigenvalues)), key=lambda i: -eigenvalues[i].real):
        z = eigenvalues[i]
        frequency, damping = mode_metrics(z)
        damping_text = f"{damping:.5f}" if damping is not None else "indefinit"
        print(f"{i:4d} {z.real:14.6e} {z.imag:14.6e} {frequency:10.5f} {damping_text:>10} {classes[i]}")
    print(f"{len(classes)} modes: {classes.count(CLASS_STABLE)} estables, {classes.count(CLASS_NEAR_AXIS)} propers a l’eix, {classes.count(CLASS_UNSTABLE)} inestables.")
    print("La proximitat a l’eix no demostra marginalitat exacta ni soroll numèric.")


def plot_eigenvalues(row, eigenvalues, save_path=None, show=True):
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tol = STABLE_MAX_REAL_PART
    alpha = [z.real for z in eigenvalues]
    beta = [z.imag for z in eigenvalues]
    x_pad = .15 * max(max(alpha) - min(alpha), 4 * tol)
    y_pad = .15 * max(max(beta) - min(beta), 1e-6)
    x_min = min(min(alpha) - x_pad, -3 * tol)
    x_max = max(max(alpha) + x_pad, 3 * tol)
    fig, ax = plt.subplots(figsize=(9.5, 7), constrained_layout=True)
    ax.axvspan(x_min, -tol, color="tab:green", alpha=.08)
    ax.axvspan(-tol, tol, color="tab:orange", alpha=.20)
    ax.axvspan(tol, x_max, color="tab:red", alpha=.10)
    ax.axvline(0, color="black", linestyle="--", linewidth=1, label="Re(lambda) = 0")
    ax.axvline(tol, color="tab:red", linestyle=":", linewidth=1, label=f"Llindar = {tol:g} 1/s")
    classes = classify_modes(eigenvalues)
    for kind, label, marker, color in ((CLASS_STABLE, "Estables", "o", "tab:blue"),
                                       (CLASS_NEAR_AXIS, "Propers a l’eix", "s", "tab:orange"),
                                       (CLASS_UNSTABLE, "Inestables", "x", "tab:red")):
        points = [z for z, c in zip(eigenvalues, classes) if c == kind]
        ax.scatter([z.real for z in points], [z.imag for z in points], s=55,
                   marker=marker, color=color, label=f"{label} ({len(points)})")
    for i, z in enumerate(eigenvalues):
        ax.annotate(str(i), (z.real, z.imag), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(min(beta) - y_pad, max(beta) + y_pad)
    ax.set_xlabel(r"Re($\lambda$) [1/s]")
    ax.set_ylabel(r"Im($\lambda$) [rad/s]")
    ax.set_title("Exponents de Floquet desats — només els modes calculats")
    ax.grid(alpha=.3)
    ax.legend(loc="best")
    diagnosis, reason = classify(row)
    fig.suptitle(f"Contingència {row['contingency_id']} — {row['grid_name']}\n"
                 f"{topology_description(row)} | risc: {diagnosis} ({reason})\n"
                 f"Modes propers a l’eix: |Re(lambda)| ≤ {tol:g} 1/s", fontsize=10)
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180)
        print(f"Gràfic desat a {path}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("contingency_id", type=int)
    parser.add_argument("--db", help="BD de resultats (per defecte config.DB_FILE)")
    parser.add_argument("--save", help="Camí on desar el gràfic")
    parser.add_argument("--no-show", action="store_true", help="No obrir cap finestra gràfica")
    args = parser.parse_args()
    if args.db is None:
        import config
        args.db = config.DB_FILE
    try:
        row = load_result_from_db(args.contingency_id, args.db)
        eigenvalues = parse_eigenvalues(row.get("eigenvalues"))
    except (sqlite3.Error, ValueError) as exc:
        parser.exit(1, f"No s’ha pogut llegir el resultat: {exc}\n")
    print_summary(row, eigenvalues)
    if eigenvalues is not None and (args.save or not args.no_show):
        plot_eigenvalues(row, eigenvalues, args.save, not args.no_show)
    elif eigenvalues is None and args.save:
        print("No hi ha modes per dibuixar; --save no genera cap fitxer.", file=sys.stderr)


if __name__ == "__main__":
    main()
