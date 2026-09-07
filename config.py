from pathlib import Path


ROOT = Path(__file__).resolve().parent

TEST_1_PREPROCESS = True
DB_FILE = str(ROOT / "results.db")
TEST_2_PROCESS = False
TEST_CONTINGENCY_ID = 15

if TEST_1_PREPROCESS:
    GRID_NAME = "IEEE 9 Bus.gridcal"
    GRID_PATH = str(ROOT / "VeraGrid" / "Grids_and_profiles" / "grids" / GRID_NAME)
else:
    GRID_NAME = "IEEE118busNREL.raw"
    GRID_PATH = str(ROOT / "stability_analysis" / "stability_analysis" / "data" / "raw" / GRID_NAME)

VERAGRID_SRC = str(ROOT / "VeraGrid" / "src")
