module load python/3.10.2 COMPSs 
export PYTHONPATH=${PYTHONPATH}:$(pwd)/src
enqueue_compss \
  --pythonpath="${PYTHONPATH}" \
  --lang=python \
  --project_name=bsc19 \
  --qos=debug \
  --exec_time=10 \
  --num_nodes=1 \
  /home/bsc/bsc019818/tutorial_apps/python/increment/src/increment.py 10 1 2 3

