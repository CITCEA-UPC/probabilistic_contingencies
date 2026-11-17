#!/usr/bin/env bash
# Execució local en sèrie, sense Slurm ni runtime COMPSs.
# Requereix les dependències de VeraGrid instal·lades al Python seleccionat.
# La xarxa i la BD es configuren a config.py.
#
# Després del càlcul es generen CSV, JSON i gràfics de risc de TOTA la BD,
# també amb --ids o si no queden pendents. --preprocess només genera la BD.
# --skip-risk omet els informes; --risk-out /ruta canvia la carpeta de sortida.
# La inspecció d'un cas amb modal_analysis.py es fa explícitament.
# Només el mestre accedeix a SQLite; --batch-size N controla els resultats
# per transacció (256 per defecte), sense limitar les tasques en paral·lel.
#
# Ús:
#   ./local_exec.sh --preprocess         # genera la BD local
#   ./local_exec.sh --ids 13             # executa només el cas 13
#   ./local_exec.sh --ids 1,13           # executa diversos casos en sèrie
#   ./local_exec.sh --debug --ids 13 --skip-risk # depura sense generar informes
#   ./local_exec.sh --pending            # processa totes les pendents en sèrie
#   ./local_exec.sh                      # genera la BD i processa les pendents
#
# --preprocess i l'execució sense arguments regeneren la BD si
# config.CLEAR_DB_ON_START és True. --ids utilitza la BD existent i
# actualitza el resultat del cas encara que ja estigués calculat.
#
# Python: entorn virtual actiu, .venv del repo o python3 del PATH.
# Per seleccionar-ne un altre: PYTHON_BIN=/ruta/python ./local_exec.sh --ids 13
#
# Amb pdb, per aturar-se abans del càlcul:
#   (Pdb) b contingency.calculate_contingency
#   (Pdb) c
# Després: n (següent línia), s (entrar), p expressió (inspeccionar), q (sortir).
# Les excepcions del càlcul es capturen i es desen a la BD; posa un breakpoint
# al punt que vulguis inspeccionar per seguir-les abans que es capturin.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${PYTHON_BIN:-}" ]]; then
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
    elif [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
        PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
    else
        PYTHON_BIN=python3
    fi
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python executable not found: $PYTHON_BIN" >&2
    exit 1
fi

# main.py selecciona els dummies encara que PyCOMPSs estigui instal·lat.
export CONTINGENCIES_LOCAL=1

if [[ "${1:-}" == "--debug" ]]; then
    shift
    exec "$PYTHON_BIN" -u -m pdb "${SCRIPT_DIR}/main.py" "$@"
fi

exec "$PYTHON_BIN" -u "${SCRIPT_DIR}/main.py" "$@"
