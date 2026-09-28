#!/usr/bin/env bash

# Llança el pipeline en local, sense Slurm: preprocess + process per a cada contingència.

set -euo pipefail

# Directori del repositori i intèrpret Python del projecte.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${SCRIPT_DIR}/.venv/bin/python}"

cd "$SCRIPT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

start_time=$(date +%s)

echo "Running preprocess"
"$PYTHON_BIN" 1.preprocess.py

# Consulta quantes files ha creat el preprocess per definir el rang a processar.
contingency_count=$("$PYTHON_BIN" -c '
import sqlite3
import config

with sqlite3.connect(config.DB_FILE) as connection:
    print(connection.execute(
        "SELECT COUNT(*) FROM contingency_results"
    ).fetchone()[0])
')

if [[ "$contingency_count" -lt 1 ]]; then
    echo "No contingencies were generated." >&2
    exit 1
fi

echo "Processing $contingency_count contingencies locally"
# Per defecte, fem servir el 80% dels cores disponibles (mínim 1).
job_slots="${JOB_SLOTS:-$(( $(nproc) * 80 / 100 ))}"
job_slots="${job_slots:-1}"
if [[ "$job_slots" -lt 1 ]]; then
    job_slots=1
fi
echo "Using $job_slots parallel workers"
seq 1 "$contingency_count" | xargs -I{} -P "$job_slots" \
    "$PYTHON_BIN" 2.process.py {}

end_time=$(date +%s)
elapsed=$(( end_time - start_time ))
printf 'Total elapsed time: %02d:%02d:%02d\n' "$(( elapsed / 3600 ))" "$(( (elapsed % 3600) / 60 ))" "$(( elapsed % 60 ))"
