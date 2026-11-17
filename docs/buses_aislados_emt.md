# Buses aislados y el error "Floating bus phases" en el análisis EMT de contingencias

## 1. Síntoma

Al procesar ciertas contingencias (p. ej. la contingencia 1 del IEEE 9 Bus,
que desconecta la línea 0), `2.process.py` fallaba con:

```
Error processing contingency 1: TopologyError: Floating bus phases detected
(each phase must be connected to at least 2 elements):
  - Bus 'bus 0' phase 'v_A' is floating (connected to 1 element(s): {'injection:2108de6c...'})
  - Bus 'bus 0' phase 'v_B' is floating (connected to 1 element(s): {'injection:2108de6c...'})
  - Bus 'bus 0' phase 'v_C' is floating (connected to 1 element(s): {'injection:2108de6c...'})
```

y la contingencia se guardaba en la base de datos con valores por defecto
poco informativos (`errors=1`, `powerflow_converged=0`, `islands=0`), que
además eran incorrectos: el power flow balanceado **sí** converge en ese caso
y el sistema **sí** queda partido en islas.

## 2. Causa raíz

En el IEEE 9 Bus, el bus 0 (slack) tiene exactamente **una rama**
(`branch 0`: bus 0 → bus 3) y **un generador** (`gen 0`). La contingencia 1
desconecta esa única rama, así que el bus 0 queda con un solo elemento
activo: el generador. Físicamente, el generador del slack queda desconectado
del resto de la red, formando una isla de un solo nodo.

El constructor del problema EMT del motor
(`VeraGridEngine/Simulations/EMT/problems/emt_problem_dae.py`,
`EmtProblemDae._validate_connections`) exige que **cada fase de cada bus
esté conectada a al menos 2 elementos con modelo EMT**. No es un capricho:
en el análisis nodal, la ecuación KCL de un nodo de fase que solo tiene una
fuente de corriente (el generador) y ningún camino de admitancia es
singular — la tensión de esa fase queda indefinida y la matriz del sistema
DAE no se puede resolver. Por eso el motor lanza `EmtTopologyError` antes de
intentar simular.

### Evidencia de que es un comportamiento diseñado del motor

- Existe un test unitario dedicado que **exige** este error:
  `src/tests/EMT/test_emt_system_validation.py::test_floating_phases_raises_emt_topology_error`.
- En los ~60 ejemplos EMT de
  `/home/alexandre/Desktop/git/VeraGrid_TenSyGrid/src/TensyGridEngine/emt`:
  - **Ninguno** cambia la topología (`active = False`) antes de simular; los
    eventos son cambios de parámetros (`EmtEvent`) sobre redes siempre
    conectadas (IEEE 9, Kundur, IEEE 39, two-bus).
  - **Todos** comprueban la convergencia del power flow (balanceado y, donde
    se usa, trifásico) y abortan con `RuntimeError` si no converge antes de
    construir el problema EMT (p. ej. `emt_ieee9.py:450-457`).
- El subsistema EMT **no** tiene gestión de islas (no hay ningún
  `split_into_islands` en `Simulations/EMT/`): no poda automáticamente los
  buses aislados.
- En cambio, las herramientas de régimen permanente del motor sí gestionan
  este fenómeno: el análisis de contingencias HELM usa
  `ignore_single_node_islands=True`
  (`Simulations/ContingencyAnalysis/Methods/helm_contingency_analysis.py:46`).
  Es decir, el motor reconoce que una contingencia puede dejar islas de un
  solo nodo y las filtra — pero solo en régimen permanente. Para estudios
  dinámicos (EMT) la responsabilidad recae en el flujo que llama.

**Conclusión:** no es un problema del fichero de red (el IEEE 9 Bus base es
válido) ni un bug del motor. Es una topología post-contingencia
legítimamente degenerada para EMT, y el pipeline de contingencias —que por
definición genera buses aislados e islas— debe detectarla y clasificarla en
vez de estrellarse.

