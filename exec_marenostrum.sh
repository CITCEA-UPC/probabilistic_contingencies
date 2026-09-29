#!/usr/bin/env bash

# Llança el pipeline al node local amb: ./exec_marenostrum.sh
# El preprocess s'executa localment; només el process s'envia als nodes de càlcul.
#SBATCH --job-name=contingencies
#SBATCH --output=slurm-%x-%A_%a.out
#SBATCH --error=slurm-%x-%A_%a.err
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --account=bsc15
#SBATCH --qos=gp_bsccs
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=agracia@bsc.es


module load hdf5
module load python/3.12.1

unset PYTHONHOME
unset PYTHONPATH

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

    # L'array està particionat en trossos; OFFSET trasllada l'índex de tasca
    # (0-based) a l'identificador real de la contingència (1-based a la BD).
    OFFSET="${OFFSET:-0}"
    contingency_id=$(( SLURM_ARRAY_TASK_ID + OFFSET + 1 ))

    exec "$PYTHON_BIN" 2.process.py "$contingency_id"
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
# Slurm limita la mida d'un array (MaxArraySize); amb milers de contingències
# cal partir-lo en trossos. Cada tros és un array 0-based i OFFSET trasllada
# l'índex de tasca a l'ID real de la contingència.
CHUNK_SIZE="${CHUNK_SIZE:-}"
if [[ -z "$CHUNK_SIZE" ]]; then
    max_array=$(scontrol show config 2>/dev/null \
        | sed -n 's/^[[:space:]]*MaxArraySize[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' \
        | head -n1) || true
    CHUNK_SIZE="${max_array:-1000}"
    if (( CHUNK_SIZE < 1 )); then
        CHUNK_SIZE=1000
    fi
fi

MAX_CONCURRENT="${MAX_CONCURRENT:-300}"

echo "Submitting process array for $contingency_count contingencies (chunks of $CHUNK_SIZE)"
for (( offset = 0; offset < contingency_count; offset += CHUNK_SIZE )); do
    end=$(( offset + CHUNK_SIZE ))
    if (( end > contingency_count )); then
        end=$contingency_count
    fi
    n=$(( end - offset ))          # nombre de tasques d'aquest tros
    last_index=$(( n - 1 ))        # índex 0-based de l'última tasca

    sbatch \
        --array="0-${last_index}%${MAX_CONCURRENT}" \
        --export="ALL,PIPELINE_STAGE=process,OFFSET=${offset}" \
        "$SCRIPT_DIR/exec_marenostrum.sh"
done