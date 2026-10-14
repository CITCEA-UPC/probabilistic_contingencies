#!/usr/bin/env bash
# =============================================================================
# pycompss_mn.sh — Pipeline de contingències amb PyCOMPSs al BSC MareNostrum 5
# =============================================================================
#
# Llança pycompss_main.py (que processa cada contingència com una @task) a
# través d'enqueue_compss, que envia la feina a SLURM i desplega el runtime
# de COMPSs (master + workers) pels nodes demanats.
#
# Ús:
#   ./pycompss_mn.sh                  # processa les contingències 'pending'
#   ./pycompss_mn.sh --pending        # idem (explícit)
#   ./pycompss_mn.sh --all            # reprocessa TOTES les contingències
#   ./pycompss_mn.sh --ids 1,2,3      # només unes quantes (a posteriori)
#
# Tots els paràmetres es poden sobreescriure amb variables d'entorn:
#   PROJECT, QOS, NUM_NODES, CPUS_PER_NODE, WORKER_IN_MASTER_CPUS,
#   EXEC_TIME, WALL_CLOCK_LIMIT, COMPSs_VERSION, JOB_NAME, LOG_DIR, TRACING.
#
# ---------------------------------------------------------------------------
# ENTORN PYTHON (important!)
# ---------------------------------------------------------------------------
# Les @task corren en workers que han de poder fer:
#   import config, contingency, VeraGridEngine, numpy, ...
# Per tant, l'entorn Python de COMPSs ha de tenir pycompss I les dependències
# de VeraGrid (numpy, numba, fmpy, matplotlib...). Dues opcions:
#
#   A) (recomanada) Instal·lar pycompss dins del .venv del projecte i fer-lo
#      servir com a intèrpret:
#          .venv/bin/pip install pycompss
#          VENV="$PWD/.venv" ./pycompss_mn.sh --ids 1,2,3
#   B) Fer servir el python del mòdul COMPSs i afegir el site-packages del
#      .venv al PYTHONPATH (menys net, pot tenir conflictes de versions).
#
# El mòdul COMPSs es carrega amb 'module load COMPSs/<versió>'; aquest mòdul
# ja inclou Java, Python i el runtime. No carreguis altres Python a sobre.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Paràmetres de llançament (sobreescriu-los amb variables d'entorn)
# ---------------------------------------------------------------------------
PROJECT="${PROJECT:-bsc15}"                         # compte/projecte SLURM
QOS="${QOS:-gp_bsccs}"                              # quality of service
NUM_NODES="${NUM_NODES:-1}"                         # nodes (1 = tot en un node)
CPUS_PER_NODE="${CPUS_PER_NODE:-112}"               # cores/node (GPP: 112)
WORKER_IN_MASTER_CPUS="${WORKER_IN_MASTER_CPUS:-112}"  # cores de worker al master
EXEC_TIME="${EXEC_TIME:-720}"                       # walltime SLURM (minuts)
WALL_CLOCK_LIMIT="${WALL_CLOCK_LIMIT:-42000}"       # límit COMPSs (segons, < EXEC_TIME*60)
COMPSs_VERSION="${COMPSs_VERSION:-3.3.3}"           # versió del mòdul COMPSs
JOB_NAME="${JOB_NAME:-contingencies_pycompss}"      # nom del job
LOG_DIR="${LOG_DIR:-${SCRIPT_DIR}/compss_logs}"     # carpeta de logs COMPSs
TRACING="${TRACING:-}"                              # p. ex. TRACING="--tracing" per activar-lo

# ---------------------------------------------------------------------------
# Entorn Python
# ---------------------------------------------------------------------------
module load "COMPSs/${COMPSs_VERSION}"

# Si s'indica un venv (opció A), l'activem perquè enqueue_compss l'usi com a
# intèrpret i el propagui als workers (pycompss ha d'estar instal·lat dins).
if [[ -n "${VENV:-}" ]]; then
    # shellcheck disable=SC1091
    source "${VENV}/bin/activate"
    echo "Usant venv: ${VENV}"
fi

# PYTHONPATH perquè les @task trobin config.py, contingency.py i VeraGrid.
# (config.py ja injecta VeraGrid_TenSyGrid/src a sys.path, però així ho fem
#  explícit i robust per als workers remots.)
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/VeraGrid_TenSyGrid/src:${PYTHONPATH:-}"

mkdir -p "${LOG_DIR}"

# ---------------------------------------------------------------------------
# Llançament amb enqueue_compss
# ---------------------------------------------------------------------------
# shellcheck disable=SC2086
enqueue_compss \
    --project_name="${PROJECT}" \
    --qos="${QOS}" \
    --num_nodes="${NUM_NODES}" \
    --cpus_per_node="${CPUS_PER_NODE}" \
    --worker_in_master_cpus="${WORKER_IN_MASTER_CPUS}" \
    --exec_time="${EXEC_TIME}" \
    --wall_clock_limit="${WALL_CLOCK_LIMIT}" \
    --job_name="${JOB_NAME}" \
    --worker_working_dir=shared_disk \
    --master_working_dir=shared_disk \
    --lang=python \
    --pythonpath="${PYTHONPATH}" \
    --log_dir="${LOG_DIR}" \
    ${TRACING} \
    "${SCRIPT_DIR}/pycompss_main.py" "$@"
