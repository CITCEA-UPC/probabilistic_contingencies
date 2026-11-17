# Probabilistic contingencies

Pipeline de contingències N−1/N−2 per a xarxes elèctriques amb VeraGrid: fluxos de potència, comprovació EMT, modes de Floquet i anàlisi de vulnerabilitat amb casos desconeguts explícits.

## Estructura

```text
main.py                 Entrada del pipeline i tasques PyCOMPSs
config.py               Xarxa seleccionada i rutes
local_exec.sh           Execució local en sèrie i depuració
pycompss_mn.sh          Enviament a MareNostrum amb PyCOMPSs
risk_analysis.py        Informes de risc de tota la BD
modal_analysis.py       Inspecció dels modes d’una contingència
contingencies/          Càlcul, persistència del mestre, diagnòstics i dummies
tests/                  Proves sense simulacions EMT
validation/             Verificació numèrica i cas base del 118
bug/                    Reproducció autònoma de la incidència EMT
docs/                   Teoria, notes BSC i diagnòstics tècnics
outputs/                BD, gràfics, logs i perfils generats
paper/                  Manuscrit i figures del paper
grids/                  Xarxes d’entrada addicionals
VeraGrid_TenSyGrid/      Submòdul del motor
stability_analysis/     Submòdul amb eines i dades addicionals
```

Els submòduls mantenen la seva ubicació. Les carpetes antigues `datagen/` i `legacy/` s’han eliminat; les versions anteriors continuen a l’historial de Git.

## Entorn local

S’ha executat amb Python 3.12. En una màquina nova, inicialitza els submòduls i crea un entorn amb les dependències del motor i matplotlib:

```bash
git submodule update --init --recursive
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./VeraGrid_TenSyGrid/src/VeraGridEngine
python -m pip install matplotlib
```

`config.py` incorpora el codi del submòdul a `sys.path`. No cal instal·lar PyCOMPSs per treballar en local: el llançador força els dummies i executa les tasques en sèrie.

Selecciona `GRID_NAME` i `GRID_PATH` a `config.py`. La BD es deriva del nom de la xarxa i es desa a `outputs/databases/`. També es pot seleccionar la xarxa amb `--grid /ruta/xarxa.raw`, sense editar la configuració; `--db` té prioritat sobre el nom de BD derivat. `--reset-db` força la regeneració des de zero. Aquestes dues opcions s’utilitzen amb el pipeline complet o `--preprocess`, sense `--pending`, `--all` ni `--ids`.

L’estudi manté les dades de la xarxa i només desactiva els elements de cada contingència. El pipeline no reassigna l’slack, no modifica les consignes i no intenta recuperar la convergència amb OPF ni redespatx. Si un càlcul no convergeix o el motor rebutja la topologia, es desa el diagnòstic disponible. Les columnes `opf_needed` i `opf_converged` es mantenen per compatibilitat amb BD històriques; els càlculs nous no executen OPF.

## Execució local

```bash
./local_exec.sh --preprocess
./local_exec.sh --ids 13
./local_exec.sh --pending
```

Sense arguments, es genera la BD i es processen les pendents. Amb `CLEAR_DB_ON_START=True`, generar la BD esborra la BD anterior d’aquella xarxa. `--ids`, `--pending` i `--all` utilitzen l’existent.

Per depurar un cas sense generar informes:

```bash
./local_exec.sh --debug --ids 13 --skip-risk
```

Dins de `pdb`:

```text
b contingency.calculate_contingency
c
```

Es pot seleccionar un altre intèrpret amb `PYTHON_BIN=/ruta/python`. El llançador prioritza l’entorn virtual actiu, després `.venv/` i finalment `python3` del PATH.

## MareNostrum

Executa el llançador directament des del login node. Prepara hdf5, Python, COMPSs i el venv, i envia la feina amb `enqueue_compss`.

```bash
QOS=gp_debug EXEC_TIME=120 ./pycompss_mn.sh --preprocess
# Espera que el job acabi abans de processar:
QOS=gp_debug EXEC_TIME=120 NUM_NODES=1 COMPUTING_UNITS=8 \
  ./pycompss_mn.sh --pending
```

