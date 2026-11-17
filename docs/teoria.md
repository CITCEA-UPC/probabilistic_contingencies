# Formulació Teòrica: Índex de Risc Probabilístic per a Anàlisi de Contingències

> Estructura actual: el càlcul i els diagnòstics compartits viuen a `contingencies/`; les BD i els informes es desen a `outputs/`. Els punts d’entrada continuen a l’arrel. Vegeu la guia d’execució al [README](../README.md).

## 1. Identificació del Problema Conceptual

### 1.1 Error Dimensional a la Fórmula Original

La fórmula original del paper defineix la freqüència N-2 com:

$$F_{i,j} = \lambda_i \cdot \lambda_j$$

**Problema:** Si $\lambda_i$ té unitats de [falles/any], llavors:

$$[\lambda_i \cdot \lambda_j] = \frac{1}{\text{any}} \cdot \frac{1}{\text{any}} = \frac{1}{\text{any}^2}$$

Això **NO és una freqüència** (que hauria de ser [1/any]), sinó una taxa al quadrat. L'índex de risc resultant $R_i$ té unitats incorrectes i no és interpretable físicament.

### 1.2 Interpretació Incorrecta de la Probabilitat Conjunta

El producte $\lambda_i \cdot \lambda_j$ representa la probabilitat que **ambdós components fallin en un període d'un any** (assumint independència), no la freqüència de fallada simultània.

Per a una doble contingència real, necessitem que el segon component falli **mentre el primer està fora de servei**, la qual cosa depèn del temps de reparació.

---

## 2. Nova Formulació Proposada

### 2.1 Canvi d'Enfocament: Vulnerabilitat Estructural vs. Probabilitat Temporal

**Reflexió clau:** El que estem fent NO és modelar la probabilitat que els components fallin en el temps. Estem **forçant la fallada** de cada component (i combinacions) i avaluant si la xarxa té problemes.

La pregunta real és:
- **N-1:** Si falla l'element $i$ sol → la xarxa té problemes?
- **N-2:** Si a més falla l'element $j$ → empitjora la situació?

Això és una **avaluació de vulnerabilitat estructural**, no una predicció probabilística temporal.

### 2.2 Nou Enfocament: Vulnerabilitat Ponderada per Probabilitat

En lloc de calcular la probabilitat conjunta de fallada (que requereix MTTR), proposem:

**Donat que l'element $i$ ha fallat, quin és el risc addicional si un altre element també falla?**

### 2.3 Definicions

**Severitat binària per als casos amb diagnòstic concloent:**

$$S_c = \begin{cases} 1 & \text{si la contingència } c \text{ causa fallada del sistema} \\ 0 & \text{altrament} \end{cases}$$

On "fallada del sistema" es defineix com qualsevol de:
- Inviabilitat del punt de funcionament segons les restriccions adoptades. La no-convergència numèrica del PF o de l’OPF, per si sola, no prova aquesta inviabilitat (secció 2.7).
- Inestabilitat de petit senyal (almenys un autovalor amb part real $\geq 0$)
- Formació d'illes elèctriques

Un cas que el model o el procediment numèric no poden avaluar conserva una severitat desconeguda, llevat que un altre criteri ja demostri fallada (per exemple, la formació d’illes). No s’assigna automàticament $S_c=1$ ni $S_c=0$ a aquests casos; vegeu la secció 2.7.

**Probabilitat anual de fallada:**

Per a un component $j$ amb taxa de fallada $\lambda_j$ [falles/any], la probabilitat que falli en un any és:

$$P_j = 1 - e^{-\lambda_j} \approx \lambda_j \quad \text{(per } \lambda_j \ll 1\text{)}$$

Aquesta és una **probabilitat adimensional** que utilitzem com a pes relatiu.

### 2.4 Índex de Risc de Vulnerabilitat

Definim el **risc de vulnerabilitat** de l'element $i$ com la suma de dos components independents:

$$\boxed{R_i = R_i^{(1)} + R_i^{(2)}}$$

on:

**Risc N-1 (vulnerabilitat individual):**

$$\boxed{R_i^{(1)} = S_i}$$

Mesura si l'element $i$ és crític per si sol. Val 1 si la fallada de $i$ causa fallada del sistema, 0 altrament.

**Risc N-2 (vulnerabilitat per combinacions):**

