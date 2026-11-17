# Comandes útils (MareNostrum 5)

## Què tinc disponible?

### Versions de COMPSs

```bash
module available COMPSs
# COMPSs/3.3   COMPSs/3.3.1   ...   COMPSs/3.4   COMPSs/release(default)
```

### Particions i nodes (quants n'hi ha i l'estat)

```bash
sinfo                        # visió general de particions i nodes
sinfo -N                     # per node (estat: idle/mix/allocated)
scontrol show partitions     # particions, nodes i cores de cadascuna
scontrol show partition <nom>   # detall d'una partició concreta
```

### Cues i QOS

```bash
bsc_queues                   # visió general de cues/QOS (comanda pròpia del BSC)
```

### Límits del QOS gp_bsccs (nº CPU, walltime, nº jobs)

```bash
sacctmgr show qos name=gp_bsccs format=Name,MaxTRESPerJob,MaxTRESPerNode,MaxWall,MaxSubmitJobs
#      Name       MaxTRES MaxTRESPerNode     MaxWall MaxSubmit
#  gp_bsccs cpu=28000,no+                 2-00:00:00       366
```

### Els teus comptes i QOS associats

```bash
sacctmgr show associations user=$USER format=Account,User,QOS,Partition
```

## Els teus jobs

```bash
squeue -u $USER              # jobs en cua / corrent
scontrol show job <jobid>    # detall d'un job (nodes assignats, motiu de pendència)
scancel <jobid>              # cancel·lar un job
```

## Repartició de cores a COMPSs

Amb `enqueue_compss` (vegeu `pycompss_mn.sh`):

- `--num_nodes=N` → nodes demanats.
- `--cpus_per_node=C` → cores per node (GPP: 112/node).
- `COMPUTING_UNITS` (a `main.py`, `@constraint(computing_units=...)`) → cores que
  ocupa **cada tasca**.

Les tasques que corren alhora per node són `cpus_per_node / computing_units`:

| num_nodes | cpus_per_node | computing_units | tasques/node | tasques totals en paral·lel |
|-----------|---------------|-----------------|--------------|-----------------------------|
| 1         | 112           | 1               | 112          | 112                         |
| 20        | 112           | 1               | 112          | 2240                        |
| 20        | 112           | 8               | 14           | 280                         |
| 20        | 8             | 1               | 8            | 160                         |

> Nota: el càlcul de VeraGrid és **monofil**, així que `computing_units=1` és
> el més eficient en CPU. Puja `computing_units` (o baixa `cpus_per_node`)
> només si vols limitar la concurrència (p. ex. per memòria).
