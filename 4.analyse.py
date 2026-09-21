"""
Script per analitzar els resultats d'una contingència de la base de dades.

Carrega la fila de la contingència (definició, classificació i autovalors de
Floquet desats per 2.process.py) i:
  - Imprimeix un resum de la contingència i del seu estat.
  - Imprimeix una taula amb els modes (autovalor, freqüència i amortiment),
    ordenada del menys amortit al més amortit.
  - Mostra els autovalors amb la representació habitual d'estabilitat
    small-signal (matplotlib), en dos panells: el pla s amb la meitat dreta
    (Re(lambda) > 0, inestable) ombrejada en vermell i l'esquerra (estable)
    en verd, i un panell d'amortiment (zeta) vs freqüència.

Els autovalors només existeixen per a les contingències amb status='ok'
(les classificades com a 'isolated_buses', 'pf*_not_converged', etc. no
arriben a executar l'anàlisi small-signal).

Ús:
    python 4.analyse.py <contingency_id>
    python 4.analyse.py <contingency_id> --save modes.png  # desa el gràfic
    python 4.analyse.py <contingency_id> --no-show         # sense finestra
"""

import argparse
import json
import sqlite3
import sys

import numpy as np
import matplotlib.pyplot as plt

import config

DB_FILE = config.DB_FILE


def load_result_from_db(contingency_id):
    """
    Carrega la fila de resultats d'una contingència pel seu ID.

    Args:
        contingency_id: ID primari de la contingència.

    Returns:
        dict: Fila de la taula contingency_results com a diccionari.

    Raises:
        FileNotFoundError: Si no existeix la base de dades.
        ValueError: Si no es troba la contingència amb l'ID especificat.
    """
    try:
        with sqlite3.connect(DB_FILE) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM contingency_results WHERE contingency_id = ?",
                (contingency_id,),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        raise FileNotFoundError(f"Database error ({DB_FILE}): {exc}") from exc

    if row is None:
        raise ValueError(f"Contingency not found: {contingency_id}")

    return dict(row)


def parse_eigenvalues(raw):
    """
    Converteix la columna `eigenvalues` (JSON de parells [real, imag]) en un
    vector complex de numpy.

    Args:
        raw: Contingut de la columna eigenvalues (cadena JSON o None).

    Returns:
        numpy.ndarray | None: Vector complex amb els autovalors, o None si la
        columna és buida (contingència no calculada o sense anàlisi modal).
    """
    if not raw:
        return None

    pairs = json.loads(raw)
    if not pairs:
        return None

    return np.array([complex(re, im) for re, im in pairs])


def print_summary(row, eigenvalues):
    """
    Imprimeix el resum de la contingència i la taula de modes.

    La taula s'ordena per part real decreixent (el mode menys amortit / més
    proper a la inestabilitat primer). La freqüència i l'amortiment es
    calculen amb les mateixes fórmules que el motor:
    f = |Im(lambda)| / (2*pi) i zeta = -Re(lambda) / |lambda|.

    Args:
        row: Fila de la base de dades com a diccionari.
        eigenvalues: Vector complex d'autovalors (o None).
    """
    print("=" * 78)
    print(f"Contingency {row['contingency_id']}  -  {row['grid_name']}")
    print(f"  lines={row['lines']}  generators={row['generators']}  "
          f"transformers={row['transformers']}  level={row['level']}")
    print(f"  status={row['status']}  stable={bool(row['stable'])}  "
          f"errors={bool(row['errors'])}  islands={bool(row['islands'])}")
    print(f"  powerflow_converged={bool(row['powerflow_converged'])}  "
          f"n_islands={row['n_islands']}  isolated_buses={row['isolated_buses']}")
    if row["error_message"]:
        print(f"  error_message: {row['error_message']}")
    print("=" * 78)

    if eigenvalues is None:
        print("No eigenvalues stored for this contingency "
              f"(status='{row['status']}').")
        print("Only contingencies processed with status='ok' have modal data.")
        return

    alpha = eigenvalues.real
    beta = eigenvalues.imag
    frequencies = np.abs(beta) / (2.0 * np.pi)
    damping = -alpha / np.sqrt(alpha ** 2 + beta ** 2 + 1e-15)

    order = np.argsort(-alpha)  # menys amortit (re més gran) primer
    print(f"{'mode':>4}  {'re(lambda)':>13}  {'im(lambda)':>13}  "
          f"{'f [Hz]':>9}  {'zeta':>9}  stable")
    for index in order:
        lam = eigenvalues[index]
        print(f"{index:>4d}  {lam.real:>13.6e}  {lam.imag:>13.6e}  "
              f"{frequencies[index]:>9.4f}  {damping[index]:>9.4f}  "
              f"{'yes' if lam.real <= 0.0 else 'NO'}")

    unstable = int(np.sum(alpha > 0.0))
    print("-" * 78)
    print(f"{len(eigenvalues)} modes stored, {unstable} unstable "
          f"(Re(lambda) > 0).")


