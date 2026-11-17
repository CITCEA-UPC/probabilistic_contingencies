# Context de continuïtat del projecte

Actualitzat el **17 de novembre de 2026**, zona Europe/Madrid. Document per
reprendre el treball sense reconstruir la conversa. Els estats de jobs i les
xifres de la BD són una fotografia d'aquesta data: consultar-los de nou.

## Lectura inicial i objectiu

1. Llegir aquest document i les instruccions locals que siguin aplicables.
2. Consultar `git status --short`, els jobs i la BD en mode només lectura.
3. Llegir `main.py` per entendre el pipeline, i després els fitxers de l'àrea
   concreta que cal modificar. No cal tornar a llegir tots els submòduls.

L'objectiu immediat és **tancar la validació del càlcul i obtenir els resultats
de l'IEEE 118**. El paper es prepara mentrestant com a esborrany. L'usuari ha
decidit **unificar power systems i HPC en un sol paper**, després de considerar
dos articles. La contribució haurà de combinar resultats científics interpretables
amb evidència de rendiment; executar contingències independents amb PyCOMPSs no
és, per si mateix, una novetat demostrada.

## Decisions de l'usuari que s'han de respectar

- Conversa i explicacions en català; avançar sense demanar confirmacions rutinàries.
- **La xarxa només es modifica desactivant els elements de la contingència.**
  No canviar slack, setpoints, redispatch, OPF, connexions ni afegir components
  artificials per aconseguir convergència o passar el filtre EMT.
- **Una no-convergència observada del power flow és una situació perillosa**
  i es classifica com a `failure`. És el criteri adoptat, no una prova matemàtica
  d'inexistència de solució. Una excepció sense resultat real del PF és `unknown`.
- Qualsevol prova enviada per l'assistent: **`gp_debug`, un node i un cas petit**,
  amb temps adequat fins a 120 minuts. Provar abans de reservar molts nodes.
  Els experiments multinode es preparen per a la cua general; l'usuari està
  enviant personalment el job gran actual. No cancel·lar-lo ni substituir-lo.
- Pot comunicar incidències als desenvolupadors de VeraGrid. Preparar evidència
  quan calgui; no enviar missatges externs sense instrucció explícita.
- **No tocar el format del paper**: classe IEEEtran, preàmbul, fonts, marges,
  autors i maquetació. Es poden canviar contingut i apartats. No inventar resultats.
- No ha demanat noves funcionalitats de traçabilitat ni auditories opcionals.
  Prioritzar validació, resultats i experiments necessaris.
- No fer push automàtic: els dos pushes anteriors es van fer a petició explícita.

## Repositori i estat de Git

Arrel: `/gpfs/home/bsc/bsc453248/git/probabilistic_contingencies`.
Remote: `git@github.com:CITCEA-UPC/probabilistic_contingencies.git`, branca `main`.

Últims commits vistos:

- `9c848d4` — Preserve contingency settings and classify PF nonconvergence as risk.
- `202786c` — refactor.
- `751fa32` — remove walclock.

Els dos primers ja es van pujar. A l'última consulta hi ha canvis **sense commit**:

- `main.py`, `pycompss_mn.sh`, `tests/test_pipeline.py`.
- `paper/main.tex` (nou esborrany conjunt).
- Nous: `contingencies/catalogue.py`, `tests/test_catalogue.py`,
  `tests/test_base_case_validation.py` i `validation/`.
- Aquest mateix `CONTEXT.md` s'afegeix ara.

Comprovar l'estat real; no descartar canvis existents ni assumir que tot està pujat.

## Mapa del codi

| Fitxer o carpeta | Funció |
| --- | --- |
| `main.py` | Preprocess, selecció de casos, tasques PyCOMPSs, persistència i informes |
| `config.py` | Xarxa i BD per defecte; injecta el submòdul VeraGrid a `sys.path` |
| `contingencies/catalogue.py` | Singles i combinacions dobles úniques |
| `contingencies/contingency.py` | Càlcul d'una contingència; sense accés SQLite |
| `contingencies/storage.py` | Lectura i transaccions SQLite exclusivament al mestre |
| `contingencies/result_diagnostics.py` | Classificació compartida i tolerància modal |
| `risk_analysis.py` | Resums, cobertura, límits de risc, CSV/JSON i gràfics |
| `modal_analysis.py` | Inspecció explícita d'un cas; no és una etapa automàtica |
| `local_exec.sh` | Mateix pipeline en sèrie, sense Slurm ni runtime COMPSs |
| `pycompss_mn.sh` | Entorn i enviament a MareNostrum |
| `validation/` | Referència escalar i refinament numèric del cas base |
| `tests/` | Tests de pipeline, emmagatzematge, política, risc, catàleg i validació |
| `docs/teoria.md` | Teoria i criteris; pot requerir actualització amb els últims experiments |
| `docs/buses_aislados_emt.md` | Diagnòstic de terminals, slack i filtre EMT |
| `docs/bsc.md` | Comandes BSC; algunes recomanacions antigues són massa categòriques |
| `outputs/` | BD, logs, informes i validacions; majoritàriament ignorat per Git |
| `paper/main.tex` | Manuscrit principal i bibliografia inline |
| `legacy/` | Scripts antics preservats; no són el pipeline vigent |

