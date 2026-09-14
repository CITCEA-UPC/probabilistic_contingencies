from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

# Rutes als submòduls
VERAGRID_SRC = str(ROOT / "VeraGrid_TenSyGrid" / "src")

# Injecció automàtica a sys.path per trobar VeraGridEngine
if VERAGRID_SRC not in sys.path:
    sys.path.insert(0, VERAGRID_SRC)

TEST_1_PREPROCESS = True
DB_FILE = str(ROOT / "results.db")
TEST_2_PROCESS = False
TEST_CONTINGENCY_ID = 15

if TEST_1_PREPROCESS:
    GRID_NAME = "IEEE 9 Bus.gridcal"
    GRID_PATH = str(ROOT / "VeraGrid_TenSyGrid" / "Grids_and_profiles" / "grids" / GRID_NAME)
else:
    GRID_NAME = "IEEE118busNREL.raw"
    GRID_PATH = str(ROOT / "stability_analysis" / "stability_analysis" / "data" / "raw" / GRID_NAME)


