#!/usr/bin/env bash
# Validació del cas base IEEE 118, sense contingències ni accés a SQLite.
# Preparat per quan es resolgui el rebuig de connectivitat EMT de VeraGrid.
# Un node a gp_debug; una sola configuració numèrica per job.
#
#   ./validation/ieee118_mn.sh --dry-run  # mostra la comanda, no envia res
#   ./validation/ieee118_mn.sh            # primer cas: 600 passos, 1 període
#   STEPS_PER_PERIOD=1200 ./validation/ieee118_mn.sh
#   STEPS_PER_PERIOD=1200 SETTLE_PERIODS=10 ./validation/ieee118_mn.sh
# No enviar refinaments fins que el primer cas hagi passat inicialització i EMT.
# SETTLE_PERIODS és la durada TOTAL en períodes; es captura l'últim període.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
dry_run=false
if [[ "${1:-}" == --dry-run && $# == 1 ]]; then
    dry_run=true
elif (( $# )); then
    echo "Ús: $0 [--dry-run]" >&2
    exit 2
fi

STEPS_PER_PERIOD="${STEPS_PER_PERIOD:-600}"
SETTLE_PERIODS="${SETTLE_PERIODS:-1}"
MODES="${MODES:-12}"
EXEC_TIME="${EXEC_TIME:-120}"
for value in "$STEPS_PER_PERIOD" "$SETTLE_PERIODS" "$MODES" "$EXEC_TIME"; do
    if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
        echo "Els paràmetres numèrics han de ser enters positius." >&2
        exit 2
    fi
done
if (( STEPS_PER_PERIOD < 2 || EXEC_TIME > 120 )); then
    echo "Calen almenys 2 passos; gp_debug admet fins a 120 minuts." >&2
    exit 2
fi

GRID="$ROOT/stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw"
RUN_DIR="${RUN_DIR:-$ROOT/outputs/validation/ieee118_base_case/run_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
if [[ "$RUN_DIR" != /* || "$RUN_DIR" == *' '* || "$ROOT" == *' '* ]]; then
    echo "RUN_DIR ha de ser absolut; evitar espais als camins d'arguments COMPSs." >&2
    exit 2
fi
[[ -f "$GRID" ]] || { echo "No s'ha trobat $GRID" >&2; exit 2; }

command=(enqueue_compss
    "--project_name=${PROJECT:-bsc15}" --qos=gp_debug --num_nodes=1
    --cpus_per_node=8 --worker_in_master_cpus=8 "--exec_time=$EXEC_TIME"
    --job_name=ieee118_base_validation "--job_execution_dir=$RUN_DIR/logs"
    "--appdir=$ROOT/validation" --worker_working_dir=local_disk
    --master_working_dir=local_disk --lang=python
    "--pythonpath=$ROOT:$ROOT/validation:$ROOT/VeraGrid_TenSyGrid/src"
    "--log_dir=$RUN_DIR/logs" "$ROOT/validation/base_case.py"
    --grid "$GRID" --out "$RUN_DIR/results" --steps "$STEPS_PER_PERIOD"
    --settle-periods "$SETTLE_PERIODS" --modes "$MODES")

if "$dry_run"; then
    printf '%q ' "${command[@]}"
    printf '\n'
    exit 0
fi

module load hdf5 "python/${PYTHON_MODULE:-3.12.1}"
unset PYTHONHOME PYTHONPATH CONTINGENCIES_LOCAL
module load "COMPSs/${COMPSs_VERSION:-3.4.post2609}"
source "${VENV:-$ROOT/.venv}/bin/activate"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p "$RUN_DIR/logs"
echo "Resultats i logs: $RUN_DIR"
"${command[@]}"