$$\boxed{R_i^{(2)} = \sum_{j \neq i} P_j \cdot S_{i,j}}$$

Mesura quantes combinacions amb altres elements causen fallada, ponderat per la probabilitat que aquests altres elements fallin. Si $i$ combinat amb un element $j$ molt propens a fallar ($P_j$ alt) causa fallada, és més preocupant que si ho fa amb un element molt fiable ($P_j$ baix).

**Segon element més crític:**

Per a un element $i$ donat, identifiquem quin és l'element $j$ més perillós quan es combina amb $i$:

$$\boxed{j^*_i = \arg\max_{j \neq i} \{ P_j \cdot S_{i,j} \}}$$

Això respon a la pregunta: "Si ja ha fallat $i$, quin és el segon element que seria més perillós que també fallés?"

**Per què descompondre?**

La descomposició permet respondre preguntes operatives concretes:

| Pregunta | Resposta |
|----------|----------|
| Quin element és més perillós en N-1? | $\arg\max_i R_i^{(1)}$ (o tots els que tinguin $R_i^{(1)} = 1$) |
| Quin element és més perillós en N-2? | $\arg\max_i R_i^{(2)}$ |
| Si falla $i$, quin $j$ és més crític? | $j^*_i = \arg\max_{j \neq i} P_j \cdot S_{i,j}$ |
| Quin element té el risc global més alt? | $\arg\max_i (R_i^{(1)} + R_i^{(2)})$ |

### 2.5 Comptatge de Contingències N-2

El preprocess genera dues files per parella: $(i,j)$ i $(j,i)$. El càlcul actual desconnecta els dos elements abans de simular; no modela una seqüència temporal de fallades. Per tant, aquestes files representen el mateix escenari físic final.

**Convenció per defecte a `risk_analysis.py`: una sola contribució per parella.** Es canonicalitza el conjunt d’elements desconnectats i s’aplica la fórmula de la secció 2.4:

$$R_i = S_i + \sum_{j \neq i} P_j \cdot S_{\{i,j\}}$$

Un diagnòstic concloent preval sobre un duplicat sense diagnòstic. Si els duplicats donen diagnòstics concloents contradictoris, el cas queda desconegut i s’informa del conflicte. Les combinacions N−1/N−2 absents, dins l’univers d’elements observats a la BD, també es tracten com a desconegudes.

**Comparació amb el comptatge històric:** `--n2-counting rows` conserva una contribució per fila N−2. Per a una BD completa amb dues files concordants per parella, això duplica el terme N−2 respecte al comptatge únic, però no el terme N−1. El rànquing del risc total pot canviar. Les files que falten per arribar a dues per parella s’inclouen com a desconegudes; les N−1 duplicades s’agrupen en tots dos modes.

Si en el futur es modelen fallades successives amb redispatch o dinàmica entre desconnexions, l’ordre podrà definir escenaris diferents i caldrà revisar aquesta convenció. El doble registre actual no proporciona aquesta informació temporal.

### 2.6 Índexs de Risc Normalitzats [0,1]

Per obtenir índexs entre 0 i 1, normalitzem cada component pel seu màxim global:

$$\boxed{RI_i^{(1)} = \frac{R_i^{(1)}}{\max_{k \in \mathcal{E}} R_k^{(1)}}} \quad \text{(Risc N-1 normalitzat)}$$

$$\boxed{RI_i^{(2)} = \frac{R_i^{(2)}}{\max_{k \in \mathcal{E}} R_k^{(2)}}} \quad \text{(Risc N-2 normalitzat)}$$

$$\boxed{RI_i = \frac{R_i}{\max_{k \in \mathcal{E}} R_k}} \quad \text{(Risc total normalitzat)}$$

**On:**
- $RI_i^{(1)}, RI_i^{(2)}, RI_i \in [0, 1]$: Índexs de risc normalitzats
- $\mathcal{E}$: Conjunt de tots els elements de la xarxa (línies, transformadors, generadors)

**Interpretació:**
- $RI_i^{(1)} = 1$: L'element més crític en fallada individual
- $RI_i^{(2)} = 1$: L'element més crític en combinacions N-2
- $RI_i = 1$: L'element amb el risc global més alt
- Valors propers a 0 indiquen baixa vulnerabilitat en la categoria corresponent

