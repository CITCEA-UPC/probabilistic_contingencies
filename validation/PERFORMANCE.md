# Protocol de rendiment: IEEE 118

**Estat: preparat, no executat.** Primer cal resoldre el rebuig de connectivitat
EMT i validar la part modal del 118. El cas principal del paper és el 118;
el 9 es reserva a desenvolupament local i comprovacions de suport.

## Model estudiat

S'utilitza el RAW del 118 amb els templates EMT de VeraGrid del pipeline.
`stability_analysis` és un altre estudi: no n'incorporem models ni paràmetres.
La ruta del RAW dins aquell submòdul només identifica el fitxer estàtic utilitzat.

## Condicions abans de començar

1. Comprovar la resposta del constructor amb `bug/reproduce.py`, sense patches
   temporals ni modificacions físiques de la xarxa.
2. Validar el cas base amb `validation/ieee118_mn.sh`: inicialització,
   convergència, periodicitat, refinament i modes. Revisar cada prova abans
   d'enviar la següent. Veure els comentaris del launcher per a les opcions.
3. Adaptar, si la solució de VeraGrid ho requereix, el filtre anticipat del
   pipeline productiu. Actualment encara pot rebutjar SARGENTS abans del motor.
4. Provar contingències representatives individualment a `gp_debug`, un node:
   una línia, un generador i un transformador, i casos amb retorn anticipat.
   Seleccionar els IDs a partir de les definicions de la BD vigent.
5. Fixar els paràmetres numèrics a partir de la validació, sense canviar slack,
   despatx o dades de xarxa. Els modes han de calcular-se realment en una part
   representativa del workload. Una BD amb totes les files calculades però
   rebutjades abans d'EMT no valida rendiment de la part modal.

No enviar benchmarks abans de superar aquestes condicions. No executar
automàticament tota la matriu d'experiments.

## Workload comparable

- Catàleg complet: 239 N−1 i 28.441 N−2 úniques, 28.680 casos sense cas base.
- Fer primer un pilot fix més petit per estimar temps, memòria i proporció de
  casos modals. Escollir la mida del workload final amb aquestes mesures;
  no assumir que el catàleg complet cap al walltime.
- Mateixos IDs, ordre, models, toleràncies i versió del motor a totes les
  configuracions comparades. Un subset fix és vàlid per comparar recursos;
  no s'han de barrejar subsets diferents en una corba de strong scaling.
- Cada repetició treballa sobre una **còpia independent** de la mateixa BD.
  Recalcular amb `--all`; no utilitzar `--pending` per als benchmarks.
- No regenerar el catàleg amb el `config.py` actual: selecciona el 9 per defecte.
- Separar dos workloads si cal: conjunt representatiu del pipeline complet
  i subset de casos que realment arriben a modal. Identificar com s'ha escollit
  el subset; no extrapolar-ne la cobertura al conjunt complet.
- Retenir els casos fallits i els errors en els recomptes. No eliminar una
  repetició lenta o fallida per obtenir una corba millor.

## Matriu progressiva

| Fase | Nodes | Canvi controlat | Repeticions previstes | Decisió |
| --- | --- | --- | --- | --- |
| Prova funcional | 1, `gp_debug` | Un cas per prova | Una inicial; repetir si canvia el codi | Corregir qualsevol error abans d'escalar |
| Pilot de cost | 1, general | Subset fix i petit | 3 | Estimar cost i memòria abans del catàleg |
| Recursos per tasca | 1, general | CU 8, 4, 2, 1; resta fixa | 3 per configuració viable | Fixar CU segons temps, memòria i cost |
| Strong scaling | 1, 2, 4, general | Només nombre de nodes | 3 per configuració | Ampliar a 8 només si hi ha prou feina i guany |
| Persistència | Nombre fix de nodes | Lots de 64, 256, 1024 | 3 per configuració viable | Comparar temps i memòria amb mateix resultat |
| Diagnòstic runtime | Configuració representativa | Tracing activat/desactivat | Parella comparable; ampliar si cal | Interpretar ocupació i sobrecost |