Submòduls: `VeraGrid_TenSyGrid/` i `stability_analysis/`. No s'han modificat
per esquivar les limitacions de la xarxa o dels models.

## Com funciona el pipeline

- `--preprocess`: només genera el catàleg. Sense flags: preprocess + pendents.
- **Atenció:** `config.CLEAR_DB_ON_START=True`; preprocess i execució sense flags
  poden esborrar i regenerar la BD seleccionada.
- `--ids 1,2`, `--all` o `--pending`: utilitzen la BD existent, sense regenerar.
  `--ids` i `--all` poden recalcular resultats ja existents.
- `--db` selecciona la BD. Al BSC passar una ruta absoluta expandida al login.
- Els workers reben definicions i retornen resultats; **no llegeixen ni escriuen SQLite**.
- El mestre envia totes les tasques i espera/desa lots en ordre d'enviament.
  Un cas lent pot retardar el desament del seu lot.
- `--batch-size 256` = resultats per transacció; **no limita concurrència**.
- Els lots confirmats sobreviuen a una interrupció; `--pending` reprèn el que falta.
  Això no equival a recuperació transparent de tasques en curs.
- Després es generen informes de **tota la BD**, també amb `--ids` o sense pendents.
  `--skip-risk` els omet; `--risk-out` canvia el destí.
- Una tasca engloba tot el càlcul d'una contingència. **No hi ha encara un DAG
  amb tasques separades de topologia, PF i modal.** És una possible extensió
  experimental, no una característica que puguem anunciar com a implementada.

`config.py` continua apuntant al **9 busos**. Això no afecta el job del 118:
les definicions de la seva BD contenen el camí del 118. No regenerar aquella
BD amb la configuració del 9.

## BSC: instruccions d'Eduardo i configuració vigent

- COMPSs: `COMPSs/3.4.post2609`; consultar versions amb `module spider COMPSs`.
- Python: mòdul `3.12.1`; ordre entorn Python → COMPSs → `.venv`.
- `gp_debug`: un node per a les nostres proves, màxim 120 minuts.
- `gp_bsccs`: màxim de temps consultat 2880 minuts (48 h).
- **No utilitzar `--wall_clock_limit`.**
- `--worker_working_dir=local_disk` i `--master_working_dir=local_disk`.
  La BD i els informes persistents continuen al disc compartit.
- Tracing: `TRACING="--tracing"` o `TRACING="-t"`. Comparar execucions amb i
  sense tracing si es vol quantificar el sobrecost; encara no hi ha aquesta mesura.
- El launcher actual ja compleix aquests punts.
- Valors actuals: `CPUS_PER_NODE=112`, `WORKER_IN_MASTER_CPUS=112`.
  El `sacct` pot comptabilitzar 224 CPU per node amb reserva exclusiva; no
  deduir la topologia física d'aquesta diferència.
- `COMPUTING_UNITS` reserva recursos per tasca; no demostra ús eficient d'aquells
  cores. L'òptim **no està mesurat**. No repetir com a fet la nota antiga de
  `docs/bsc.md` que afirma que 1 és sempre el més eficient.
- `NATIVE_THREADS=1` per defecte fixa OMP/MKL/OpenBLAS/NumExpr per evitar
  sobreassignació de fils. És una precaució nostra, no un requisit del compte
  ni una millora de rendiment demostrada.
- Límits consultats de `gp_bsccs`: 125 nodes / 28000 CPU per job; són sostres,
  no una recomanació de mida ni garantia de disponibilitat. Revalidar si cal.

L'usuari ha enviat aquesta comanda:

```bash
QOS=gp_bsccs EXEC_TIME=2880 NUM_NODES=20 \
CPUS_PER_NODE=112 WORKER_IN_MASTER_CPUS=112 \
COMPUTING_UNITS=8 \
./pycompss_mn.sh \
  --db "$PWD/outputs/databases/results_IEEE118busNREL.db" \
  --pending --batch-size 256
```

Job **49160098**: a l'última consulta estava **PENDING**, no executant encara.
La BD tenia les 28.680 files en `pending`. Reconsultar:

```bash
squeue -u "$USER"
scontrol show job 49160098
sacct -j 49160098 --format=JobID,State,Elapsed,AllocCPUS,NodeList,ExitCode
```

No declarar aquest job un experiment d'escalabilitat: és una única configuració.

## Criteris científics del codi actual

- Només es desactiven línies, generadors o transformadors de dos debanats.
- Es registra el nombre d'illes i el PF balancejat abans del retorn pel filtre EMT.
- `isolated_buses` és un nom històric: significa que un bus no compleix el
  mínim de connexions que exigeix el constructor EMT. **No equival a aïllament
  elèctric real**, que es registra separadament amb `n_islands`.
- PF balancejat o trifàsic observat no convergit → `failure`.
- Més d'una illa → `failure`, independentment d'altres errors.
- Excepció, filtre EMT sense altra fallada acreditada, modes absents o invàlids
  → `unknown`; els falsos per defecte d'una excepció no acrediten no-convergència.
- Modes finits, salut EMT correcta i màxim real ≤ `1e-6` → `stable` del pipeline.
  Màxim real > `1e-6` → `failure/modal_instability`.
- Es demanen 12 modes amb el camí ARPACK estàndard. No dir Hybrid/Block Arnoldi
  ni afirmar que es certifica tot l'espectre o l'estabilitat transitòria.
- No s'aplica OPF ni es comproven límits tèrmics o de tensió com a criteris de risc.
  `opf_needed=False`, `opf_converged=None` són camps llegats.
- La salut EMT exigeix arrays d'inicialització i convergència no buits i correctes.
- Configuració de producció: EMT `dt=1e-6`, durada `0.02 s`, tolerància `1e-6`;
  Floquet període `0.02 s`, pas `T/600`, 12 modes, ARPACK tol `1e-8`, seed 42.
  S'utilitzen models dinàmics genèrics: no presentar-los com un benchmark dinàmic
  IEEE independentment validat. Reconsultar el codi abans de publicar detalls.

## Catàleg i índex de risc

- Nou catàleg: singles i parelles **no ordenades**, sense duplicats.
- IEEE 118: 175 línies + 53 generadors + 11 transformadors = 239 elements;
  239 N−1 + 28.441 N−2 = **28.680** casos, sense incloure el cas base.
- La BD preparada té un índex únic sobre la definició. IDs 1–239 són singles,
  dobles des de 240. Els IDs no són universals entre BD o catàlegs regenerats.
- La BD antiga del 9 es conserva: 144 files històriques = 12 singles +
  132 dobles ordenades; representen 78 contingències úniques.
- `risk_analysis.py` tracta parelles úniques per defecte; el mode històric de
  files ordenades existeix per compatibilitat.
- Pesos il·lustratius: línies .05, transformadors .02, generadors .10.
  No són dades empíriques d'actius ni freqüències anuals demostrades.
- `R1_i=S_i`; `R2_i=sum_j p_j*S_ij`: vulnerabilitat ponderada condicional a
  perdre `i`. **No són esdeveniments de fallada per any**.
- Casos `unknown`: severitat 0/1 per construir límits inferior/superior.
  No són intervals estadístics de confiança. Informar cobertura ponderada i
  no ponderada; no fer rànquings definitius amb cobertura insuficient.

## Resultats i bloquejos coneguts

### IEEE 118

Entrada: `stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw`.
BD completa preparada: `outputs/databases/results_IEEE118busNREL.db`.

El cas base convergeix en PF i té una illa. El bus **SARGENTS** només té la
branca activa `71_73_1`, sense generador/càrrega/shunt actiu, i ja incompleix
el filtre EMT. Treure elements no augmenta el seu nombre de connexions;
per tant s'espera que aquesta limitació bloquegi la part modal del catàleg.
No modificar la xarxa per forçar-ne l'acceptació.

Prova petita job `49157888`: línia 0, PF convergit, una illa, estat
`isolated_buses`, sense modes; ~2 s de càlcul. Artefactes a
`outputs/validation/ieee118_initial/`.