**Nota:** Com que $R_i^{(1)} \in \{0, 1\}$, el màxim $\max_k R_k^{(1)}$ també és 1 (si hi ha almenys un element crític). Per tant, $RI_i^{(1)} = R_i^{(1)}$.

### 2.7 Limitacions del model EMT i casos sense diagnòstic concloent

Cal distingir la **connectivitat elèctrica**, l’**admissibilitat del model EMT** i l’**estabilitat dinàmica**. Són propietats diferents:

- La fragmentació de la xarxa es determina a partir de les illes del circuit numèric (`n_islands > 1`). D’acord amb el criteri adoptat en aquesta formulació, això ja implica $S_c=1$, encara que no s’executi EMT.
- El motor EMT actual exigeix almenys dues connexions amb model per fase de bus. Aquesta validació pot rebutjar un bus terminal que continua connectat a la xarxa per una única línia després de desconnectar-ne el generador.
- La convergència del PF estableix un resultat numèric de règim permanent, però no acredita l’estabilitat dinàmica. Si no s’ha pogut completar l’anàlisi modal, aquesta estabilitat roman desconeguda.

Per tant, tenir menys de dues connexions amb model EMT **no demostra per si sol aïllament físic, singularitat matemàtica ni inestabilitat**. És el criteri de rebuig del motor actual; la seva justificació i el tractament dels busos terminals requereixen una revisió específica del model.

**Evidència de l’IEEE 9, execució del 17 de novembre de 2026.** El job `49153617` va processar les 144 files de contingències de `results_IEEE_9_Bus.db` (inclouen els dos ordres N−2):

| Resultat observat | Files | Interpretació |
|---|---:|---|
| `ok`, amb 12 autovalors finits i `stable=1` | 24 | Estables segons els modes calculats i el criteri numèric actual. |
| `isolated_buses`, amb diverses illes | 75 | Fragmentació real: severitat 1 segons el criteri adoptat. L’estabilitat modal no s’ha calculat. |
| `isolated_buses`, amb una sola illa de 9 busos | 45 | Topologia rebutjada pel filtre EMT, sense fragmentació de la xarxa. No hi ha diagnòstic modal. |

Dels 24 casos `ok`, 18 també tenen dues illes i 6 mantenen una sola illa. L’estabilitat modal desada no elimina la fragmentació: segons el criteri adoptat, els primers continuen tenint severitat 1.

Dels 45 casos connectats, 37 tenen PF balancejat convergit i 8 no. En aquests darrers, el retorn anticipat per topologia evita provar el recurs a OPF; aquesta execució no permet concloure que el redespatch sigui inviable.

En la revisió en memòria del validador real `EmtProblemDae._validate_connections`, els casos 109, 121 i 133 (desconnexió d’un generador) mantenen una única illa de 9 busos, però el motor rebutja, respectivament, els busos 0, 1 i 2 per tenir una sola connexió per fase. El cas 13 supera la validació. Aquesta comprovació valida el motiu del rebuig; no és una simulació dinàmica dels casos descartats.

**Conseqüències per a l’índex de risc.** El postprocessament anterior (`3.postprocess.py`, substituït per `risk_analysis.py`) assignava severitat 1 a tots els casos `isolated_buses` i també als errors de càlcul. Això barrejava fallades segons els criteris físics adoptats amb limitacions del model o del procediment numèric, i podia sobreestimar la vulnerabilitat física.

Abans d’interpretar els índexs com a vulnerabilitat física, cal:

1. Separar la classificació de fragmentació elèctrica de la de topologia no admesa pel model EMT, conservant el motiu del rebuig.
2. Conservar el resultat d’estabilitat com a desconegut quan no s’ha pogut calcular; un `stable=0` associat a un retorn anticipat no prova inestabilitat.
3. Informar de la cobertura de l’avaluació, global i per element, distingint casos pendents, errors i limitacions de model dels diagnòstics concloents.
4. Evitar que els casos desconeguts entrin automàticament com a fallades o com a casos sans. Si es vol quantificar-ne l’efecte, es poden donar límits inferior i superior del risc brut assignant-los, respectivament, severitat 0 i 1, amb els mateixos pesos i la mateixa convenció de comptatge N−2. Aquests límits expressen incertesa; no resolen els casos desconeguts. La normalització per un màxim global variable requereix una anàlisi separada i no preserva necessàriament aquests límits.

