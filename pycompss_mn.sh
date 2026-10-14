#!/usr/bin/env bash
# =============================================================================
# pycompss_mn.sh — Pipeline de contingències amb PyCOMPSs al BSC MareNostrum 5
# =============================================================================
#
# Llança main.py (que processa cada contingència com una @task) a través
# d'enqueue_compss, que envia la feina a SLURM i desplega el runtime de
# COMPSs (master + workers) pels nodes demanats.
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
# COMPSs 3.3.3 NO porta Python (en carregar-se diu "Python not found. Please
# load a Python module"). Cal carregar-lo explícitament ABANS de COMPSs, amb
# una versió que tingui binding compss (n'hi ha per Python 3.8, 3.10 i 3.12 a
# /apps/GPP/COMPSs/3.3.3/Bindings/python/3/).
#
# Les @task corren en workers que han de fer:
#   import pycompss, compss, contingency, VeraGridEngine, numpy, ...
# - pycompss i compss els proporciona el mòdul COMPSs (via el PYTHONPATH que
#   enqueue_compss afegeix apuntant a Bindings/python/3/).
# - numpy, numba, fmpy, VeraGrid... viuen al .venv del projecte (Python 3.12),
#   que activem DESPRÉS de carregar python/3.12.1. Aquest mòdul python és
#   imprescindible: sense ell, el python del .venv no troba libpython3.12.so.
#
# Ordre correcte:  python/3.12.1  →  COMPSs/3.3.3  →  activar el .venv.
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
EXEC_TIME="${EXEC_TIME:-2880}"                       # walltime SLURM (minuts)
WALL_CLOCK_LIMIT="${WALL_CLOCK_LIMIT:-172500}"       # límit COMPSs (segons, < EXEC_TIME*60)
PYTHON_MODULE="${PYTHON_MODULE:-3.12.1}"             # mòdul python (ha de coincidir amb el venv)
COMPSs_VERSION="${COMPSs_VERSION:-3.3.3}"           # versió del mòdul COMPSs
JOB_NAME="${JOB_NAME:-contingencies_pycompss}"      # nom del job
LOG_DIR="${LOG_DIR:-${SCRIPT_DIR}/compss_logs}"     # carpeta de logs COMPSs
COMPUTING_UNITS="${COMPUTING_UNITS:-1}"             # cores per @task (@constraint)
TRACING="${TRACING:-}"                              # p. ex. TRACING="--tracing" per activar-lo

# ---------------------------------------------------------------------------
# Entorn Python
# ---------------------------------------------------------------------------
# 1) Python primer (COMPSs 3.3.3 NO el porta, i el .venv el necessita per a
#    libpython3.12.so). La versió ha de coincidir amb la del .venv.
module load hdf5
module load "python/${PYTHON_MODULE}"

# 2) COMPSs (proporciona pycompss + compss via el seu Bindings/python/3/).
module load "COMPSs/${COMPSs_VERSION}"

# 3) Activem el .venv (ara sí que funciona: libpython ja està disponible). Hi
#    viuen les dependències de VeraGrid (numpy, numba, fmpy...). Per defecte
#    el .venv del repo; sobreescriu-lo amb VENV=/ruta/al/venv si cal.
VENV="${VENV:-${SCRIPT_DIR}/.venv}"
if [[ -d "${VENV}" ]]; then
    # shellcheck disable=SC1091
    source "${VENV}/bin/activate"
    echo "Usant venv: ${VENV}"
fi

# PYTHONPATH perquè les @task trobin config.py, contingency.py i VeraGrid.
# (config.py ja injecta VeraGrid_TenSyGrid/src a sys.path, però així ho fem
#  explícit i robust per als workers remots.)
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/VeraGrid_TenSyGrid/src:${PYTHONPATH:-}"

# Cores per tasca (el llegeix main.py com a @constraint(computing_units=...)).
# Amb CPUS_PER_NODE=112 i COMPUTING_UNITS=8 corren ~14 tasques per node.
export COMPUTING_UNITS

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
    "${SCRIPT_DIR}/main.py" "$@"
