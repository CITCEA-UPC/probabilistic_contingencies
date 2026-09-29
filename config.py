from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

# Submòdul del motor VeraGrid (repo CITCEA-UPC/VeraGrid_TenSyGrid).
VERAGRID_ROOT = ROOT / "VeraGrid_TenSyGrid"
VERAGRID_SRC = str(VERAGRID_ROOT / "src")

if not (VERAGRID_ROOT / "src" / "VeraGridEngine").is_dir():
    raise FileNotFoundError(
        "No s'ha trobat el submòdul VeraGrid_TenSyGrid/src/VeraGridEngine. "
        "Inicialitza'l amb: git submodule update --init --recursive"
    )

# Injecció automàtica a sys.path per trobar VeraGridEngine
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

# ---------------------------------------------------------------------------
# Xarxa a analitzar. Edita GRID_NAME (i GRID_PATH si el fitxer no és a una de
# les carpetes per defecte) per canviar de xarxa.
# ---------------------------------------------------------------------------
GRID_NAME = "IEEE 9 Bus.gridcal"
GRID_PATH = str(VERAGRID_ROOT / "Grids_and_profiles" / "grids" / GRID_NAME)

# Exemple per a l'IEEE 118: descomenta aquestes dues línies i comenta les de dalt.
# GRID_NAME = "IEEE118busNREL.raw"
# GRID_PATH = str(ROOT / "stability_analysis" / "stability_analysis" / "data" / "raw" / GRID_NAME)

# Si vols reiniciar la base de dades des de zero (esborra la .db existent
# i torna a generar totes les contingències), descomenta la línia següent:
CLEAR_DB_ON_START = True

# El nom de la base de dades es deriva del nom de fitxer del grid:
# p. ex. "IEEE 9 Bus.gridcal" → "results_IEEE_9_Bus.db"
_grid_stem = Path(GRID_PATH).stem.replace(" ", "_")
DB_FILE = str(ROOT / f"results_{_grid_stem}.db")
