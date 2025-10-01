module load python/3.10.2 COMPSs

#export PYTHONPATH=${PYTHONPATH}:$(pwd)/src:$(pwd):$(pwd)/stability_analysis
export PYTHONPATH=/gpfs/projects/bsc19/upc848455/packages:$(pwd)/src:$(pwd):$(pwd)/stability_analysis
enqueue_compss \
  --pythonpath="${PYTHONPATH}" \
  --lang=python \
  --project_name=bsc19 \
  --qos=debug \
  --num_nodes=1 \
  --job_execution_dir="$(pwd)" \
  --log_dir="$(pwd)" \
  --worker_working_dir="$(pwd)" \
  --master_working_dir="$(pwd)" \
  /home/upc/upc848455/probabilistic_contingencies/main_parallel.py

