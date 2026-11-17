#!/usr/bin/env bash
# =============================================================================
# pycompss_mn.sh — Pipeline de contingències amb PyCOMPSs al BSC MareNostrum 5
# =============================================================================
# Executa aquest script directament des del login node: prepara els mòduls
# hdf5, Python i COMPSs, activa el venv i envia main.py a SLURM amb
# enqueue_compss. La xarxa i la BD es seleccionen a config.py.
#
# Després del càlcul es generen CSV, JSON i gràfics de risc de TOTA la BD,
# també amb --ids o si no queden pendents. --preprocess només genera la BD.
# --skip-risk omet els informes; --risk-out /ruta canvia la carpeta de sortida.
# La inspecció d'un cas amb modal_analysis.py es fa explícitament.
# Només el mestre accedeix a SQLite; --batch-size N controla els resultats
# per transacció (256 per defecte), sense limitar les tasques en paral·lel.
#
# Ús:
#   ./pycompss_mn.sh                # genera la BD i processa les pendents
#   ./pycompss_mn.sh --preprocess   # només genera la BD
#   ./pycompss_mn.sh --ids 1,13     # processa només aquests IDs de la BD
#   ./pycompss_mn.sh --pending      # reprèn les contingències pendents
#   ./pycompss_mn.sh --all          # reprocessa totes les contingències
#   ./pycompss_mn.sh --ids 13 --skip-risk # calcula un cas sense informes
#
# Sense arguments o amb --preprocess, la BD s'esborra i es regenera si
# config.CLEAR_DB_ON_START és True. --ids, --pending i --all no la regeneren.
#
# Prova de l'IEEE 9 (selecciona'l a config.py):
#   QOS=gp_debug EXEC_TIME=120 ./pycompss_mn.sh --preprocess
#   # Espera que el job de preprocess acabi abans de llançar el següent:
#   QOS=gp_debug EXEC_TIME=120 NUM_NODES=1 COMPUTING_UNITS=8 \
#     ./pycompss_mn.sh --ids 1,13
#   Per a llançar-los tots
#   QOS=gp_debug EXEC_TIME=120 NUM_NODES=1 COMPUTING_UNITS=8 \
#     ./pycompss_mn.sh --pending
#
# Variables d'entorn disponibles:
#   PROJECT, QOS, NUM_NODES, CPUS_PER_NODE, WORKER_IN_MASTER_CPUS,
#   EXEC_TIME, COMPUTING_UNITS, PYTHON_MODULE, COMPSs_VERSION, VENV,
#   JOB_NAME, LOG_DIR, TRACING i NATIVE_THREADS (1 per defecte).
#
# Ordre de l'entorn: Python → COMPSs → venv. COMPSs proporciona pycompss
# i compss; el venv conté les dependències del motor VeraGrid.
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
PYTHON_MODULE="${PYTHON_MODULE:-3.12.1}"             # mòdul python (ha de coincidir amb el venv)
COMPSs_VERSION="${COMPSs_VERSION:-3.4.post2609}"           # versió del mòdul COMPSs
JOB_NAME="${JOB_NAME:-contingencies_pycompss}"      # nom del job
LOG_DIR="${LOG_DIR:-${SCRIPT_DIR}/outputs/logs/compss}"     # carpeta de logs COMPSs
COMPUTING_UNITS="${COMPUTING_UNITS:-1}"             # cores per @task (@constraint)
TRACING="${TRACING:-}"                              # p. ex. TRACING="--tracing" per activar-lo

# ---------------------------------------------------------------------------
# Entorn Python
# ---------------------------------------------------------------------------
# 1) Carrega Python abans de COMPSs. La versió ha de coincidir amb la del
#    .venv, que necessita libpython3.12.so del mòdul Python.
module load hdf5
module load "python/${PYTHON_MODULE}"

unset PYTHONHOME
unset PYTHONPATH

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

# PYTHONPATH perquè les @task trobin config.py, contingencies/ i VeraGrid.
# (config.py ja injecta VeraGrid_TenSyGrid/src a sys.path, però així ho fem
#  explícit i robust per als workers remots.)
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/VeraGrid_TenSyGrid/src:${PYTHONPATH:-}"

# Cores per tasca (el llegeix main.py com a @constraint(computing_units=...)).
# Amb CPUS_PER_NODE=112 i COMPUTING_UNITS=8 corren ~14 tasques per node.
export COMPUTING_UNITS

# Cada worker calcula amb un fil natiu per defecte. Evita que BLAS/OMP
# creïn un equip de fils per cadascuna de les milers de tasques concurrents.
NATIVE_THREADS="${NATIVE_THREADS:-1}"
export OMP_NUM_THREADS="${NATIVE_THREADS}"
export MKL_NUM_THREADS="${NATIVE_THREADS}"
export OPENBLAS_NUM_THREADS="${NATIVE_THREADS}"
export NUMEXPR_NUM_THREADS="${NATIVE_THREADS}"

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
    --job_name="${JOB_NAME}" \
    --job_execution_dir="${LOG_DIR}" \
    --appdir="${SCRIPT_DIR}" \
    --worker_working_dir=local_disk \
    --master_working_dir=local_disk \
    --lang=python \
    --pythonpath="${PYTHONPATH}" \
    --log_dir="${LOG_DIR}" \
    ${TRACING} \
    "${SCRIPT_DIR}/main.py" "$@"