Comprobación experimental con la contingencia 1:

```python
grid.lines[0].active = False
nc = vge.compile_numerical_circuit_at(grid, t_idx=None)
nc.split_into_islands()                              # → 2 islas: [1 bus, 8 buses]
nc.split_into_islands(ignore_single_node_islands=True)  # → 1 isla: [8 buses]
```

Además, el power flow trifásico post-contingencia **no converge**
(`power_flow3ph → converged=0`), que es justo lo que los ejemplos del motor
usan como condición para abortar antes del EMT.

## 3. Cambios realizados

### 3.1 Nuevas columnas en `contingency_results`

| Columna | Tipo | Contenido |
|---|---|---|
| `isolated_buses` | TEXT (JSON) | Nombres de los buses con < 2 conexiones activas tras aplicar la contingencia (`[]` si no hay). |
| `n_islands` | INTEGER | Número de islas del circuito numérico post-contingencia. |
| `status` | TEXT | Clasificación del resultado (ver tabla abajo). |
| `error_message` | TEXT | Mensaje de la excepción, si la hubo. |
| `eigenvalues` | TEXT (JSON) | Pares `[real, imag]` de los autovalores de Floquet dominantes (dominio s), calculados con `SmallSignalStabilityEmtDriver`. NULL salvo en `status='ok'`. |

Valores de `status` (constantes en `2.process.py`):

| status | Significado | ¿Se ejecuta EMT? | errors |
|---|---|---|---|
| `pending` | Generada por el preprocess, aún no calculada. | — | — |
| `isolated_buses` | La contingencia deja buses con < 2 conexiones; topología EMT inviable. | No | 0 |
| `pf_not_converged` | El PF balancejado no converge. | No | 0 |
| `pf3_not_converged` | El PF trifásico no converge (el EMT se inicializaría con una solución no física). | No | 0 |
| `pf3_error` | El PF trifásico lanzó una excepción (bug conocido del motor en `apply_from_island`, ver §6). | No | 1 |
| `emt_topology_error` | `EmtTopologyError` pese a las comprobaciones previas (red de seguridad). | Sí (falla) | 1 |
| `small_signal_error` | El EMT temporal acabó pero el análisis de Floquet (autovalores) falló; `stable` conserva solo la comprobación numérica del transitorio (criterio débil). | Sí (SS falla) | 1 |
| `ok` | Cálculo completo; `stable` = transitorio corto numéricamente sano **y** todos los modos de Floquet con Re λ ≤ 0; `eigenvalues` guarda los modos. | Sí | 0 |
| `exception` | Excepción inesperada; detalle en `error_message`. | — | 1 |

Nota semántica importante: un caso `isolated_buses` **no es un fallo del
proceso** (`errors=0`): es un resultado válido y clasificable. La
contingencia desconecta físicamente un bus y eso es información, no un error.

### 3.2 Esquema compartido entre los dos scripts

No se ha introducido ningún módulo auxiliar: el esquema de la tabla y la
migración viven en `1.preprocess.py` (`RESULT_COLUMNS` + `ensure_schema`,
que añade con `ALTER TABLE` las columnas que falten a una BD antigua sin
perder datos), y la lógica de detección/clasificación vive en
`2.process.py`. `1.preprocess.py` siempre se ejecuta antes que
`2.process.py`, así que cuando este procesa una contingencia la tabla ya
tiene todas las columnas.

El criterio de detección es `get_buses_with_few_connections(grid)` en
`2.process.py`, que replica exactamente el conjunto de dispositivos que
reciben modelo EMT en `attach_emt_models` (líneas y trafos 2D activos en
ambos extremos, generadores, cargas y shunts activos). Esta función ya
existía en `2.process.py` pero **nunca se llamaba**; ahora se usa en la
etapa de procesamiento.

### 3.3 `1.preprocess.py`

- Crea la tabla con las columnas nuevas (vía `ensure_schema`) y es el
  propietario del esquema (`RESULT_COLUMNS`).