**Aplicació a `risk_analysis.py`.** El postprocessament aplica aquesta separació sense modificar la BD de simulació. La fragmentació (`n_islands > 1`) determina fallada segons el criteri adoptat. Un cas `ok` amb autovalors finits per sobre del llindar real de `1e-6` determina inestabilitat modal; un cas `ok`, sense errors, amb `stable=1` i autovalors finits dins del llindar es considera estable segons l’anàlisi calculada. Si `stable=0` però els modes no indiquen inestabilitat, el diagnòstic queda desconegut perquè el camp també pot reflectir fallada numèrica del transitori EMT. Els errors, la no-convergència i les limitacions topològiques sense fragmentació queden desconeguts.

Els CSV inclouen límits N−1, N−2 i totals, cobertura de diagnòstic per recompte i ponderada pels mateixos pesos del risc, i el segon element crític per a cadascun dels dos extrems. Aquest segon element és condicional a l’assignació dels desconeguts, no una identificació definitiva. Els gràfics mostren el risc brut confirmat i el marge addicional dels desconeguts, sense normalitzar ni presentar un rànquing definitiu. `scenarios.csv` conserva els IDs d’origen i el motiu del diagnòstic; `summary.json` registra pesos, llindar, cobertura i convenció N−2.

Amb el comptatge únic sobre aquesta BD, `risk_analysis.py` obté 78 escenaris: 48 amb fragmentació (fallada segons el criteri adoptat), 6 estables sense fragmentació i 24 desconeguts. La cobertura de diagnòstic global és del 69,2%; per als generadors és del 25%.

**Integració al pipeline.** `main.py` genera automàticament els informes de risc al mestre després de `compss_wait_on`, tant amb `pycompss_mn.sh` com amb `local_exec.sh`. `--skip-risk` omet aquesta etapa i `--risk-out` selecciona la carpeta de sortida. `--preprocess` només genera la BD. L’informe sempre cobreix tota la BD, també després de calcular només alguns IDs; els casos pendents continuen desconeguts. Si no queden contingències per processar, els informes es regeneren igualment. La sortida per defecte és `outputs/plots/risk_analysis/<nom de la BD>/`. Si falla la generació dels informes, l’error es propaga i els resultats de simulació ja desats es conserven.

**Persistència del càlcul.** El mestre carrega les definicions i és l’únic escriptor SQLite de l’execució. Els workers retornen l’ID i el resultat sense accedir a la BD. `contingencies/storage.py` valida la correspondència d’IDs i desa transaccions atòmiques; `--batch-size` controla quants resultats conté cada lot sense limitar la concurrència del càlcul. Els lots confirmats es conserven si una tasca del runtime o una escriptura posterior falla. En una primera execució, els casos no desats continuen pendents; en reprocessar, conserven el resultat anterior. Els informes només es generen després de desar tots els lots seleccionats.

**Inspecció modal.** `modal_analysis.py` permet consultar una contingència amb `--db`, imprimir-ne els modes i desar el pla s amb `--no-show --save`. Comparteix el llindar de `1e-6` i el diagnòstic amb el càlcul i el risc mitjançant `contingencies/result_diagnostics.py`. La topologia es mostra separadament del resultat modal; l’absència de modes queda com a desconeguda. La franja propera a l’eix no certifica marginalitat exacta ni soroll numèric, i la conclusió es limita als modes calculats.

Les dades històriques anteriors corresponen a files de la BD, no a escenaris físics únics; els recomptes depenen de la duplicació N−2 descrita a la secció 2.5. La cobertura es calcula sobre les combinacions dels elements que apareixen a la BD; no permet detectar dispositius que no hi apareguin en cap definició.

---

## 3. Pla de Treball per a la Reformulació del Paper

### 3.1 Canvis a la Secció de Metodologia

1. **Canviar l'enfocament de "freqüència de fallada" a "vulnerabilitat estructural"**
   - Explicar que estem forçant les fallades i avaluant la resposta del sistema
   - No estem modelant la probabilitat temporal de fallada

2. **Reformular l'equació del risc amb descomposició**
   - Presentar $R_i = R_i^{(1)} + R_i^{(2)}$ amb les dues components
   - Explicar que $P_j$ és un pes relatiu basat en fiabilitat
   - Introduir $j^*_i$ per identificar el segon element més crític

