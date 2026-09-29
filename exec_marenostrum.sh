#!/usr/bin/env bash

# Llança el pipeline al node local amb: ./exec_marenostrum.sh
# El preprocess s'executa localment; el process s'envia als nodes de càlcul
# com un conjunt PETIT de "workers" (cada un processa moltes contingències),
# per no superar el MaxSubmitJobsPerUser del QOS (cada tasca d'array compta).
#SBATCH --job-name=contingencies
#SBATCH --output=slurm_outputs/%A/slurm-%x-%A_%a.out
#SBATCH --error=slurm_outputs/%A/slurm-%x-%A_%a.err
#SBATCH --time=12:00:00
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

# Directori del repositori. Quan Slurm executa una tasca d'array en un node de
# càlcul, copia el script a l'spool (/scratch/slurm/jobXXXX) i BASH_SOURCE no
# apunta al repo; llavors fem servir SLURM_SUBMIT_DIR (directori des d'on es
# va fer sbatch), que és el repo correcte.
SCRIPT_DIR="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-${SCRIPT_DIR}/.venv/bin/python}"

cd "$SCRIPT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

# Les tasques de l'array són "workers": cadascuna processa les contingències
# el ID de les quals és congruent amb el seu índex mòdul WORKER_TOTAL.
if [[ "${PIPELINE_STAGE:-preprocess}" == "process" ]]; then
    if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
        echo "SLURM_ARRAY_TASK_ID is not set for the process stage." >&2
        exit 1
    fi

    worker_id="$SLURM_ARRAY_TASK_ID"       # 1..WORKER_TOTAL
    total="${TOTAL_CONTINGENCIES:?}"
    workers="${WORKER_TOTAL:?}"

    for (( cid = worker_id; cid <= total; cid += workers )); do
        "$PYTHON_BIN" 2.process.py "$cid" || {
            echo "Error processant la contingència $cid (es continua amb la següent)." >&2
        }
    done
    exit 0
fi

# El job principal genera totes les contingències abans de crear els workers.
echo "Running preprocess"
"$PYTHON_BIN" 1.preprocess.py

# Consulta quantes files ha creat el preprocess per definir el rang.
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

# Nombre de workers (tasques de l'array). Ha de ser <= MaxSubmitJobsPerUser del
# teu QOS (mira-ho amb `bsc_queues`). Cada worker processa aproximadament
# contingency_count / WORKER_TOTAL contingències.
WORKER_TOTAL="${WORKER_TOTAL:-300}"

# No llancis més workers que contingències hi ha.
if (( WORKER_TOTAL > contingency_count )); then
    WORKER_TOTAL=$contingency_count
fi

echo "Submitting $WORKER_TOTAL worker tasks for $contingency_count contingencies"
jobid=$(sbatch --parsable \
    --array="1-${WORKER_TOTAL}" \
    --export="ALL,PIPELINE_STAGE=process,WORKER_TOTAL=${WORKER_TOTAL},TOTAL_CONTINGENCIES=${contingency_count}" \
    "$SCRIPT_DIR/exec_marenostrum.sh")
# La carpeta amb el número de job s'ha de crear abans que els workers escriguin.
mkdir -p "slurm_outputs/$jobid"
echo "Submitted array job $jobid (logs a slurm_outputs/$jobid)"
