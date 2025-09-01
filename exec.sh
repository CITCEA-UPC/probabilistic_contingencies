#!/bin/bash
set -e  # si hay un error, se detiene la ejecución

echo "🔹 Eliminando entorno previo (si existe)..."
pycompss env remove docker-compss || true

echo "🔹 Inicializando nuevo entorno docker-compss con Docker..."
pycompss init -n docker-compss docker -i compss/compss:3.3.3

echo "🔹 Cambiando al entorno docker-compss..."
pycompss env change docker-compss

#docker exec -it pycompss-master-docker-compss ls -l

# Copiar el contenido de stability analysis al contenedor de docker
docker cp stability_analysis/ pycompss-master-docker-compss:/Dades/git/probabilistic_contingencies/  # esto lo copia en la carpeta home dentro de tu contenedor
docker exec -it pycompss-master-docker-compss pip install -e /Dades/git/probabilistic_contingencies/stability_analysis

docker exec -it pycompss-master-docker-compss pip install -r /Dades/git/probabilistic_contingencies/requirements.txt

pycompss run main_parallel.py

#docker exec -it pycompss-master-docker-compss bash

#docker exec -it pycompss-master-docker-compss pip install numpy


#echo "🔹 Ejecutando aplicación con PyCOMPSs..."
#pycompss run main_parallel.py

# Copiar archivo al exterior
#docker cp pycompss-master-docker-compss:Dades/git/Dades/git/probabilistic_contingencies/results_parallel.json ./results_parallel.json