- Se mantiene deliberadamente **rápido y sin cálculos sobre el grid**: solo
  enumera e inserta las definiciones de contingencias con
  `status='pending'`. Se ejecuta en serie antes de lanzar el array de jobs,
  por lo que la detección de buses aislados **no** se hace aquí, sino en
  `2.process.py`, que es el script que se ejecuta en paralelo (un proceso
  por contingencia en local con `xargs -P`, o un task de array en Slurm).
- Inserta cada fila en una única conexión (más rápido que abrir una por
  contingencia) y hace commit al final.
- Import limpio (`import VeraGridEngine.api as vge`, coherente con
  `2.process.py`; `config.py` ya inyecta la ruta).

### 3.4 `2.process.py`

Aquí es donde se detectan los buses aislados, contingencia a contingencia y
en paralelo. Nuevo flujo en `calculate_contingency`, con el orden de
comprobaciones siguiente (de más barato/determinista a más caro):

1. Aplicar la contingencia.
2. `get_buses_with_few_connections` + `get_islands_info` (nº de islas y
   tamaños) → si hay buses aislados: `status='isolated_buses'`,
   `islands=1`, `stable=0`, `errors=0`, y **no** se ejecutan ni el PF
   trifásico ni el EMT (además de ser inviables, evita el bug del motor
   descrito en §6).
3. PF balancejado (robusto con islas) → si no converge:
   `pf_not_converged`.
4. PF trifásico, envuelto en `try/except`: excepción → `pf3_error` (bug del
   motor, §6); no convergencia → `pf3_not_converged` (antes el script ni
   siquiera miraba la convergencia del trifásico).
5. Solo entonces: `attach_emt_models` (extraído a su propia función; ahora
   los shunts también se filtran por `active`) y EMT temporal, declarando un
   grupo de eventos `base_case` (sin él, el driver no simula nada, ver §7.2)
   y capturando `EmtTopologyError` como red de seguridad
   (`emt_topology_error`).
6. Con el EMT temporal completado, `run_small_signal_eigenvalues` calcula
   los `SMALL_SIGNAL_MODES=12` autovalores de Floquet dominantes con
   `SmallSignalStabilityEmtDriver` (periodo = 1/fBase, 600 pasos por
   periodo, Arnoldi por bloques) y se serializan en `eigenvalues`. Si este
   paso falla: `small_signal_error` y `stable` conserva solo la comprobación
   numérica del transitorio. El veredicte final de `stable` es modal:
   transitorio sano **y** `max(Re λ) ≤ STABLE_MAX_REAL_PART` (= 1e-6).

Otros cambios:

- `save_results_to_db(contingency_id, result)` guarda también las columnas
  nuevas (`isolated_buses`, `n_islands`, `status`, `error_message`,
  `eigenvalues`).
- `main()`: en caso de excepción guarda `status='exception'` y el mensaje
  completo en `error_message`, en vez de valores por defecto engañosos.
- Se eliminó `detect_islands` (sustituida por `get_islands_info`, que
  devuelve el recuento y los tamaños sin compilar dos veces) y el import
  sin usar de `cast`.
- Docstrings y comentarios en todas las funciones explicando el porqué.

## 4. Cómo consultar estos casos en la base de datos

Mientras una contingencia no se procesa, `status='pending'` y
`isolated_buses` es NULL; las columnas de resultado se rellenan al ejecutar
`2.process.py`.

```sql
-- Contingencias procesadas que aíslan algún bus (EMT inviable):
SELECT contingency_id, level, lines, generators, transformers, isolated_buses, n_islands
FROM contingency_results
WHERE status = 'isolated_buses';

-- Clasificación global de las contingencias procesadas:
SELECT status, COUNT(*) FROM contingency_results GROUP BY status;

-- Resultados "útiles" (EMT completado):
SELECT contingency_id, stable FROM contingency_results WHERE status = 'ok';

-- Fallos reales a investigar:
SELECT contingency_id, status, error_message
FROM contingency_results
WHERE errors = 1;

-- Pendientes de procesar:
SELECT COUNT(*) FROM contingency_results WHERE status = 'pending';
```

