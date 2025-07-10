# Data generator

#### Guide to set up datagen on HPC

Clone stability analysis repository, custom GridCal repository and datagen
```bash
git clone https://github.com/iraola/stability-analysis stability_analysis
git clone https://github.com/iraola/new-GridCal.git GridCal
git clone https://github.com/MauroGarciaLorenzo/hp2c-dt/ datagen
```

Move into datagen and checkout to the necessary branch and create "packages" dir
```bash
cd datagen
git checkout 54...
mkdir packages
```

Load python
```bash
module load python/3.12.1
```

Install packages separatelly into the "packages" directory to make sure we get the library versions we want instead of the ones imposed by GridCal
```bash
pip install -r requirements.txt --target=packages/
pip install -e ../GridCal/src/GridCalEngine
pip install -e ../stability_analysis
```

#### Preferred configuration for distributed performance

- Use `@constraint(local=True)` for the main agent task
- Tipology `tree` instead of `plain`
- Use scheduler `orderstrict.FIFOts`