Pas pendent prioritari: preparar/aclarir la reproducció mínima del bloqueig
amb VeraGrid. Distingir limitació del constructor, possible bug i problema
matemàtic real; **no s'ha demostrat singularitat només amb el recompte**.

### IEEE 9 i qüestió de slack

BD històrica: `outputs/databases/results_IEEE_9_Bus.db`.
Classificació única amb el criteri PF actual: 52 `failure`, 6 `stable`,
20 `unknown` (cobertura 74,4%); reconsultar abans de citar.

En una prova de desconnexió del generador del bus slack (cas històric 109),
VeraGrid manté el bus slack i retorna PF convergit amb injecció neta sense
generador actiu. És una qüestió de convenció/model a aclarir; l'usuari ha
prohibit reassignar el slack. No donar aquell diagnòstic experimental com a
correcció aplicada. Veure `docs/buses_aislados_emt.md`, especialment secció 8.

## Validació numèrica ja feta

Artefactes: `outputs/validation/ieee9_base_case/`.

- `validation/linear_reference.py`: operador real de Floquet per `x'=a*x`,
  `a=-2,+2`, passos 100/200/400/1200. Signe correcte i error decreixent.
  La història inicial de derivada tangent és zero i produeix un biaix de
  primer pas: convergència observada de primer ordre. **No afirmar ordre dos**
  només perquè l'integrador sigui trapezoïdal. No s'ha canviat el motor.
- `validation/base_case.py`: cas base sense contingència, sense canviar slack;
  PF/PF3, salut EMT, residus dels eigenparells, tancament periòdic i comparació
  amb espectre dens del **mateix operador discret** (147 estats).
  Això verifica l'eigensolver, no independentment el model físic.
- Hi ha aproximadament tres modes gairebé neutres en l'espectre dens.
  No presentar el resultat com a estabilitat asimptòtica de tots els modes.

| Passos/període | Períodes previs | Error tancament estats | Residual màxim | Distància màxima μ seleccionats-dens |
| --- | --- | --- | --- | --- |
| 600 | 1 | 6.59e-5 | 4.07e-12 | 5.71e-8 |
| 1200 | 1 | 3.31e-5 | 5.73e-12 | 7.74e-9 |
| 1200 | 10 | 4.49e-7 | 2.86e-9 | 5.82e-7 |

JSON corresponents: `refinement/results/steps_600_settle_1.json`,
`refinement/results/steps_1200_settle_1.json`,
`settled/results/steps_1200_settle_10.json` sota aquella carpeta.
Les mateixes carpetes tenen trajectòries `.npz`.

Jobs de validació completats: `49158202` (base), `49158820` (refinament),
`49158947` (10 períodes), tots petits a debug. Un intent `49158738` va fallar
per arguments de camí amb espais; es va resoldre amb un symlink de nom sense
espais, sense alterar el fitxer de xarxa.

**El pipeline de producció continua amb un període; no s'ha canviat a 10.**
Queda pendent consolidar aquestes troballes a teoria/manuscrit i decidir si
cal millorar la preparació de l'òrbita amb una comprovació quantitativa.

Tests: l'última execució prèvia dels tests va passar 54 proves; això no vol dir
que s'hagin tornat a executar després de qualsevol canvi futur. Comanda:

```bash
python -m unittest discover -s tests
```

Les proves numèriques del motor necessiten l'entorn de dependències. No
confondre tests unitaris amb validació física o experiments d'escalabilitat.

## Paper: enfocament i estat

`paper/main.tex` s'ha reorientat com a **esborrany provisional**, amb títol
“Task-Based Contingency Assessment of Power Networks: Numerical Coverage and
Parallel Performance”. S'han preservat exactament preàmbul, autors i capçalera.

Estructura actual: introducció; semàntica científica; tasques i persistència;
disseny experimental; resultats pendents; limitacions; conclusions pendents.
Les figures/rànquings i conclusions anteriors no són evidència vàlida del
workflow revisat i no s'utilitzen al nou cos. Els fitxers originals de figures
continuen al repositori i el text anterior és recuperable amb Git.

S'han retirat afirmacions no sustentades sobre OPF, ~57.000 casos únics,
freqüències anuals de fallada, cascades, escalat quasi lineal i temps operatiu
inferior a 15 minuts. No recuperar-les sense evidència nova.

