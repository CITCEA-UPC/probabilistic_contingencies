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
   transitorio sano **y** `max(Re λ) ≤ STABLE_MAX_REAL_PART` (= 0).

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

## 7. Análisis modal: columna `eigenvalues` y `4.analyse.py`

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

Coste: el análisis de Floquet añade ~46 s por contingencia `ok` en el IEEE 9
(contingencia 13: 4.8 s → 51.2 s). Ajustable con `SMALL_SIGNAL_MODES` y
`STEPS_PER_PERIOD` en `2.process.py`.

Nota de interpretación: el criterio de estabilidad es **modal**: `stable=1`
exige que el transitorio corto sea numéricamente sano y que todos los modos
de Floquet tengan Re λ ≤ 0 (`STABLE_MAX_REAL_PART=0.0`). Los modos con
|μ| apenas por encima de 1 (Re λ ~ 0.05–0.15) pueden ser artefactos de la
aproximación de Arnoldi; la tabla y el gráfico de `4.analyse.py` permiten
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

### 7.3 Uso de `4.analyse.py`

```bash
python 4.analyse.py 13                     # tabla + ventana matplotlib
python 4.analyse.py 13 --save modes.png    # además guarda PNG
python 4.analyse.py 13 --no-show           # sin ventana (entornos headless)
```

Imprime el resumen de la contingencia (definición, status, islas, buses
aislados) y una tabla de modos ordenada de menor a mayor amortimiento
(Re λ descendente: el menos estable primero), con frecuencia
`f = |Im λ|/(2π)` y damping `ζ = -Re λ/|λ|` (mismas fórmulas que el motor).

El gráfico tiene la representación habitual de estabilidad small-signal, en
dos paneles:

1. **Plano s**: mitad derecha (Re λ > 0) sombreada en rojo = región
   INESTABLE; mitad izquierda en verde = ESTABLE; frontera sobre el eje
   imaginario; modos estables como puntos azules e inestables como × rojas,
   anotados con su índice de modo.
2. **Amortimiento vs frecuencia**: ζ contra f [Hz], con ζ < 0 sombreado en
   rojo (inestable).

Las contingencias sin `eigenvalues` (p. ej. `isolated_buses`) imprimen el
resumen y avisan de que no hay datos modales.