## 5. Caso de prueba: contingencia 1 del IEEE 9 Bus

Antes: excepción `EmtTopologyError` → fila con `errors=1,
powerflow_converged=0, islands=0` (todo incorrecto salvo el fallo).

Después: `status='isolated_buses'`, `isolated_buses='["bus 0"]'`,
`n_islands=2`, `islands=1`, `powerflow_converged=1` (el balancejado sí
converge), `errors=0`, y sin ejecutar un EMT destinado a fallar.

## 6. Segundo bug del motor: IndexError del PF trifásico con islas

### 6.1 Síntoma

Las contingencias 42 (`lines=[3,5]`), 55 (`lines=[4,6]`) y 65 (`lines=[5,3]`)
del IEEE 9 Bus acababan con `status='exception'`:

```
IndexError: index 21 is out of bounds for axis 0 with size 21
```

### 6.2 Causa raíz (dentro del motor)

El traceback lleva a `PowerFlowResults3Ph.apply_from_island`
(`Simulations/PowerFlow3ph/power_flow_results_3ph.py`, ~línea 477):

```
self.Sf_A[br_idx] = results.Sf[ka]
```

donde `ka` sale de `get_3p_indices(length_3p=len(results.Sf))` (mismo
fichero, líneas 19-31), que **asume 4 entradas por elemento** (N, A, B, C):
`n = length/4`, índices `4k, 4k+1, 4k+2, 4k+3`. En las islas afectadas el
solver devuelve los arrays de rama con **3 entradas por rama** (A, B, C, sin
neutro), así que los índices se salen del array.

Midas medidas con un monkey-patch temporal de `apply_from_island`:

| Caso | len(V) | len(Sf) | Resultado |
|---|---|---|---|
| Grid intacto (9 ramas, 1 isla) | 36 (9×4) | 36 (9×4) | OK |
| 1 línea fuera (8 ramas, 1 isla) | 36 (9×4) | 32 (8×4) | OK |
| Cont. 42: isla con slack de 7 ramas | 32 (8×4) | **21 (7×3)** | IndexError (índice 21) |

Con 21 entradas, `get_3p_indices` produce `ka = [1,5,9,13,17,21]` y el 21
está fuera de rango. Es decir: el ancho por rama de `Sf` es inconsistente
entre configuraciones (4 vs 3) y `apply_from_island` siempre asume 4. Riesgo
adicional latente: si la longitud fuera múltiplo de 4 pero el ancho real 3,
no habría excepción pero el mapeo quedaría desalineado y
`Sf/St/If/It/loading/losses` se guardarían con valores incorrectos sin aviso.

### 6.3 Por qué esas tres contingencias y no otras

Todas dejan un bus aislado (bus 2 en 42 y 65, bus 1 en 55) y una isla
principal **con slack y 7 ramas activas** → `len(Sf)=21` → crash. La
contingencia 1 no crashea porque su isla con slack tiene 0 ramas y la
principal no tiene slack (se descarta con "No slack nodes in the island").

### 6.4 Defensa en el pipeline

1. La clasificación topológica (buses aislados) se hace **antes** de llamar
   a `power_flow3ph`: 42/55/65 se clasifican como `isolated_buses` sin llegar
   a tocar el PF trifásico (1.1 s en vez de excepción).
2. `power_flow3ph` va envuelto en `try/except`: cualquier otro caso
   multi-isla que active el bug se guarda como `status='pf3_error'` con el
   mensaje en `error_message` (`errors=1`), en vez de tumbar el job.
3. Bug comunicado a los desarrolladores de VeraGrid con reproducción
   mínima, medidas y traceback.

## 7. Análisis modal: columna `eigenvalues` y `modal_analysis.py`