Antecedent verificat i afegit a bibliografia: Chen et al., eGrid 2018,
“A High Performance Computational Framework for Dynamic Security Assessment
under Uncertainty”, DOI `10.1109/eGRID.2018.8598684`.
Font primària: https://www.pnnl.gov/publications/high-performance-computational-framework-dynamic-security-assessment-under-uncertainty
El manuscrit ja cita Konstantelos et al., IEEE TSG 2017, plataforma DSA paral·lela.
No s'ha completat una revisió exhaustiva de novetat.

Comprovacions fetes: preàmbul/autors/capçalera sense canvis, cites amb claus
existents, entorns LaTeX equilibrats i `git diff --check` correcte.
Compilació resolta el 17 de novembre de 2026: el mòdul `texlive/20260813`
proporciona `latexmk`, els motors i les fonts Times. S'han instal·lat amb
`tlmgr --usermode --usertree "$HOME/texmf"` els paquets `sttools`, `xurl`,
`orcidlink`, `svg`, `trimspaces` i les dependències. Cal exportar
`TEXMFHOME="$HOME/texmf"`: el valor per defecte del TeX Live compartit apunta
a la instal·lació compartida. `.vscode/latexmk.sh` configura PATH i TEXMFHOME;
`.vscode/settings.json` el fa servir per compilar amb LaTeX Workshop.
Verificat amb `/bin/bash ../.vscode/latexmk.sh -g -pdf -synctex=1
-interaction=nonstopmode -halt-on-error -file-line-error main.tex` des de
`paper/`: generat `paper/main.pdf`, 4 pàgines, sense errors de compilació;
només avisos Underfull hbox. No s'ha canviat el manuscrit ni la plantilla.

## Següents passos acordats

1. Aclarir el bloqueig EMT del 118 amb una reproducció mínima, sense tocar la xarxa.
2. Consolidar la validació del 9: què s'ha verificat i quines limitacions queden.
3. Quan el job 118 acabi, revisar fallades, desconeguts i cobertura per etapa.
4. Preparar experiments HPC amb un conjunt fix i comparable: començar petit,
   després comparar 1/2/4 nodes a la cua general si hi ha prou feina.
5. Mesurar temps total, distribució de costos, throughput, persistència,
   node-hores i eficiència; separar espera de Slurm i execució.
6. Necessitem un workload que arribi realment a EMT/modal. Si el 118 continua
   bloquejat, seleccionar un altre cas dinàmic documentat, no reparar-lo d'amagat.
7. Només després valorar separar etapes en tasques i comparar-ho amb la base
   actual. Augmentar N−k no resol una incompatibilitat EMT ni prova escalabilitat.

## Comandes útils per reprendre sense recalcular accidentalment

```bash
git status --short
squeue -u "$USER"

# Inspecció local d'un cas existent; preferir una còpia de BD per no sobreescriure resultats.
./local_exec.sh --debug --db /ruta/absoluta/copia.db --ids 13 --skip-risk

# Prova petita BSC, només quan calgui i sobre una BD de prova.
QOS=gp_debug EXEC_TIME=120 NUM_NODES=1 COMPUTING_UNITS=8 \
./pycompss_mn.sh --db /ruta/absoluta/prova.db --ids 13 --skip-risk
```

Comprovar què representa l'ID a la BD escollida abans de calcular-lo. Les BD
originals i la BD del job actiu no són espais de proves.

En aquesta sessió, les eines de shell amb sandbox van fallar repetidament amb
`bwrap`/namespaces; s'han utilitzat execucions escalades autoritzades per llegir
i modificar el repositori. És una limitació de l'entorn, no un motiu per canviar
el projecte. Si reapareix, comprovar el missatge i utilitzar el mecanisme d'aprovació.

## Manteniment d'aquest document

Actualitzar-lo després de decisions importants, canvis de criteris, nous resultats
validats o commits/pushes. Separar sempre **implementat**, **mesurat**, **pendent**
i **hipòtesi**. No interpretar aquesta fotografia com una autorització per enviar
jobs grans, modificar la xarxa o publicar contingut externament.


## Actualització: diagnòstic EMT del 118 (17/11/2026)

L'usuari prioritza consolidar la part modal i ha dit que cancel·larà el job
complet. Comprovar `49160098` abans de reprendre: no assumir que continua pendent.
S'ha afegit `validation/emt_topology.py`, diagnòstic del cas base sense canvis
de xarxa ni relaxació del motor. Prova `49161241`, gp_debug, un node,
15 minuts: completada, uns 14 s de càlcul.