def plot_eigenvalues(row, eigenvalues, save_path=None, show=True):
    """
    Dibuixa els autovalors amb la representació habitual d'estabilitat
    small-signal, en dos panells:

      1. Pla s: part real vs part imaginària de lambda. La meitat dreta del
         pla (Re(lambda) > 0) és la regió INESTABLE i va ombrejada en vermell;
         la meitat esquerra (Re(lambda) <= 0) és l'ESTABLE, en verd. Els
         modes estables es pinten com a punts blaus i els inestables com a
         as vermelles; l'eix imaginari marca la frontera d'estabilitat.
      2. Amortiment vs freqüencia: zeta = -Re(lambda)/|lambda| contra
         f = |Im(lambda)|/(2*pi). zeta < 0 equival a mode inestable.

    Cada punt s'anota amb el seu índex de mode, coherent amb la taula
    impresa per `print_summary`.

    Args:
        row: Fila de la base de dades com a diccionari (per al títol).
        eigenvalues: Vector complex d'autovalors.
        save_path: Camí opcional on desar el gràfic com a PNG.
        show: Si s'ha de mostrar la finestra interactiva (plt.show()).
    """
    alpha = eigenvalues.real
    beta = eigenvalues.imag
    stable = alpha <= 0.0
    frequencies = np.abs(beta) / (2.0 * np.pi)
    damping = -alpha / np.sqrt(alpha ** 2 + beta ** 2 + 1e-15)

    # Marges per poder ombrejar les regions estable/inestable del pla s.
    x_pad = 0.15 * max(alpha.max() - alpha.min(), 1e-9)
    y_pad = 0.15 * max(beta.max() - beta.min(), 1e-9)
    x_min, x_max = alpha.min() - x_pad, max(alpha.max() + x_pad, x_pad)
    y_min, y_max = beta.min() - y_pad, beta.max() + y_pad

    figure, (axis_s, axis_z) = plt.subplots(
        1, 2, figsize=(14.0, 6.2), constrained_layout=True
    )

    # --- Panell 1: pla s (meitat dreta = inestable) ---
    axis_s.axvspan(0.0, x_max, color="tab:red", alpha=0.10, zorder=0)
    axis_s.axvspan(x_min, 0.0, color="tab:green", alpha=0.08, zorder=0)
    axis_s.axvline(0.0, color="black", linestyle="--", linewidth=1.0,
                   label="stability boundary")
    axis_s.scatter(alpha[stable], beta[stable], s=55, label="stable")
    axis_s.scatter(alpha[~stable], beta[~stable], s=65, marker="x",
                   color="red", label="unstable")
    for index, lam in enumerate(eigenvalues):
        axis_s.annotate(str(index), (lam.real, lam.imag),
                        xytext=(4, 4), textcoords="offset points", fontsize=8)
    axis_s.text(x_max, y_max, "UNSTABLE  Re($\\lambda$) > 0", ha="right",
                va="top", color="tab:red", fontweight="bold")
    axis_s.text(x_min, y_max, "STABLE  Re($\\lambda$) $\\leq$ 0", ha="left",
                va="top", color="tab:green", fontweight="bold")
    axis_s.set_xlim(x_min, x_max)
    axis_s.set_ylim(y_min, y_max)
    axis_s.set_xlabel("Re($\\lambda$) [1/s]")
    axis_s.set_ylabel("Im($\\lambda$) [rad/s]")
    axis_s.set_title("s-plane (Floquet exponents)")
    axis_s.grid(alpha=0.3)
    axis_s.legend(loc="lower left")

    # --- Panell 2: amortiment vs freqüència ---
    z_min = min(damping.min(), 0.0) - 0.1
    z_max = max(damping.max(), 0.0) + 0.1
    axis_z.axhspan(z_min, 0.0, color="tab:red", alpha=0.10, zorder=0)
    axis_z.axhspan(0.0, z_max, color="tab:green", alpha=0.08, zorder=0)
    axis_z.axhline(0.0, color="black", linestyle="--", linewidth=1.0)
    axis_z.scatter(frequencies[stable], damping[stable], s=55, label="stable")
    axis_z.scatter(frequencies[~stable], damping[~stable], s=65, marker="x",
                   color="red", label="unstable")
    for index in range(len(eigenvalues)):
        axis_z.annotate(str(index), (frequencies[index], damping[index]),
                        xytext=(4, 4), textcoords="offset points", fontsize=8)
    axis_z.set_ylim(z_min, z_max)
    axis_z.set_xlabel("f [Hz]")
    axis_z.set_ylabel("$\\zeta$ (damping ratio)")
    axis_z.set_title("Damping vs frequency")
    axis_z.grid(alpha=0.3)
    axis_z.legend(loc="lower left")

    figure.suptitle(
        f"Contingency {row['contingency_id']} - {row['grid_name']}  |  "
        f"lines={row['lines']} gens={row['generators']} "
        f"trafos={row['transformers']}  |  status={row['status']}, "
        f"stable={bool(row['stable'])}"
    )

    if save_path:
        figure.savefig(save_path, dpi=180)
        print(f"Plot saved to: {save_path}")

    if show:
        plt.show()
    else:
        plt.close(figure)


def main():
    parser = argparse.ArgumentParser(
        description="Show the stored eigenvalues of one contingency (matplotlib plot + table)."
    )
    parser.add_argument(
        "contingency_id",
        type=int,
        help="Primary key of the contingency to analyse",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional path to save the plot as PNG",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open the interactive matplotlib window",
    )
    args = parser.parse_args()

    row = load_result_from_db(args.contingency_id)
    eigenvalues = parse_eigenvalues(row.get("eigenvalues"))

    print_summary(row, eigenvalues)

    if eigenvalues is not None:
        plot_eigenvalues(
            row,
            eigenvalues,
            save_path=args.save,
            show=not args.no_show,
        )
    elif args.save:
        print("Nothing to plot; --save ignored.", file=sys.stderr)


if __name__ == "__main__":
    main()