CU són recursos reservats, no fils de càlcul demostrats. CU=8 és un punt
inicial conservador per limitar concurrència, no l'òptim establert. No arribar
a CU=1 si el pilot indica manca de memòria. Mantenir `NATIVE_THREADS=1` en
aquesta primera matriu per no canviar dues variables alhora.

Strong scaling: mateix `CPUS_PER_NODE=112`, `WORKER_IN_MASTER_CPUS=112`, CU,
batch, workload i paràmetres numèrics. El mestre també pot executar workers;
declarar aquesta configuració i la càrrega del mestre en interpretar eficiència.
La cua general s'utilitza per a les comparacions multinode. Les proves que
enviï l'assistent han de continuar sent petites, d'un node a debug.

Amb 3 repeticions, mostrar mediana i mínim/màxim; no presentar-ho com un
interval de confiança. Alternar l'ordre de configuracions quan sigui viable
per reduir el biaix temporal del sistema compartit. Si la variabilitat impedeix
distingir configuracions, fer repeticions addicionals abans de concloure.

## Temps i mètriques

| Mètrica | Font / definició | Disponibilitat actual |
| --- | --- | --- |
| Temps del job | `sacct`: `Elapsed`, estat i codi de sortida | Inclou arrencada i tancament; no és temps pur del càlcul |
| Espera de cua | Diferència entre inici i enviament | Separar del temps d'execució |
| Cost per contingència | Columna `execution_time` de la BD | Cost intern del worker; no inclou espera de scheduling ni transport |
| Distribució de costos | Mediana, p90, p99, màxim; agrupats per estat/modal | Derivable de les BD; no hi ha encara resum automàtic de benchmark |
| Temps de processament al mestre | `PROCESS_PERFORMANCE.processing_total_s`: càrrega fins a final del processament, incloent alliberament de futures i logs | Implementat; exclou preprocess, selecció d’IDs, informes i arrencada/tancament de COMPSs |
| Temps de persistència | `persist_results_s`: crida completa a `storage.save_results` | Implementat; inclou validació/serialització, obertura SQLite i transacció, no només motor SQL |
| Temps d’espera | `wait_results_s`: crides a `compss_wait_on` | Implementat; inclou sincronització i recepció, no és temps pur de CPU |
| Temps d’informes | `RISK_PERFORMANCE.risk_reports_s`: crida a `run_analysis` | Implementat; exclou l’import inicial del mòdul |
| Throughput | Casos persistits / temps d'execució definit | Declarar quin denominador s'utilitza |
| Cobertura científica | Casos amb diagnòstic i casos amb modes vàlids, per estat | Derivable de resultats; `calculated=1` no implica diagnòstic resolt |
| Node-hores | Nodes assignats × hores de job | Inclou recursos reservats encara que estiguin ociosos |
| Memòria | `sacct` per passos/processos i mètriques disponibles del runtime | `MaxRSS` no s'ha de presentar com suma de memòria de tots els workers |
| Ocupació i esperes | Traces PyCOMPSs | Només disponible si s'activa tracing |

Els temporitzadors mínims del mestre ja estan implementats amb `perf_counter`.
Les línies `PROCESS_PERFORMANCE {JSON}` i `RISK_PERFORMANCE {JSON}` queden
als logs. No confondre el temps que triga `enqueue_compss` a enviar el job
amb el temps del job. No sumar durades concurrents per estimar temps de paret.

Calcular `S(n)=T(1)/T(n)` i `E(n)=S(n)/n` per un mateix abast de temps i el
mateix workload. Un node COMPSs és la base de strong scaling, no execució
seqüencial: pot tenir molts workers simultanis. Una execució local en sèrie
és una comparació diferent i només s'ha d'afegir si és viable i comparable.

`--skip-risk` separa el cost del càlcul i persistència del postprocessat.
Mesurar els informes de risc per separat i incloure'ls quan es presenti el
temps de tot el pipeline. Si es publica només `Elapsed` del job amb skip-risk,
anomenar-lo temps del job de càlcul, no temps complet amb informes.

## Plantilla manual d'una execució (NO executar encara)

