"""Ubicacions compartides del projecte, independents del directori de treball."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"
DATABASES_DIR = OUTPUTS_DIR / "databases"
PLOTS_DIR = OUTPUTS_DIR / "plots"