### 7.1 Cálculo y almacenamiento

Con el EMT temporal completado (`status='ok'`), `2.process.py` ejecuta
`run_small_signal_eigenvalues`: construye un problema EMT periódico
(paso = 1/fBase/600, tiempo = 1 periodo) y corre
`SmallSignalStabilityEmtDriver` (Floquet + Arnoldi por bloques,
`SMALL_SIGNAL_MODES=12` modos dominantes), siguiendo el ejemplo del motor
`emt_ieee9_small_signal.py`. Los autovalores del dominio s
(`lambda = log(mu)/T`) se serializan como JSON de pares `[real, imag]` en la
columna `eigenvalues`. Si este paso falla: `status='small_signal_error'`
conservando el veredicto temporal del EMT.

Coste: con la simulación real activada (ver §7.2), una contingencia `ok` del
IEEE 9 cuesta ~317 s: el transitorio EMT de 20 ms con `time_step=1e-6`
(20 000 pasos) ~270 s, y el análisis de Floquet ~45 s. Ajustable con el
`time_step` de `run_small_signal_emt_analysis` y con `SMALL_SIGNAL_MODES` /
`STEPS_PER_PERIOD` en `2.process.py`.

Validación de los modos inestables (contingencia 13): dos métodos
independientes confirman que la inestabilidad es **física**, no un
artefacto de Arnoldi:

- Transitorio EMT largo (2 s, `time_step=2e-5`): la simulación diverge con
  fallos de Newton (`converged=False`) y la envolvente RMS de las tres
  `omega_gen` crece ~×10⁴.
- Floquet refinado (1200 pasos/periodo, Krylov 60, 2 relanzamientos): los 6
  modos inestables persisten y se refuerzan (Re λ: 2.49→3.10, 0.14→0.82,
  0.05→0.58) y los estables se reproducen (p. ej. -0.731±7.43j →
  -0.978±7.54j). La configuración base (600 pasos, Krylov 30) es
  cualitativamente fiable (signos de Re λ robustos) pero cuantitativamente
  aproximada para los modos inestables.

Nota de interpretación: el criterio de estabilidad es **modal**: `stable=1`
exige que el transitorio corto sea numéricamente sano y que todos los modos
de Floquet tengan Re λ ≤ 0 (`STABLE_MAX_REAL_PART=1e-6`). Los modos con
|μ| apenas por encima de 1 (Re λ ~ 0.05–0.15) pueden ser artefactos de la
aproximación de Arnoldi; la tabla y el gráfico de `modal_analysis.py` permiten
inspeccionar los márgenes caso por caso.

### 7.2 Dos bugs del criterio `stable` anterior

Hasta esta revisión, `stable` se calculaba como:

```python
stable = bool(emt_results.well_initialized.all()) and bool(emt_results.converged.all())
```

Dos problemas, uno dentro del uso del motor y otro de numpy:

1. **El EMT no simulaba nada.** `EmtSimulationDriver.run()` itera
   `grid.emt_events_groups` y simula solo los grupos declarados
   (`emt_driver.py`, líneas 140–232; el código que creaba un grupo por
   defecto "simulation1" está comentado en el motor). El pipeline no
   declaraba ningún grupo → `ng=0` → **cero pasos temporales**, arrays de
   resultados vacíos y `values` sin columnas de datos. Todos los ejemplos
   del motor llaman `grid.add_emt_events_group(EmtEventsGroup(...))` antes
   de simular; ahora `run_small_signal_emt_analysis` también lo hace
   (grupo `base_case`, sin eventos: caso base puro).
2. **`.all()` sobre arrays vacíos devuelve `True`.** Con `ng=0`,
   `well_initialized` y `converged` eran arrays vacíos y la expresión
   anterior daba `stable=True` para cualquier contingencia que llegara al
   EMT, sin haber simulado un solo paso. Ahora se exige
   `size > 0` además de `.all()`.

Consecuencias del arreglo:

- `run_small_signal_emt_analysis` devuelve `{"emt_ok": ..., "error": ...}`:
  `emt_ok` es una comprobación de salud numérica del transitorio de 20 ms
  (inicialización + convergencia del solver), no un veredicto de
  estabilidad.
- El veredicto final en `calculate_contingency` es
  `stable = emt_ok and modal_stable`, con
  `modal_stable = max(Re λ) ≤ STABLE_MAX_REAL_PART` sobre los autovalores de
  Floquet (sin modos calculados no se afirma estabilidad).
- Las filas antiguas con `status='ok', stable=1` carecían de significado
  (el EMT era un no-op): hay que regenerar la base de datos y reprocesar.
- Un transitorio de 20 ms no puede sustituir al criterio modal de todos
  modos: una inestabilidad débil (Re λ = 2.5 1/s, τ ≈ 0.4 s) solo crece un
  ~5% en esa ventana, invisible para el solver.

### 7.3 Uso de `modal_analysis.py`

Este visor sustituye a `4.analyse.py`. Consulta la BD en modo de solo lectura;
`--db` permite seleccionar otra red sin editar `config.py`.

```bash
python modal_analysis.py 13
python modal_analysis.py 13 --db outputs/databases/results_IEEE_9_Bus.db --no-show
python modal_analysis.py 13 --no-show --save outputs/plots/modal_analysis/modes_13.png
```

El resumen separa la topología, el estado almacenado, el diagnóstico de riesgo
y el resultado de los modos calculados. Los campos NULL se muestran como
desconocidos. Un caso sin autovalores no tiene diagnóstico modal, aunque
`stable` contenga el valor de reserva False. Si hay varias islas, se conserva
el diagnóstico de fragmentación aunque los modos calculados no sean inestables.

`contingencies/result_diagnostics.py` centraliza el umbral `STABLE_MAX_REAL_PART=1e-6`,
utilizado por `contingency.py`, `risk_analysis.py` y el visor. La tabla y el
gráfico distinguen modos estables (Re λ < −tol), próximos al eje
(|Re λ| ≤ tol) e inestables (Re λ > tol). La proximidad al eje no certifica
marginalidad exacta ni demuestra que el signo sea ruido numérico. La banda
es absoluta; otros modos del espectro no alteran este umbral.

La tabla conserva el índice original y ordena por parte real descendente,
no por razón de amortiguamiento. Muestra `f = |Im λ|/(2π)` y
`ζ = −Re λ/|λ|`; para λ=0 el amortiguamiento es indefinido. Se validan la
estructura y la finitud de los autovalores antes de mostrarlos. Solo se
inspeccionan los modos almacenados: el visor no calcula ni certifica el
espectro completo.

Con `--no-show` se imprime la tabla sin abrir ventanas ni requerir matplotlib;
si además se pide `--save`, se genera el plano s con el backend Agg.

## 8. Incidencias reproducibles para consultar con VeraGrid (17-11-2026)

El estudio mantiene la red de entrada y únicamente desactiva los elementos
de la contingencia. No se reasigna el slack, no se cambian consignas y no
se busca un redespliegue de generación mediante OPF. El código del motor
no se ha modificado. Las descripciones antiguas de este documento sobre
singularidad o aislamiento deben interpretarse con la distinción de la
sección 2.7 de [teoria.md](teoria.md).

### 8.1 Inyección en el slack con su generador desactivado

**Red y versión:** `IEEE 9 Bus.gridcal`, submódulo VeraGrid en
`2692754f16a097c9b387b8b5741ae8ebc87efd52`.

**Única modificación de los datos eléctricos:**
`grid.generators[0].active = False` (contingencia 109 de nuestra BD).
El bus 0 conserva `is_slack=True` tal como viene en el fichero.
No tiene cargas, shunts ni otros generadores activos. Permanece conectado
al bus 3 mediante `branch 0` (`R=0`, `X=0.0576`, `B=0`).