`NUM_NODES` selecciona els nodes, `CPUS_PER_NODE` els cores per node i `COMPUTING_UNITS` els cores reservats per tasca. Aquest últim limita la concurrència; no és el límit de recursos del compte. Els paràmetres i les versions dels mòduls es poden sobreescriure amb variables d’entorn.

```bash
squeue -u "$USER"
sacct -j JOBID --format=JobID,State,ExitCode,Elapsed
```

Per regenerar el catàleg del 118 i executar-lo en un sol job a la cua general:

```bash
QOS=gp_bsccs EXEC_TIME=2880 NUM_NODES=20 \
CPUS_PER_NODE=112 WORKER_IN_MASTER_CPUS=112 \
COMPUTING_UNITS=8 NATIVE_THREADS=1 \
./pycompss_mn.sh \
  --grid "$PWD/stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw" \
  --db "$PWD/outputs/databases/results_IEEE118busNREL.db" \
  --reset-db --batch-size 256
```

Això esborra els resultats anteriors d'aquella BD quan comença el job. No
executar-ho mentre una altra execució utilitza la mateixa BD. No s'hi posa
`--pending`, perquè el job ha de començar pel preprocess. Les limitacions
EMT del motor continuen aplicant-se; regenerar la BD no les corregeix.

Els logs nous es desen a `outputs/logs/compss/`, incloent `compss-JOBID.out`, `.err` i `.COMPSs/`. `LOG_DIR` permet seleccionar una altra ubicació. Més notes a [docs/bsc.md](docs/bsc.md).

## Persistència i represa

El mestre carrega les definicions des de SQLite i les envia als workers. Els workers només calculen i retornen un diccionari amb l’ID i el resultat; no accedeixen a la BD. `contingencies/storage.py` valida els IDs i desa els resultats al mestre en transaccions per lots.

```bash
./local_exec.sh --pending --batch-size 64
QOS=gp_debug EXEC_TIME=120 NUM_NODES=1 COMPUTING_UNITS=8 \
  ./pycompss_mn.sh --pending --batch-size 256
```

`--db ruta.db` permet executar el pipeline sobre una altra BD sense editar `config.py`; també determina el fitxer creat o regenerat amb `--preprocess`. És útil per provar sobre una còpia sense alterar els resultats originals.

`--batch-size` controla els resultats per transacció (256 per defecte), no el nombre de tasques en paral·lel. Les tasques s’envien abans de recollir els lots. El log mostra `Committed X/Y contingency results` després de cada commit. Un lot petit confirma l’avenç més sovint; un lot gran redueix el nombre de transaccions. La recollida segueix l’ordre dels IDs seleccionats, de manera que una tasca lenta pot retardar el commit del seu lot.

Els logs inclouen un resum JSON `PROCESS_PERFORMANCE` amb temps del mestre per carregar definicions, enviar tasques, esperar resultats i persistir lots, així com els recomptes enviats i confirmats. Es publica també si el procés falla, amb `completed=false`. Els informes tenen un resum separat `RISK_PERFORMANCE`. Aquests temps exclouen l’arrencada i el tancament del runtime; l’espera no és temps de CPU i la persistència inclou tota la crida d’emmagatzematge. El protocol experimental és a [validation/PERFORMANCE.md](validation/PERFORMANCE.md).

Si falla una tasca del runtime, el transport o l’escriptura d’un lot, l’error es propaga. Els lots confirmats es conserven i el lot no desat manté els valors anteriors. En una primera execució, aquests casos continuen `pending` i es reprenen amb `--pending`; en un reprocessament amb `--all` o `--ids`, els casos no desats conserven el resultat anterior i s’han de seleccionar explícitament per tornar-los a calcular. Una excepció de càlcul capturada es desa amb `status='exception'` i no és una tasca del runtime fallida.

La centralització elimina els escriptors concurrents dels workers dins d’una mateixa execució. Cal utilitzar una sola execució de càlcul per BD alhora; no coordina dos mestres independents que treballin sobre el mateix fitxer.