3. **Afegir secció sobre normalització**
   - Explicar la normalització pel màxim global per a cada component
   - Justificar per què és útil per a comparació i visualització

4. **Clarificar el tractament de contingències N-2**
   - Explicar que els dos registres actuals representen una mateixa desconnexió final
   - Comptar cada parella una vegada i declarar el mode per files només per a comparacions històriques

### 3.2 Canvis a la Secció de Resultats

1. **Recalcular els índexs de risc**
   - Aplicar la nova fórmula als resultats existents
   - Calcular $R_i^{(1)}$, $R_i^{(2)}$ i $R_i$ per separat
   - Identificar $j^*_i$ per als elements més crítics
   - Normalitzar pel màxim global

2. **Actualitzar les figures**
   - Gràfics separats per $RI^{(1)}$ (risc N-1) i $RI^{(2)}$ (risc N-2)
   - Gràfic combinat amb $RI$ total (barres apilades N-1 + N-2)
   - Taula amb $j^*_i$ per als top-N elements més crítics

3. **Reinterpretar els resultats**
   - Responder explícitament les tres preguntes operatives:
     - Quin element és més perillós en N-1?
     - Quin element és més perillós en N-2?
     - Si falla un element N-1, quin és el segon més crític?

### 3.3 Canvis a la Discussió

1. **Eliminar referències a "failure-events/year"**
   - Substituir per "vulnerabilitat relativa normalitzada"

2. **Mantenir la discussió sobre concentració de risc**
   - La distribució asimètrica del risc es manté
   - La identificació d'elements crítics és la mateixa

3. **Afegir avantatges de la nova formulació**
   - No necessita MTTR
   - Descomposició N-1/N-2 per a anàlisi detallada
   - Identificació del segon element més crític
   - Més fàcil d'interpretar (0-100% del màxim)
   - Reflecteix vulnerabilitat estructural, no predicció temporal

---

## 4. Exemple Numèric

### 4.1 Dades

Considerem una línia $i$ amb els següents resultats de simulació:
- Contingència N-1: $S_i = 1$ (causa fallada)
- Contingències N-2 amb 3 altres elements:
  - $j_1$ (línia): $\lambda_{j_1} = 0.05$, $S_{i,j_1} = 1$
  - $j_2$ (generador): $\lambda_{j_2} = 0.10$, $S_{i,j_2} = 1$
  - $j_3$ (transformador): $\lambda_{j_3} = 0.02$, $S_{i,j_3} = 0$

### 4.2 Càlcul dels Components del Risc

**Risc N-1:**
$$R_i^{(1)} = S_i = 1$$

**Risc N-2:**
$$R_i^{(2)} = \sum_{j \neq i} P_j \cdot S_{i,j} = 0.05 \cdot 1 + 0.10 \cdot 1 + 0.02 \cdot 0 = 0.15$$

**Risc total:**
$$R_i = R_i^{(1)} + R_i^{(2)} = 1 + 0.15 = 1.15$$

### 4.3 Identificació del Segon Element Més Crític

Per a la línia $i$, calculem el producte $P_j \cdot S_{i,j}$ per a cada $j$:

| Element $j$ | $P_j$ | $S_{i,j}$ | $P_j \cdot S_{i,j}$ |
|-------------|-------|-----------|---------------------|
| $j_1$ (línia) | 0.05 | 1 | 0.05 |
| $j_2$ (generador) | 0.10 | 1 | **0.10** |
| $j_3$ (transformador) | 0.02 | 0 | 0.00 |

$$j^*_i = j_2 \quad \text{(generador amb } P_{j_2} = 0.10\text{)}$$

**Interpretació:** Si la línia $i$ ja ha fallat, el segon element més perillós que també fallés seria el generador $j_2$, perquè té la probabilitat de fallada més alta entre els que causen fallada combinada.

### 4.4 Normalització

Suposem que el màxim global de $R^{(2)}$ és 0.25 i el màxim de $R$ és 1.50:

$$RI_i^{(1)} = \frac{1}{1} = 1.0 \quad \text{(la línia } i \text{ és crítica en N-1)}$$

$$RI_i^{(2)} = \frac{0.15}{0.25} = 0.60 \quad \text{(60% del risc N-2 màxim)}$$

$$RI_i = \frac{1.15}{1.50} = 0.767 \quad \text{(76.7% del risc global màxim)}$$

### 4.5 Anàlisi del Resultat