**Resultado observado:** el PF balanceado y el trifásico indican convergencia,
pero el balanceado devuelve `Sbus[0] ≈ 71.7866817 + j10.1725392 MVA`.
El trifásico atribuye aproximadamente `23.9288956 + j3.3908533 MVA` a cada
fase de ese bus. Con el generador fuera, ese punto de funcionamiento
incluye una inyección para la que no hay un dispositivo activo en el bus.

**Consulta al motor:** ¿el contrato de `active=False` debe retirar también
la capacidad de inyección de ese bus aunque su flag de referencia permanezca?
Si el slack del PF representa una fuente ideal independiente del generador,
¿cómo debe indicar el motor que esa solución convergida no representa la
contingencia solicitada? El pipeline conserva el flag y no lo corrige
manualmente. Esto es un comportamiento reproducido que requiere confirmar
con los desarrolladores si es un bug o una convención del modelo de slack.

### 8.2 Rechazo EMT de un terminal conectado a una sola rama

En el mismo caso, hay una sola isla de nueve buses. El bus 0 tiene una
única rama activa y ninguna inyección activa. La validación de
`EmtProblemDae._validate_connections` rechaza sus fases A/B/C porque cada
una cuenta una conexión, por debajo del mínimo de dos.

**Consulta al motor:** ¿cómo se representa, sin dispositivos artificiales ni
cambios de topología, un terminal abierto conectado mediante una línea o
un transformador? El criterio de cardinalidad por sí solo no demuestra
singularidad; se necesita confirmar qué restricciones impone el solver
sobre las ecuaciones de ese terminal. La rama del caso concreto no tiene
susceptancia shunt, por lo que tampoco se presupone que la excepción pueda
eliminarse sin más y que el DAE resultante sea resoluble.

**Reproducción mínima de ambos comportamientos**, desde la raíz del repo:

```python
import config
from contingencies import contingency as ct
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae

grid = ct.vge.open_file(config.GRID_PATH)  # configurar IEEE 9 Bus.gridcal
assert grid.generators[0].bus is grid.buses[0]
assert grid.buses[0].is_slack
grid.generators[0].active = False

pf = ct.vge.power_flow(grid)
pf3 = ct.vge.power_flow3ph(grid)
print(pf.converged, pf.Sbus[0])
print(pf3.converged, pf3.Sbus_A[0], pf3.Sbus_B[0], pf3.Sbus_C[0])
print(ct.get_islands_info(grid))  # (1, [9])

ct.attach_emt_models(grid)
# La construcción se detiene en la validación, antes de la simulación:
EmtProblemDae(grid=grid, options=EmtOptions(), pf_results=pf,
              pf_results_3ph=pf3, logger=Logger())
```

Se había enviado el experimento aislado `49157034` a `gp_debug`, que
modificaba el slack en memoria para investigar el DAE. Se canceló al
aclararse el alcance del estudio. No se obtuvieron conclusiones sobre
estabilidad de ese experimento y no se cambió la BD original ni el motor.
La eliminación de la recuperación automática por OPF afecta solo al
pipeline del proyecto; no introduce una corrección en VeraGrid.


## 9. IEEE 118: extremo SARGENTS y rechazo previo al análisis modal

Diagnóstico iniciado el 17 de noviembre de 2026. No se cambia la red ni el
criterio del motor durante esta reproducción.

### Dos barreras distintas

1. `contingencies/contingency.py:get_buses_with_few_connections` detecta
   SARGENTS y devuelve `isolated_buses` después del PF balanceado. No se
   llega al PF trifásico ni a construir el DAE.
2. `EmtProblemDae._validate_connections` impone independientemente un mínimo
   de dos dispositivos conectados por fase. El nombre del error es
   `Floating bus phases detected`. El contador guarda una entrada por
   dispositivo, no por elemento eléctrico interno del modelo de ese dispositivo.

El caso base ya tiene esa condición. Aumentar los recursos, cambiar el batch
size o repetir contingencias no la resuelve.

