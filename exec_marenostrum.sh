#!/usr/bin/env bash

# =============================================================================
# Pipeline de contingències — BSC MareNostrum 5 (partició GPP)
# =============================================================================
#
# Ús:  ./exec_marenostrum.sh
#
# Dues etapes (segons PIPELINE_STAGE):
#   1. preprocess (per defecte, al login node): genera la BD i llança un array
#      on cada tasca és UN NODE sencer que processa un rang de contingències.
#   2. process (cada tasca de l'array): processa el seu rang en paral·lel amb
#      tots els cores del node (xargs -P).
#
# GPP: 112 cores/node. QOS gp_bsccs: 125 nodes (14000 cores) per job, 48h.

#SBATCH --job-name=contingencies
#SBATCH --output=slurm_outputs/slurm-%x-%A_%a.out
#SBATCH --error=slurm_outputs/slurm-%x-%A_%a.err
#SBATCH --time=12:00:00
#SBATCH --account=bsc15
#SBATCH --qos=gp_bsccs
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=agracia@bsc.es

module load hdf5
module load python/3.12.1

unset PYTHONHOME
unset PYTHONPATH

set -euo pipefail

# Directori del repo. En una tasca d'array, SLURM_SUBMIT_DIR apunta al repo
# (BASH_SOURCE apuntaria a l'spool).
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
CORES_PER_NODE="${CORES_PER_NODE:-112}"   # GPP: 112 cores/node
MAX_NODES="${MAX_NODES:-112}"             # màx. nodes amb marge (QOS: 125)

# ---------------------------------------------------------------------------
# Etapa "process": cada tasca de l'array = un node
# ---------------------------------------------------------------------------
run_worker() {
    local rank="${SLURM_ARRAY_TASK_ID:?}"
    local nnodes="${SLURM_ARRAY_TASK_COUNT:?}"
    local total="${TOTAL_CONTINGENCIES:?}"
    local ncpus="${SLURM_CPUS_ON_NODE:-$(nproc)}"

    # Rang contigu [start, end] d'IDs assignat a aquest node.
    local chunk=$(( (total + nnodes - 1) / nnodes ))
    local start=$(( (rank - 1) * chunk + 1 ))
    local end=$(( rank * chunk ))
    if (( end > total )); then end=$total; fi
    if (( start > end )); then return 0; fi

    echo "Node $rank: contingències $start..$end de $total ($ncpus cores)"
    seq "$start" "$end" | xargs -P "$ncpus" -n 1 -r "$PYTHON_BIN" 2.process.py \
        || echo "Node $rank: alguna contingència ha fallat" >&2
}

# ---------------------------------------------------------------------------
# Etapa "preprocess": es llança al login node
# ---------------------------------------------------------------------------
count_contingencies() {
    "$PYTHON_BIN" -c '
import sqlite3
import config
with sqlite3.connect(config.DB_FILE) as c:
    print(c.execute("SELECT COUNT(*) FROM contingency_results").fetchone()[0])
'
}

run_preprocess() {
    "$PYTHON_BIN" 1.preprocess.py

    local total
    total="$(count_contingencies)"
    if (( total < 1 )); then
        echo "No contingencies were generated." >&2
        exit 1
    fi

    # Un node per cada CORES_PER_NODE contingències, acotat a MAX_NODES.
    local nodes=$(( (total + CORES_PER_NODE - 1) / CORES_PER_NODE ))
    if (( nodes > MAX_NODES )); then nodes=$MAX_NODES; fi

    echo "Submitting $nodes nodes for $total contingencies"
    mkdir -p "$SCRIPT_DIR/slurm_outputs"

    local jobid
    jobid="$(sbatch --parsable \
        --array="1-${nodes}" \
        --nodes=1 \
        --exclusive \
        --export="ALL,PIPELINE_STAGE=process,TOTAL_CONTINGENCIES=${total}" \
        "$SCRIPT_DIR/exec_marenostrum.sh")"
    echo "Submitted array job $jobid"
}

# ---------------------------------------------------------------------------
# Punt d'entrada
# ---------------------------------------------------------------------------
if [[ "${PIPELINE_STAGE:-preprocess}" == "process" ]]; then
    run_worker
    exit 0
fi
run_preprocess