Resultats: PF i PF3 convergits, una illa de 118 busos, slack MUSKNGUM intacte.
El validador original rebutja només les fases A/B/C de SARGENTS, amb una
única branca 71_73_1. Aquesta branca té B=.01178 i matriu C terminal diagonal
positiva de rang 3, diagonal 1.874845229622527e-05 (contracte pu EMT, no F SI).
El model PI inclou q=C*v i corrents capacitius: una branca no implica per
si sola tensió indeterminada. Possible criteri excessivament restrictiu del
validador, amb reproducció concreta. **No s'ha compilat ni integrat el DAE
complet, i no s'ha demostrat que funcioni sense aquest bloqueig.**

Artefacte: `outputs/validation/ieee118_emt_topology/base_case.json`;
script/logs al mateix directori. Explicació i comanda reproduïble a la
secció 9 de `docs/buses_aislados_emt.md`. Pas següent: comunicar/estudiar una
correcció justificada del validador, sense convertir globalment <2 en <1,
i després validar DAE, inicialització, periodicitat i modes abans del catàleg.


## Paquet per a desenvolupadors de VeraGrid

A petició de l'usuari s'ha creat `bug/`: informe anglès `report.tex` i
`report.pdf` (2 pàgines), `README.txt`, grid original `IEEE118busNREL.raw`,
`reproduce.py` autònom i dos JSON observats. ZIP per compartir:
`outputs/validation/veragrid_emt_bug.zip` (~138 kB). No s'ha enviat externament.

El nou script no importa res del nostre pipeline i crida la factoria pública
`build_emt_problem`, sense monkeypatch ni relaxació del validador. Inclou
`--minimal` per generar un cas sintètic independent de 2 busos, 1 generador
i 1 línia PI amb els mateixos R/X/B. No altera la grid IEEE original.

Job `49161934`, gp_debug, 1 node, completat: **tots dos casos reprodueixen
EmtTopologyError al constructor públic**, amb PF/PF3 convergits i C de rang 3.
Això amplia la comprovació anterior del validador en context mínim. Encara
no hi ha DAE inicialitzat ni modes, perquè el constructor s'atura al validador.
Entorn mesurat: RHEL 9.6, Python 3.12.1, NumPy 2.5.3, SciPy 1.18.1,
VeraGridEngine 6.7.0, submòdul net al commit
`2692754f16a097c9b387b8b5741ae8ebc87efd52`.

