VERSION=1.3
JOB_NAME=probabilistic
NAME_OUTPUT=out
PARTITION=dops
N_TASKS=1
CPUS_PER_TASK=16
MAIL_TYPE=END,FAIL
MAIL_USER=alexandre.gracia@upc.edu
MEMORY=60G
BEGIN=now
TIME_LIMIT=192:00:00
LOG_OUTPUT=log
FORCED_NODES=
EXCLUDED_NODES=
ROUTE=~/git/probabilistic_contingencies
COMMANDS=(
    "hostname"
    "source $ROUTE/venv/bin/activate"
    "python3 -u $ROUTE/main.py"
    "deactivate"
)
