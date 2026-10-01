# Comandes útils

## Límit d'execució

```bash
(.venv) [bsc453248@glogin4 probabilistic_contingencies]$ sacctmgr show qos name=gp_bsccs format=Name,MaxTRESPerJob,MaxTRESPerNode,MaxWall,MaxSubmi
tJobs
      Name       MaxTRES MaxTRESPerNode     MaxWall MaxSubmit 
---------- ------------- -------------- ----------- --------- 
  gp_bsccs cpu=28000,no+                 2-00:00:00       366 

scontrol show partitions 
```