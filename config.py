from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

# Rutes als submòduls
VERAGRID_SRC = str(ROOT / "VeraGrid_TenSyGrid" / "src")

# Injecció automàtica a sys.path per trobar VeraGridEngine
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

# ---------------------------------------------------------------------------
# Xarxa a analitzar. Edita GRID_NAME (i GRID_PATH si el fitxer no és a una de
# les carpetes per defecte) per canviar de xarxa.
# ---------------------------------------------------------------------------
# GRID_NAME = "IEEE 9 Bus.gridcal"
# GRID_PATH = str(ROOT / "VeraGrid_TenSyGrid" / "Grids_and_profiles" / "grids" / GRID_NAME)

# Exemple per a l'IEEE 118: descomenta aquestes dues línies i comenta les de dalt.
GRID_NAME = "IEEE118busNREL.raw"
GRID_PATH = str(ROOT / "stability_analysis" / "stability_analysis" / "data" / "raw" / GRID_NAME)

# Si vols reiniciar la base de dades des de zero (esborra la .db existent
# i torna a generar totes les contingències), descomenta la línia següent:
# CLEAR_DB_ON_START = True

# El nom de la base de dades es deriva del nom de fitxer del grid:
# p. ex. "IEEE 9 Bus.gridcal" → "results_IEEE_9_Bus.db"
_grid_stem = Path(GRID_PATH).stem.replace(" ", "_")
DB_FILE = str(ROOT / f"results_{_grid_stem}.db")
