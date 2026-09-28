"""
Script per analitzar els resultats d'una contingència de la base de dades.

Carrega la fila de la contingència (definició, classificació i autovalors de
Floquet desats per 2.process.py) i:
  - Imprimeix un resum de la contingència i del seu estat.
  - Imprimeix una taula amb els modes (autovalor, freqüència i amortiment),
    ordenada del menys amortit al més amortit, amb la classificació
    estable / marginal / inestable de cada mode.
  - Mostra els autovalors amb la representació habitual d'estabilitat
    small-signal (matplotlib): el pla s amb la meitat dreta (Re(lambda) > 0,
    inestable) ombrejada en vermell, l'esquerra (estable) en verd i la franja
    marginal al voltant de l'eix imaginari en taronja.

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

# Tolerància de la franja marginal al voltant de l'eix imaginari. El càlcul de
# Floquet (Arnoldi amb tol=1e-8 sobre un cicle límit integrat numèricament) no
# pot resoldre els modes propis de Re(lambda) = 0 amb precisió absoluta: entre
# execucions de la mateixa contingència aquests modes surten amb Re(lambda)
# entre ~1e-14 i ~1e-5, amb signe aleatori. Sense tolerància es classificarien
# com a inestables.
#
# La tolerància és relativa a l'escala de l'espectre (els modes físics d'una
# xarxa a 60 Hz són de l'ordre de 0.1-1 1/s), amb un terra absolut per a
# espectres degenerats. Amb MARGINAL_REL_TOL = 1e-3, un mode marginal té
# |zeta| <= 1e-3, és a dir, pràcticament no amortit.
MARGINAL_REL_TOL = 1e-3
MARGINAL_ABS_TOL = 1e-9

CLASS_STABLE = "stable"
CLASS_MARGINAL = "marginal"
CLASS_UNSTABLE = "UNSTABLE"


def marginal_tolerance(eigenvalues):
    """
    Calcula la tolerància efectiva de la franja marginal per a un espectre.

    Args:
        eigenvalues: Vector complex d'autovalors.

    Returns:
        float: max(MARGINAL_REL_TOL * max|lambda|, MARGINAL_ABS_TOL).
    """
    values = np.asarray(eigenvalues)
    scale = float(np.abs(values).max()) if values.size else 0.0

    return max(MARGINAL_REL_TOL * scale, MARGINAL_ABS_TOL)


def classify_modes(eigenvalues):
    """
    Classifica cada mode com a estable, marginal o inestable.

    Criteri, amb tol = `marginal_tolerance` (mateix per a la taula i el gràfic):
      - inestable: Re(lambda) >  tol
      - marginal:  |Re(lambda)| <= tol  (pràcticament sobre l'eix imaginari;
                   el signe de la part real és soroll numèric)
      - estable:   Re(lambda) < -tol

    Args:
        eigenvalues: Vector complex d'autovalors.

    Returns:
        numpy.ndarray: Vector de cadenes amb la classe de cada mode.
    """
    tol = marginal_tolerance(eigenvalues)
    alpha = np.asarray(eigenvalues).real
    classes = np.full(alpha.shape, CLASS_STABLE, dtype=object)
    classes[np.abs(alpha) <= tol] = CLASS_MARGINAL
    classes[alpha > tol] = CLASS_UNSTABLE

    return classes


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
    f = |Im(lambda)| / (2*pi) i zeta = -Re(lambda) / |lambda|. La darrera
    columna classifica cada mode amb `classify_modes`.

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
    classes = classify_modes(eigenvalues)

    order = np.argsort(-alpha)  # menys amortit (re més gran) primer
    print(f"{'mode':>4}  {'re(lambda)':>13}  {'im(lambda)':>13}  "
          f"{'f [Hz]':>9}  {'zeta':>9}  class")
    for index in order:
        lam = eigenvalues[index]
        print(f"{index:>4d}  {lam.real:>13.6e}  {lam.imag:>13.6e}  "
              f"{frequencies[index]:>9.4f}  {damping[index]:>9.4f}  "
              f"{classes[index]}")

    n_unstable = int(np.sum(classes == CLASS_UNSTABLE))
    n_marginal = int(np.sum(classes == CLASS_MARGINAL))
    n_stable = int(np.sum(classes == CLASS_STABLE))
    print("-" * 78)
    print(f"{len(eigenvalues)} modes stored: {n_stable} stable, "
          f"{n_marginal} marginal, {n_unstable} unstable  "
          f"(|Re(lambda)| <= {marginal_tolerance(eigenvalues):.3e} = marginal)")


def plot_eigenvalues(row, eigenvalues, save_path=None, show=True):
    """
    Dibuixa els autovalors al pla s amb la representació habitual d'estabilitat
    small-signal, diferenciant les tres classes de `classify_modes` (amb
    tol = `marginal_tolerance`):

      - ESTABLE (Re(lambda) < -tol): meitat esquerra ombrejada en verd,
        punts blaus.
      - MARGINAL (|Re(lambda)| <= tol): franja al voltant de l'eix imaginari
        ombrejada en taronja, quadrats taronja. Són modes pràcticament no
        amortits; el signe de la part real és soroll numèric del càlcul de
        Floquet, per això no es classifiquen com a inestables.
      - INESTABLE (Re(lambda) > tol): meitat dreta ombrejada en vermell,
        as vermelles.

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
    classes = classify_modes(eigenvalues)
    tol = marginal_tolerance(eigenvalues)

    # Marges per poder ombrejar les regions del pla s.
    x_pad = 0.15 * max(alpha.max() - alpha.min(), 1e-9)
    y_pad = 0.15 * max(beta.max() - beta.min(), 1e-9)
    x_min, x_max = alpha.min() - x_pad, max(alpha.max() + x_pad, x_pad)
    y_min, y_max = beta.min() - y_pad, beta.max() + y_pad

    figure, axis_s = plt.subplots(figsize=(8.6, 6.6), constrained_layout=True)

    # Regions de fons: estable | marginal | inestable.
    axis_s.axvspan(x_min, -tol, color="tab:green", alpha=0.08, zorder=0)
    axis_s.axvspan(-tol, tol, color="tab:orange", alpha=0.20, zorder=0)
    axis_s.axvspan(tol, x_max, color="tab:red", alpha=0.10, zorder=0)
    axis_s.axvline(0.0, color="black", linestyle="--", linewidth=1.0,
                   label="stability boundary")

    mask_stable = classes == CLASS_STABLE
    mask_marginal = classes == CLASS_MARGINAL
    mask_unstable = classes == CLASS_UNSTABLE

    axis_s.scatter(alpha[mask_stable], beta[mask_stable], s=55, color="tab:blue",
                   label=f"stable ({int(mask_stable.sum())})")
    axis_s.scatter(alpha[mask_marginal], beta[mask_marginal], s=60,
                   marker="s", color="tab:orange", edgecolors="black",
                   linewidths=0.5, label=f"marginal ({int(mask_marginal.sum())})")
    axis_s.scatter(alpha[mask_unstable], beta[mask_unstable], s=65, marker="x",
                   color="red", label=f"unstable ({int(mask_unstable.sum())})")

    for index, lam in enumerate(eigenvalues):
        axis_s.annotate(str(index), (lam.real, lam.imag),
                        xytext=(4, 4), textcoords="offset points", fontsize=8)

    axis_s.text(x_max, y_max, "UNSTABLE  Re($\\lambda$) > 0", ha="right",
                va="top", color="tab:red", fontweight="bold")
    axis_s.text(x_min, y_max, "STABLE  Re($\\lambda$) < 0", ha="left",
                va="top", color="tab:green", fontweight="bold")
    axis_s.set_xlim(x_min, x_max)
    axis_s.set_ylim(y_min, y_max)
    axis_s.set_xlabel("Re($\\lambda$) [1/s]")
    axis_s.set_ylabel("Im($\\lambda$) [rad/s]")
    axis_s.set_title("s-plane (Floquet exponents)")
    axis_s.grid(alpha=0.3)
    axis_s.legend(loc="lower left")

    figure.suptitle(
        f"Contingency {row['contingency_id']} - {row['grid_name']}  |  "
        f"lines={row['lines']} gens={row['generators']} "
        f"trafos={row['transformers']}\n"
        f"status={row['status']}, stable={bool(row['stable'])}  |  "
        f"marginal band |Re($\\lambda$)| $\\leq$ {tol:.2e}",
        fontsize=10,
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