- **Contribució N-1:** $1 / 1.15 = 87\%$ del risc ve de la fallada individual
- **Contribució N-2:** $0.15 / 1.15 = 13\%$ del risc ve de combinacions
- **Segon element més perillós:** Generador $j_2$ (perquè té $\lambda$ més alta i causa fallada)

Això indica que la línia $i$ és crítica principalment per si sola, però també empitjora significativament quan es combina amb generadors propensos a fallar.

---

## 5. Comparació amb la Fórmula Original

| Aspecte | Fórmula Original | Nova Fórmula |
|---------|------------------|--------------|
| **Enfocament** | Freqüència de fallada temporal | Vulnerabilitat estructural |
| **Unitats de $F_{i,j}$** | [1/any²] (incorrecte) | N/A (no existeix) |
| **Pes N-2** | $\lambda_i \cdot \lambda_j$ | $P_j \approx \lambda_j$ |
| **Interpretació** | Freqüència esperada (falles/any) | Vulnerabilitat relativa |
| **Descomposició N-1/N-2** | No (barrejat) | Sí ($R^{(1)}$ i $R^{(2)}$ separats) |
| **Identificació de $j^*$** | No | Sí ($\arg\max$) |
| **Rang de $R_i$** | [0, ∞) | [0, 1 + N·λ_max] aprox. |
| **Normalització** | No | Sí, a [0,1] per component |
| **Dependència de MTTR** | Implícita (no declarada) | No necessària |
| **Interpretabilitat** | Difícil (valors com 1.47) | Fàcil (0-100% del màxim) |
| **Pregunta que respon** | "Amb quina freqüència fallarà?" | "Què passa si falla? I si a més falla un altre?" |

---

## 6. Preguntes Obertes per a Discussió

1. **Valors de $\lambda_i$ per component específic:**
   - Actualment usem valors genèrics per tipus
   - El framework permet assignar $\lambda_i$ individuals
   - Cal decidir si mantenim valors genèrics o busquem dades específiques

2. **Independència de fallades:**
   - Assumim que les fallades són independents
   - En realitat, pot haver-hi correlació (línies al mateix corredor, etc.)
   - Podríem introduir un factor de correlació si tenim dades

3. **Severitat no binària:**
   - Actualment $S_c \in \{0, 1\}$
   - Podríem definir $S_c \in [0, 1]$ basat en magnitud de la violació
   - Exemple: $S_c = \frac{\text{MW no servits}}{\text{MW totals}}$

4. **Pes del terme N-1 vs N-2:**
   - Actualment el terme N-1 té pes 1 (constant)
   - Podríem ponderar-lo per $\lambda_i$ si volem que elements més propensos a fallar tinguin més pes N-1
   - Alternativa: $R_i = \lambda_i \cdot S_i + \sum_{j \neq i} \lambda_j \cdot S_{i,j}$

5. **Comptatge únic vs. seqüència temporal:**
   - Per defecte comptem una vegada cada parella; el mode històric per files es manté explícit
   - Si es modelen fallades successives en el futur, caldrà representar l’ordre temporal
   - El canvi de pes relatiu N−1/N−2 pot modificar el rànquing total

---

## 7. Conclusions

La nova formulació corregeix l'error dimensional de la fórmula original i proporciona un sistema d'índexs de risc que:

- **Reflecteix vulnerabilitat estructural**, no predicció temporal
- **És adimensional** i normalitzat a [0, 1]
- **És interpretable**: percentatge de la vulnerabilitat màxima
- **No necessita MTTR** (evita el problema dimensional)
- **Pondera per fiabilitat**: combinacions amb elements propensos a fallar tenen més pes
- **Es descompon en N-1 i N-2**: permet anàlisi detallat per tipus de contingència
- **Identifica el segon element més crític**: $j^*_i$ per a cada element $i$

Aquesta formulació respon a les tres preguntes operatives clau:

1. **Quin element és més perillós en N-1?** → $\arg\max_i R_i^{(1)}$
2. **Quin element és més perillós en N-2?** → $\arg\max_i R_i^{(2)}$
3. **Si falla $i$, quin $j$ és més crític?** → $j^*_i = \arg\max_{j \neq i} P_j \cdot S_{i,j}$

És més rigorosa des del punt de vista conceptual i més fàcil de comunicar a operadors i planificadors de xarxes.
