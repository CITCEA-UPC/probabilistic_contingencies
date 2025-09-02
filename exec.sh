#!/bin/bash
set -e  # si hay un error, se detiene la ejecución

echo "🔹 Eliminando entorno previo (si existe)..."
pycompss env remove docker-compss || true

echo "🔹 Inicializando nuevo entorno docker-compss con Docker..."
pycompss init -n docker-compss docker -i compss/compss:3.3.3

echo "🔹 Cambiando al entorno docker-compss..."
pycompss env change docker-compss

#echo "🔹 Para ejecutar un comando y verlo por pantalla"
#docker exec -it pycompss-master-docker-compss ls -l

echo "🔹 Copiando el contenido de stability analysis al container"
docker cp stability_analysis/ pycompss-master-docker-compss:/Dades/git/probabilistic_contingencies/  # esto lo copia en la carpeta home dentro de tu contenedor

echo "🔹 Instalando las dependencias de stability analysis"
docker exec -it pycompss-master-docker-compss pip install -e /Dades/git/probabilistic_contingencies/stability_analysis

echo "🔹 Instalando los requirements"
docker exec -it pycompss-master-docker-compss pip install -r /Dades/git/probabilistic_contingencies/requirements.txt

echo "🔹 Ejecutando el programa"
pycompss run main_parallel.py

#echo "🔹 Por si quiero interactuar con el contenedor"
#docker exec -it pycompss-master-docker-compss bash

# echo "🔹 Cómo ejecutar directamente líneas"
#docker exec -it pycompss-master-docker-compss pip install numpy

#echo "🔹 TODO: Preguntar a edu si esto puede ir así"
#pycompss run main_parallel.py

# Copiar archivo al exterior. Esto va así?
#docker cp pycompss-master-docker-compss:Dades/git/Dades/git/probabilistic_contingencies/results_parallel.json ./results_parallel.json

# PAra resetear el contenedor:
# docker exec -it pycompss-master-docker-compss compss_clean_procs

#docker exec -it pycompss-master-docker-compss compss_clean_procs; pycompss run main_parallel.py