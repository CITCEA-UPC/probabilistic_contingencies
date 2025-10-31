#!/bin/bash

# Script para ejecutar el análisis de contingencias probabilísticas
# Uso: ./exec.sh [debug|bsc_cs] [num_nodes]
# Ejemplos:
#   ./exec.sh debug          # Ejecuta en modo debug con 1 nodo
#   ./exec.sh bsc_cs         # Ejecuta en modo bsc_cs con 1 nodo
#   ./exec.sh bsc_cs 4       # Ejecuta en modo bsc_cs con 4 nodos

# Verificar parámetros
if [ $# -eq 0 ]; then
    echo "Error: Debes especificar el modo de ejecución (debug o bsc_cs)"
    echo "Uso: $0 [debug|bsc_cs] [num_nodes]"
    echo "Ejemplos:"
    echo "  $0 debug          # Modo debug con 1 nodo"
    echo "  $0 bsc_cs         # Modo bsc_cs con 1 nodo"
    echo "  $0 bsc_cs 4       # Modo bsc_cs con 4 nodos"
    exit 1
fi

MODE=$1
NUM_NODES=${2:-1}  # Por defecto 1 nodo si no se especifica

# Validar modo
if [ "$MODE" != "debug" ] && [ "$MODE" != "bsc_cs" ]; then
    echo "Error: El modo debe ser 'debug' o 'bsc_cs'"
    echo "Modo recibido: $MODE"
    exit 1
fi

echo "=== Configuración de ejecución ==="
echo "Modo: $MODE"
echo "Número de nodos: $NUM_NODES"
echo "================================"

module load python/3.10.2 COMPSs/3.3.3
#module load python/3.10.2 COMPSs/TrunkEI

#export PYTHONPATH=${PYTHONPATH}:$(pwd)/src:$(pwd):$(pwd)/stability_analysis
export PYTHONPATH=$(pwd)/../packages:$(pwd)/src:$(pwd):$(pwd)/stability_analysis

set -xe 
echo "PYTHONPATH=${PYTHONPATH}"
which python
python --version

# Configurar parámetros según el modo
if [ "$MODE" = "debug" ]; then
    echo "Ejecutando en modo DEBUG..."
    enqueue_compss \
      --pythonpath="${PYTHONPATH}" \
      --lang=python \
      --project_name=bsc19 \
      --qos=debug \
      --worker_in_master_cpus=40 \
      --exec_time=120 \
      --num_nodes=$NUM_NODES \
      --tracing \
      $(pwd)/main.py
else
    echo "Ejecutando en modo BSC_CS..."
    enqueue_compss \
      --pythonpath="${PYTHONPATH}" \
      --lang=python \
      --project_name=bsc19 \
      --qos=bsc_cs \
      --worker_in_master_cpus=40 \
      --exec_time=2880 \
      --num_nodes=$NUM_NODES \
      --tracing \
      $(pwd)/main.py
fi

if false; then
  enqueue_compss \
    --pythonpath="${PYTHONPATH}" \
    --lang=python \
    --project_name=bsc19 \
    --qos=bsc_cs \
    --num_nodes=1 \
    --debug \
    --job_execution_dir="$(pwd)" \
    --log_dir="$(pwd)" \
    --worker_working_dir="$(pwd)" \
    --master_working_dir="$(pwd)" \
    --tracing \
    $(pwd)/main.py
fi