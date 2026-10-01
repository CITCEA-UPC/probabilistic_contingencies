#!/usr/bin/env bash

# =============================================================================
# Pipeline de contingències (BSC / MareNostrum 5, partició GPP)
# =============================================================================
#
# Ús (des del node de login):  ./exec_marenostrum.sh
#
# L'escript té dues etapes, controlades per la variable PIPELINE_STAGE:
#
#   1. preprocess (per defecte, s'executa al node de login):
#        - 1.preprocess.py genera totes les contingències a la BD. Amb
#          CLEAR_DB_ON_START=True esborra la BD abans, així que els IDs són
#          contigus 1..N.
#        - Llança un job array on cada tasca és UN NODE que processa un rang
#          contigu de contingències en paral·lel amb tots els seus cores.
#
#   2. process (cada tasca de l'array = 1 node):
#        - Calcula el seu rang [start, end] d'IDs segons SLURM_ARRAY_TASK_ID.
#        - Processa el rang en paral·lel (xargs -P <cores>) amb 2.process.py.
#
# Funciona per a qualsevol nombre de contingències (144, 56k, ...): el nombre
# de nodes es calcula dinàmicament i s'acota als límits del QOS.
#
# Límits de la partició GPP / QOS gp_bsccs de MN5:
#   - 224 cores per node.
#   - MAX PROC = 14000 CPUs per job (≈ 62 nodes).
#   - MaxSubmitJobs finit (comprova-ho amb `sacctmgr show qos gp_bsccs`); el
#     nombre de tasques de l'array és <= MAX_NODES, molt per sota del límit.

#SBATCH --job-name=contingencies
#SBATCH --output=slurm_outputs/slurm-%x-%A_%a.out
#SBATCH --error=slurm_outputs/slurm-%x-%A_%a.err
#SBATCH --time=12:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --account=bsc15
#SBATCH --qos=gp_bsccs
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=agracia@bsc.es

# ---------------------------------------------------------------------------
# Entorn
# ---------------------------------------------------------------------------
module load hdf5
module load python/3.12.1

unset PYTHONHOME
unset PYTHONPATH

set -euo pipefail

# ---------------------------------------------------------------------------
# Directori del repositori i intèrpret de Python
# ---------------------------------------------------------------------------
# En una tasca d'array, Slurm copia el script a l'spool i BASH_SOURCE no apunta
# al repo; per això es fa servir SLURM_SUBMIT_DIR (directori des d'on es va fer
# sbatch). En execució local es resol a partir de BASH_SOURCE.
SCRIPT_DIR="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-${SCRIPT_DIR}/.venv/bin/python}"

cd "$SCRIPT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Configuració
# ---------------------------------------------------------------------------
CORES_PER_NODE="${CORES_PER_NODE:-224}"   # cores per node (partició GPP de MN5)
MAX_NODES="${MAX_NODES:-62}"              # MAX PROC (14000) / CORES_PER_NODE

# ---------------------------------------------------------------------------
# Etapa "process": una tasca de l'array = un node
# ---------------------------------------------------------------------------
run_worker() {
    local rank="${SLURM_ARRAY_TASK_ID:?}"
    local nnodes="${SLURM_ARRAY_TASK_COUNT:?}"
    local ncpus="${SLURM_CPUS_PER_TASK:-$CORES_PER_NODE}"
    local total="${TOTAL_CONTINGENCIES:?}"

    # Rang contigu [start, end] d'IDs assignat a aquest node.
    local chunk=$(( (total + nnodes - 1) / nnodes ))
    local start=$(( (rank - 1) * chunk + 1 ))
    local end=$(( rank * chunk ))
    if (( end > total )); then
        end=$total
    fi

    if (( start > end )); then
        echo "Node $rank: cap contingència assignada."
        return 0
    fi

    echo "Node $rank: processant les contingències $start..$end de $total amb $ncpus cores"

    # Processa el rang en paral·lel. 2.process.py ja desa l'estat de cada
    # contingència a la BD, així que una fallada individual no atura el node.
    if ! seq "$start" "$end" \
        | xargs -P "$ncpus" -n 1 -r "$PYTHON_BIN" 2.process.py; then
        echo "Node $rank: alguna contingència ha fallat (mira els logs)." >&2
    fi
}

# ---------------------------------------------------------------------------
# Etapa "preprocess": s'executa al node de login
# ---------------------------------------------------------------------------
count_contingencies() {
    "$PYTHON_BIN" -c '
import sqlite3
import config

with sqlite3.connect(config.DB_FILE) as connection:
    print(connection.execute(
        "SELECT COUNT(*) FROM contingency_results"
    ).fetchone()[0])
'
}

run_preprocess() {
    echo "Running preprocess"
    "$PYTHON_BIN" 1.preprocess.py

    local total
    total="$(count_contingencies)"

    if (( total < 1 )); then
        echo "No contingencies were generated." >&2
        exit 1
    fi

    # Un node per cada CORES_PER_NODE contingències, acotat a MAX_NODES.
    local nodes=$(( (total + CORES_PER_NODE - 1) / CORES_PER_NODE ))
    if (( nodes > MAX_NODES )); then
        nodes=$MAX_NODES
    fi

    echo "Submitting $nodes node-tasks for $total contingencies"
    mkdir -p "$SCRIPT_DIR/slurm_outputs"

    local jobid
    jobid="$(sbatch --parsable \
        --array="1-${nodes}" \
        --nodes=1 \
        --ntasks=1 \
        --cpus-per-task="$CORES_PER_NODE" \
        --export="ALL,PIPELINE_STAGE=process,TOTAL_CONTINGENCIES=${total}" \
        "$SCRIPT_DIR/exec_marenostrum.sh")"

    echo "Submitted array job $jobid (logs a slurm_outputs/)"
}

# ---------------------------------------------------------------------------
# Punt d'entrada: tria l'etapa segons PIPELINE_STAGE
# ---------------------------------------------------------------------------
if [[ "${PIPELINE_STAGE:-preprocess}" == "process" ]]; then
    run_worker
    exit 0
fi

run_preprocess
