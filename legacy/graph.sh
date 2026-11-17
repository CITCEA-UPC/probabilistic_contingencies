#!/usr/bin/env bash

# Comprova si s'ha passat almenys un paràmetre
if [ -z "$1" ]; then
    echo "Error: Falta el paràmetre CONTINGENCY_ID."
    echo "Ús: $0 <CONTINGENCY_ID>"
    exit 1
fi

CONTINGENCY_ID="$1"
OUTPUT_DIR="plots"

# Crea el directori 'plots' si no existeix
mkdir -p "$OUTPUT_DIR"

# Noms de fitxer basats en l'ID de la contingència
PSTATS_FILE="${OUTPUT_DIR}/${CONTINGENCY_ID}.profile.pstats"
SVG_FILE="${OUTPUT_DIR}/${CONTINGENCY_ID}.profile.svg"
PNG_FILE="${OUTPUT_DIR}/${CONTINGENCY_ID}.profile.png"

# 1. Executa el profiler generant un .pstats propi per aquesta contingència
.venv/bin/python3 -m cProfile -o "$PSTATS_FILE" 2.process.py "$CONTINGENCY_ID"

# 2. Genera la imatge SVG des del .pstats d'aquesta contingència
gprof2dot -f pstats "$PSTATS_FILE" | dot -Tsvg -o "$SVG_FILE"

# 3. Genera la imatge PNG des del .pstats d'aquesta contingència
gprof2dot -f pstats "$PSTATS_FILE" | dot -Tpng -o "$PNG_FILE"

echo "Perfilat completat per a la contingència $CONTINGENCY_ID."
echo "Fitxers generats a ${OUTPUT_DIR}/:"
echo " - $PSTATS_FILE"
echo " - $SVG_FILE"
echo " - $PNG_FILE"


# Només funcions amb >0.5% del temps (llindar de node)
# gprof2dot -f pstats -n 0.5 PSTATS_FILE | dot -Tsvg -o SVG_FILE

# Treure paths llargs dels noms (els deixa més nets)
# gprof2dot -f pstats --strip -n 1 PSTATS_FILE | dot -Tsvg -o SVG_FILE

# Retallar a partir d'una funció arrel concreta
# gprof2dot -f pstats --root=calculate_contingency PSTATS_FILE | dot -Tsvg -o SVG_FILE

# Generar gràfic amb un node arrel específic
# gprof2dot -f pstats -n 0.5 --root="*main" plots/13.profile.pstats | dot -Tsvg -o plots/13.2.svg

#pip install snakeviz
#.venv/bin/python -m cProfile -o profile.pstats 2.process.py 1
#snakeviz profile.pstats