Compilació del report correcta. Per l'absència de `pdftex.map` global al BSC,
s'ha usat el mapa existent: `pdflatex -jobname=report
'\pdfmapfile{+cm.map}\input{report.tex}'` (sortida temporal fora del paquet).
El format de `paper/main.tex` no s'ha tocat en aquesta tasca.
Slurm confirma que el job gran `49160098` va quedar CANCELLED abans d'executar.


## Actualització de Git abans del push autoritzat

L'usuari ha demanat fer push del treball acumulat: catàleg únic, validació,
launcher, esborrany conjunt del paper, paquet `bug/` i documents de context.
Les 54 proves passen; sintaxi bash dels launchers correcta. El check de blancs
del codi i la documentació passa. La còpia byte a byte del RAW conserva
els blancs originals, que generen avisos de whitespace deliberadament.
La llista històrica de fitxers sense commit de més amunt queda superada per
aquest commit: consultar `git log -1` i `git status` per obtenir-ne l'estat final.
Hi ha canvis locals addicionals a `.vscode/settings.json` i `.vscode/latexmk.sh`
que no formen part d'aquest commit; es conserven sense modificar.


## Consolidació mentre s'espera resposta de VeraGrid

S'han afegit les mesures existents a `docs/teoria.md` (secció 8) i a
`paper/main.tex` (resultats de verificació amb taula). Sense nous jobs,
canvis del motor ni modificació del càlcul. Sense commit/push encara.
Preàmbul, autors i capçalera IEEE preservats.

Precisió important respecte del resum anterior: `settle_periods=10` és la
DURADA TOTAL fins al final de la captura, no deu períodes previs més un.
Se simula fins a 0.20 s i es captura [0.18,0.20] s. Els encapçalaments
històrics que diuen «períodes previs» s'han d'interpretar amb aquesta correcció.

La referència escalar dóna ordre observat ~1 per als dos signes; la resposta
amb història tangent inicial nul·la explica el primer pas. No s'ha notificat
una segona incidència ni canviat el motor. Millorar el tancament del cicle
(factor ~74 amb 1200 passos i durada 10 vs 1 període) NO millora el residual
ni la distància a l'espectre dens en aquella prova. No hi ha tolerància de
tancament físicament justificada ni validació independent de tot l'espectre.
El text del paper ja indica que el job 20 nodes es va cancel·lar sense executar.


## Prioritat del cas d'estudi confirmada per l'usuari

El paper s'ha de fer amb **IEEE 118 com a cas d'estudi principal**, tant per
resultats de contingències com per rendiment. El 9 busos serveix per treballar
en local i fer comprovacions numèriques. Pot aparèixer breument com a suport
metodològic, però no substituir els resultats del 118 ni ocupar una secció
experimental principal. La taula detallada del 9 s'ha retirat del manuscrit;
les mesures es conserven a `docs/teoria.md` secció 8 i als artefactes originals.
El cos del paper té ara subseccions pendents explícites per al cas base,
contingències i rendiment del 118. No s'ha substituït el cas principal per
una altra xarxa. Primer cal resoldre el bloqueig EMT i validar el 118 mateix.


## Preparació de la validació del 118 mentre s'espera VeraGrid

Afegit `validation/ieee118_mn.sh`, executable. `--dry-run` mostra la comanda
sense carregar mòduls ni enviar res. Cas base original, gp_debug, un node,
8 slots, 120 minuts per defecte; 600 passos/període, durada total 1 període,
12 modes. Variables STEPS_PER_PERIOD, SETTLE_PERIODS, MODES i EXEC_TIME.
Cada execució crea per defecte una carpeta de resultats nova. No usa SQLite.
**No s'ha enviat cap job d'aquest launcher.** Esperar resposta/correcció EMT.

Canvi a `validation/base_case.py`: el recompte simple de connexions només
es registra com a `connection_count_candidates`; decideix el constructor
original del motor (que ara encara rebutja SARGENTS). No hi ha monkeypatch
ni relaxació de validacions. El filtre de producció no s'ha modificat.
Protocol detallat a `docs/teoria.md` secció 9: primer funcionament base,
refinament temporal, durada de preparació, selecció de modes i finalment
poques contingències. El resum anterior del catàleg complet no s'ha de
reprendre abans de superar aquestes etapes.

Verificació: 54 tests passen, bash -n, dry-run i rebuig de paràmetres invàlids.
Canvis posteriors al push 7a3ee01 encara sense commit/push.


## Neteja autoritzada del repositori

L'usuari ha demanat eliminar COMPLETAMENT `datagen/` i `legacy/`, així com
auxiliars LaTeX i cachés Python, i afegir-ne les exclusions a Git.
S'han eliminat les dues carpetes (incloent fitxers locals que hi contenien).
README actualitzat: ja no formen part de l'estructura vigent; el mapa i
les referències de més amunt són històriques respecte d'aquestes carpetes.
**No s'ha tocat cap fitxer de docs/** en aquesta neteja; els seus canvis
pendents anteriors es mantenen. S'han conservat submòduls, .venv, .git,
outputs, PDFs finals, fonts LaTeX i figures. La neteja de cachés i auxiliars
s'ha limitat al codi i documents del projecte, fora d'aquelles ubicacions.
El .gitignore global incorpora auxiliars LaTeX i cachés d'eines Python;
__pycache__ i *.py[cod] ja hi eren. No s'ha reescrit l'historial de Git.
Les eliminacions estan al working tree, encara sense commit/push.


## Commit de neteja i protocol de rendiment preparat

A petició de l'usuari s'ha creat el commit **4116f3d** exclusivament amb
eliminacions de datagen/legacy, .gitignore i README. Els canvis de validació,
manuscrit, teoria, context i VS Code s'han mantingut fora d'aquest commit.
No s'ha fet push d'aquest commit.

Protocol preparat a `validation/PERFORMANCE.md`, sense modificar docs/.
Inclou prerequisits científics, pilot, CU, strong scaling 1/2/4 nodes,
persistència, tracing, repeticions, definicions de temps, còpies independents
SQLite i una plantilla de comanda explícitament pendent d'execució.
S'hi distingeixen mètriques disponibles i instrumentació del mestre pendent.
Cap benchmark ni job nou enviat. Primer resposta de VeraGrid i validació modal
real del cas base del 118; després poques contingències i pilot.


## Instrumentació mínima del mestre

Afegits a main.py temporitzadors perf_counter, sense canvis al càlcul físic,
a l'esquema SQLite o a la política de tasques/lots. Logs JSON amb prefix
PROCESS_PERFORMANCE: càrrega, enviament, espera, persistència i total, més
selected/submitted/committed/committed_batches/batch_size/completed.
El resum també surt si falla una etapa i només compta commits confirmats.
RISK_PERFORMANCE separa el temps de run_analysis i l'estat de completitud.
No s'escriu cap fitxer nou de mètriques. Total exclou preprocess, selecció
IDs, informes i runtime; espera inclou sincronització/recepció; persistència
inclou validació, serialització i transacció. En local el càlcul síncron queda
dins submit_s, que no s'ha d'interpretar com overhead de PyCOMPSs.

56 tests passen, incloent comprovació amb rellotge controlat de les etapes i
comptatge parcial quan falla una transacció. No s'ha fet prova a Slurm ni
benchmark. README i validation/PERFORMANCE.md actualitzats; docs/ intacte en
aquest pas. Canvis encara sense commit/push, a part del commit de neteja
4116f3d ja creat abans.


## Delimitació confirmada per l'usuari

`stability_analysis` és un altre treball. No n'importar models ni paràmetres,
ni continuar l'auditoria dels seus Excel per a aquest projecte. El cas actual
és el RAW del 118 amb els templates de VeraGrid que ja fem servir; la ruta
del RAW dins el submòdul no implica utilitzar l'altre estudi.



## Simplificació del càlcul modal

A petició de l'usuari s'ha simplificat contingencies/contingency.py:

- El recompte de connexions usa Counter i agrupa generadors/càrregues/shunts,
  amb la mateixa regla per a dispositius actius i terminals.
- El càlcul modal ja no construeix dos problemes EMT per substituir-ne un.
  El constructor actual SmallSignalStabilityEmtDriver accepta pf_results i
  pf_results_3ph: s'usen directament i es consulta el seu logger abans de run.
- Eliminats imports de Logger/build_emt_problem que només servien per aquella
  construcció redundant i comentaris obsolets sobre l'API/Arnoldi.
- Es conserven models, opcions numèriques, tractament d'errors i criteris.
  El paquet bug/ continua com a reproducció independent, sense modificar.

60 tests passen, incloent recepció dels dos PF al mateix driver, parada davant
errors de construcció, resultats absents i recompte de dispositius actius.
No s'ha repetit simulació amb motor real ni enviat cap job en aquest pas.
La revisió d'Excel de l'altre estudi també s'ha retirat del protocol de
rendiment. No s'ha tocat docs/ ni s'ha fet commit/push d'aquest refactor.


## Pipeline del 118 des de zero amb una sola comanda

main.py accepta ara `--grid /ruta/IEEE118busNREL.raw` per seleccionar xarxa
sense editar config.py, i `--reset-db` per forçar CLEAR_DB_ON_START=True en
memòria. El nom de BD es deriva del grid dins el directori de BD existent,
llevat que s'indiqui --db explícitament (té prioritat). Config.py al disc
continua al 9. Ometre --pending/--all/--ids per fer preprocess + càlcul +
informes en el mateix job; --preprocess continua fent només catàleg.

Les opcions de grid/reset es rebutgen si es combinen amb modes de processar
una BD existent. Es valida que el fitxer grid existeixi abans del reset.
64 tests passen, incloent reinici real d'una BD temporal amb default de
CLEAR_DB_ON_START=False. No s'ha tocat la BD real ni enviat cap job.
La comanda de 20 nodes a gp_bsccs amb --grid, --db i --reset-db és al README.
No reiniciar una BD mentre un altre job la fa servir. El reset no resol
el bloqueig EMT de SARGENTS.


## Publicació autoritzada dels canvis posteriors a la neteja

L'usuari ha demanat push després d'afegir la comanda única del 118.
Es publiquen el commit de neteja 4116f3d i un commit separat amb --grid,
--reset-db, temporitzadors, simplificació modal, validació i documents
pendents. 64 tests passen; bash -n i git diff --check correctes.
Preàmbul, autors i capçalera IEEE es conserven. Submòduls sense canvis.
VS Code continua fora del commit: settings.json i latexmk.sh són locals.
Consultar git log/status per l'identificador i l'estat final. No s'ha enviat
cap job ni modificat la BD real durant la publicació.
