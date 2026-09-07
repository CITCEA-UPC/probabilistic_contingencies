#!/usr/bin/env bash

# Llança el pipeline al node local amb: ./run_slurm.sh
# El preprocess s'executa localment; només el process s'envia als nodes de càlcul.
#SBATCH --job-name=contingencies
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=1

unset PYTHONPATH

module load python/3.12.1

set -euo pipefail

# Directori del repositori i intèrpret Python del projecte.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${SCRIPT_DIR}/.venv/bin/python}"

cd "$SCRIPT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

# Les tasques de l'array només processen la contingència assignada per Slurm.
if [[ "${PIPELINE_STAGE:-preprocess}" == "process" ]]; then
    if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
        echo "SLURM_ARRAY_TASK_ID is not set for the process stage." >&2
        exit 1
    fi

    exec "$PYTHON_BIN" 2.process.py "$SLURM_ARRAY_TASK_ID"
fi

# El job principal genera totes les contingències abans de crear l'array.
echo "Running preprocess"
"$PYTHON_BIN" 1.preprocess.py

# Consulta quantes files ha creat el preprocess per definir el rang de l'array.
contingency_count=$("$PYTHON_BIN" -c '
import sqlite3
import config

with sqlite3.connect(config.DB_FILE) as connection:
    print(connection.execute(
        "SELECT COUNT(*) FROM contingency_results"
    ).fetchone()[0])
')

# No enviïs un array buit si el preprocess no ha generat cap contingència.
if [[ "$contingency_count" -lt 1 ]]; then
    echo "No contingencies were generated." >&2
    exit 1
fi

# El preprocess ja ha acabat localment abans d'enviar l'array a Slurm.
echo "Submitting process array for $contingency_count contingencies"
sbatch \
    --array="1-${contingency_count}" \
    --export="ALL,PIPELINE_STAGE=process" \
    "$SCRIPT_DIR/run_slurm.sh"