Exemple de configuració; **no és una recomanació final de recursos**. Enviar
des de l'arrel quan el pilot i la validació ho justifiquin:

```bash
mkdir -p "$PWD/outputs/validation/ieee118_performance"
RUN_DIR="$(mktemp -d "$PWD/outputs/validation/ieee118_performance/run_XXXXXX")"

# Còpia coherent de SQLite. L'original s'obre en mode només lectura.
python - "$PWD/outputs/databases/results_IEEE118busNREL.db" "$RUN_DIR/input.db" <<'PY'
import sqlite3
import sys
from pathlib import Path
source = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + '?mode=ro', uri=True)
target = sqlite3.connect(sys.argv[2])
try:
    source.backup(target)
finally:
    target.close()
    source.close()
PY

QOS=gp_bsccs EXEC_TIME=2880 NUM_NODES=1 \
CPUS_PER_NODE=112 WORKER_IN_MASTER_CPUS=112 \
COMPUTING_UNITS=8 NATIVE_THREADS=1 \
LOG_DIR="$RUN_DIR/logs" \
./pycompss_mn.sh --db "$RUN_DIR/input.db" --all --batch-size 256 --skip-risk
```

`--all` aquí calcula el catàleg complet de la còpia. Per un pilot, preparar
una selecció fixa amb `--ids` i mantenir-la a totes les repeticions del pilot.
No aplicar aquesta plantilla sobre la BD original. La comanda de còpia pot
executar-se en login; els càlculs van als nodes via el launcher.

## Registre mínim i criteris per avançar

Per repetició guardar la comanda exacta, job ID, commits del projecte/motor,
hash del RAW, IDs del workload i resultats. BD independent i logs de cada run
es conserven sota `outputs/validation/ieee118_performance/`, fora de Git.
No cal afegir un sistema nou de traçabilitat.

- Abans de comparar temps, verificar mateixes definicions i distribució de
  classificacions, i comparar els modes amb toleràncies justificades pel
  refinament; no exigir igualtat bit a bit dels autovalors.
- Si apareixen canvis de classificació, especialment prop del llindar modal,
  investigar-los abans de presentar les execucions com a equivalents.
- Si hi ha timeout, OOM o error, no calcular speedup d'una execució incompleta
  com si fos equivalent a una de completa.
- Si el temps d'arrencada o la falta de tasques domina, aturar l'ampliació de
  nodes. No assumir que 20 nodes és millor ni créixer només per tenir una corba.
- La suma de costos de worker no és una mesura d'ús efectiu de CPU: els temps
  inclouen esperes internes, càrrega de models i possible I/O.
- Un possible workflow amb tasques separades per etapa requerirà una
  comparació pròpia amb la versió actual, sobre els mateixos casos i criteris.
  Encara no està implementat ni s'ha mesurat cap benefici.


## Interpretació dels resums del mestre

`PROCESS_PERFORMANCE` inclou `selected`, `submitted`, `committed`,
`committed_batches`, `batch_size` i `completed`, a més dels temps
`load_definitions_s`, `submit_s`, `wait_results_s`, `persist_results_s` i
`processing_total_s`. És un únic resum al final del processament, també si
una excepció s'escapa: només els lots confirmats incrementen `committed`.
No es converteix una execució parcial en una mesura comparable d'èxit.

El total també inclou comptatge, alliberament de futures, logs i cost dels
mateixos temporitzadors; la suma de les quatre etapes no ha de coincidir
exactament amb el total. Les etapes es mesuren al mestre, mentre que els
workers poden calcular simultàniament. Amb els dummies locals, el càlcul
s'executa a la crida de tasca i queda inclòs a `submit_s`; això no és
sobrecost de scheduling distribuït.

`RISK_PERFORMANCE` es publica quan s'intenten generar informes, amb
`completed` i `risk_reports_s`; amb `--skip-risk` no es genera. Si no hi ha
IDs seleccionats, no hi ha processament ni resum `PROCESS_PERFORMANCE`,
encara que es puguin generar informes. Aquests resums no substitueixen
`sacct` o les traces per mesurar tot el runtime.