### Datos originales y modelo PI

En `IEEE118busNREL.raw`, el bus 73 es SARGENTS. Su única rama activa es
`71_73_1`, con R=0.00866, X=0.0454 y B=0.01178 pu. No tiene generador,
carga ni shunt independiente activos. La susceptancia de la propia línea
no es cero y no equivale a añadir un dispositivo artificial.

El template `pi_line_emt_template.py` incluye los estados de carga de los
condensadores terminales y las relaciones `q=C*v`. En el extremo receptor,
el modelo impone `i_terminal=-i_serie+i_capacitivo`. KCL en un extremo sin
inyección externa exige `i_terminal=0`, de donde
`i_capacitivo=i_serie`. Si C es invertible, la tensión terminal puede evolucionar
según `C*dv/dt=i_serie`: tener una sola rama no demuestra que esa tensión
quede indeterminada. La matriz concreta de C debe comprobarse en la importación.

Esto señala una posible restricción excesiva del validador, no demuestra
por sí solo que todo el DAE de 118 buses se inicialice o tenga rango completo.
Tampoco justifica cambiar globalmente `<2` por `<1`: otros dispositivos y
terminales pueden requerir tratamientos distintos.

### Reproducción acotada

`validation/emt_topology.py` carga el caso base original, ejecuta PF y PF3,
recoge R/L/C del mapeo utilizado por EMT, adjunta los mismos modelos del
pipeline e invoca **el validador original** en un contexto mínimo. No compila
ni integra todo el DAE, no relaja validaciones y no modifica bases de datos.

```bash
python -m validation.emt_topology \
  --grid stability_analysis/stability_analysis/data/raw/IEEE118busNREL.raw \
  --out outputs/validation/ieee118_emt_topology/base_case.json
```

Se ha enviado el job pequeño `49161241`, `gp_debug`, un nodo, 15 minutos.
Script y logs en `outputs/validation/ieee118_emt_topology/`. Consultar el JSON
y el estado del job antes de afirmar sus resultados. La falta de resultado
modal sigue siendo `unknown` salvo otra condición de fallo observada.

### Comprobación siguiente necesaria

Si el validador rechaza el caso aun con capacitancia terminal de rango completo,
trasladar a los desarrolladores una reproducción con los parámetros y el error.
Una corrección debería reconocer modelos de terminal bien determinados y
seguir rechazando fases realmente desconectadas. Tras esa corrección deben
comprobarse construcción, inicialización, convergencia, cierre periódico y
modos del caso base, antes de reanudar el catálogo completo.


Resultado de `49161241`: prueba completada; PF y PF3 convergen, una isla
con 118 buses, slack MUSKNGUM sin cambios. El validador original rechaza
únicamente las tres fases de SARGENTS por tener una rama. La matriz C
terminal calculada por el mapeo real es diagonal con tres entradas
`1.874845229622527e-05`, estrictamente positivas y de rango completo.
Estos valores son del contrato por unidad EMT del motor, no faradios SI.
R es diagonal `0.00866` y L diagonal `0.00014451268832744099`.
El diagnóstico requiere ~14 s de cálculo (sin incluir arranque de Slurm).
El JSON está en `outputs/validation/ieee118_emt_topology/base_case.json`.
Se confirma el bloqueo por el contador, no un fallo del PF ni una contingencia
concreta. Queda pendiente la comprobación del DAE completo tras una corrección
justificada del validador; no se ha omitido ninguna validación.


Paquete autocontenido preparado en `bug/`, con informe inglés LaTeX/PDF,
RAW original, script y resultados. El nuevo job `49161934` comprobó el
**constructor público** `build_emt_problem` tanto en el 118 como en un caso
sintético independiente de dos buses: ambos reproducen el mismo rechazo,
con PF/PF3 convergidos y C terminal de rango 3. No se ha ejecutado integración
ni análisis modal. Esto amplía la prueba anterior del validador aislado.