## Informes i resultats

Quan totes les tasques han acabat, el mestre genera automàticament l’anàlisi de risc de **tota la BD**, també si s’han seleccionat alguns IDs o si no queden pendents. `--preprocess` només genera la BD. `--skip-risk` omet els informes i `--risk-out carpeta` en canvia la sortida.

| Contingut | Ubicació per defecte |
|---|---|
| Base de dades | `outputs/databases/results_<xarxa>.db` |
| Risc: CSV, JSON i gràfics | `outputs/plots/risk_analysis/results_<xarxa>/` |
| Logs PyCOMPSs | `outputs/logs/compss/` |
| Logs Slurm històrics | `outputs/logs/slurm/` |
| Perfils de rendiment | `outputs/profiles/` |

Es poden regenerar els informes sense executar simulacions:

```bash
python risk_analysis.py
python risk_analysis.py --db outputs/databases/results_IEEE_9_Bus.db
```

El criteri de risc considera perillosa la no-convergència del PF balancejat o trifàsic, a més de la formació d’illes i la inestabilitat modal. Un terminal rebutjat per EMT conserva el diagnòstic de risc si el PF balancejat ja ha retornat no-convergència. Les excepcions que no permeten establir el resultat del PF continuen sent desconegudes.

Per defecte, cada parella N−2 es compta una sola vegada. `--n2-counting rows` permet comparar amb el comptatge històric per files. Els casos sense diagnòstic són desconeguts; es mostren cobertura i límits de risc brut, sense un rànquing definitiu.

Per consultar un cas i, opcionalment, desar-ne el gràfic:

```bash
python modal_analysis.py 13 --no-show
python modal_analysis.py 13 --no-show --save outputs/plots/modal_analysis/modes_13.png
```

`--db` selecciona una altra BD. L’estabilitat dels modes calculats i la fragmentació de la xarxa es mostren separadament. Els dos analitzadors llegeixen la BD sense modificar-la.

La formulació i les limitacions del model són a [docs/teoria.md](docs/teoria.md) i [docs/buses_aislados_emt.md](docs/buses_aislados_emt.md).

## Proves

```bash
python -m unittest discover -s tests -v
```

Les proves de diagnòstic, risc i ordre del pipeline no executen simulacions ni requereixen el motor VeraGrid.

## Validació amb PyCOMPSs real

El 17 de novembre de 2026 s’ha validat la persistència centralitzada amb dues proves a `gp_debug`, cadascuna limitada a la contingència 13 de l’IEEE 9 i a 10 minuts. S’han utilitzat còpies de la BD amb el cas marcat prèviament com a pendent.

| Job | Disposició | Estat | Durada |
|---|---|---|---|
| `49156017` | Mestre i worker en un node | COMPLETED, codi 0 | 2 min 22 s |
| `49156230` | Mestre i worker en nodes diferents; `WORKER_IN_MASTER_CPUS=0` | COMPLETED, codi 0 | 2 min 27 s |

En totes dues proves, el worker ha retornat el resultat, el mestre ha confirmat el lot i s’han generat els informes. El cas recalculat ha quedat `ok`, amb 12 autovalors finits. Només s’ha modificat l’ID 13 de cada còpia; el SHA-256 de la BD original no ha canviat. L’evidència local és a `outputs/validation/`, incloent logs i `validation.json`.

Aquestes proves comproven el flux real i el transport entre nodes per a un cas petit. Encara no són una prova de càrrega amb milers de tasques ni de rendiment a gran escala.

## Canvi d’estructura

Les comandes d’entrada s’han mantingut a l’arrel. Les BD que hi havia a l’arrel s’han traslladat a `outputs/databases/`; `plots/`, `compss_logs/`, `slurm_outputs/` i els perfils s’han agrupat a `outputs/`. Els documents `teoria.md`, `bsc.md` i `notes.txt` són ara a `docs/`.

`outputs/` queda exclòs de Git, excepte la seva guia. Els fitxers generats que abans estaven versionats es conserven localment a la nova ubicació. Les referències a rutes antigues dins dels logs històrics no s’han reescrit.
