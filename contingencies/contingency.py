"""
Mòdul compartit amb la lògica de càlcul d'una contingència individual.

Aquest mòdul calcula una contingència a partir de la definició rebuda, sense
accedir a SQLite. El mestre gestiona la persistència amb
``contingencies.storage``. És la font de veritat que fa servir ``main.py``, el punt d'entrada PyCOMPSs que embolcalla
``process_contingency`` com a ``@task`` i el llança en paral·lel (amb
``--preprocess`` genera la BD de contingències).

El mòdul és agnòstic de PyCOMPSs (no hi ha cap import de ``pycompss``), de
manera que també es pot fer servir en local sense tenir PyCOMPSs instal·lat.

El flux d'una contingència (vegeu ``docs/buses_aislados_emt.md``):

  1. Carrega el grid i aplica la contingència (desactiva línies, generadors i
     transformadors indicats).
  2. Classifica la topologia post-contingència: compta les illes i detecta
     busos amb menys de 2 connexions actives. El motor EMT rebutja aquests
     terminals; es classifiquen amb ``status='isolated_buses'``, que no
     demostra per si sol aïllament físic ni inestabilitat.
  3. Power flow balancejat i, només si l’EMT és viable, el trifàsic.
     Si no convergeixen, es classifica i s’atura, sense OPF ni canvi d’slack.
  4. Si tot és viable, adjunta els models EMT, executa un transitori curt de
     comprovació numèrica i calcula els autovalors de Floquet dominants. El
     veredicte d'estabilitat és modal (``max(Re lambda) <= 1e-6``).
"""

import ast
from collections import Counter
from itertools import chain
import json
import os
import time

import config
from contingencies.result_diagnostics import STABLE_MAX_REAL_PART

# Imports de VeraGridEngine per a simulacions
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import LogSeverity
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtTopologyError
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import (
    SmallSignalStabilityEmtDriver,
)
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import (
    SmallSignalStabilityEmtOptions,
)

# Templates per crear models EMT de cada tipus d'element
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_series_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template

# Enumeracions per configurar la simulació EMT
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
    SmallSignalEmtBuildTypes,
)

from typing import Any
import numpy as np

# Valors possibles de la columna `status` de contingency_results. L'esquema
# de la taula el gestiona el preprocess (main.py --preprocess, que crea la
# base de dades); vegeu docs/buses_aislados_emt.md per a la classificació completa.
STATUS_OK = "ok"
"""Calculada completament (PF balancejat + PF trifàsic + EMT). `stable` indica el resultat."""

STATUS_ISOLATED_BUSES = "isolated_buses"
"""El recompte de connexions rebutja algun terminal per a EMT. No prova
singularitat ni aïllament físic; islands es deriva de n_islands, errors=0."""

STATUS_PF_NOT_CONVERGED = "pf_not_converged"
"""El power flow balancejat no ha convergit; no es pot executar l'EMT."""

STATUS_PF3_NOT_CONVERGED = "pf3_not_converged"
"""El power flow trifàsic no ha convergit; no es disposa d’una solució
certificada per inicialitzar l’EMT i per això s’omet (mateix criteri que els exemples del
motor a VeraGrid_TenSyGrid/src/TensyGridEngine/emt)."""

STATUS_PF3_ERROR = "pf3_error"
"""El power flow trifàsic ha llençat una excepció (bug conegut del motor:
`apply_from_island` assumeix 4 valors per branca —N,A,B,C— però en xarxes
multi-illa el solver en retorna 3 i l'índex se surt → IndexError). No es
pot executar l'EMT; detall a `error_message`."""

STATUS_EMT_TOPOLOGY_ERROR = "emt_topology_error"
"""EmtTopologyError durant la construcció del problema EMT malgrat les
comprovacions prèvies de topologia."""

STATUS_SMALL_SIGNAL_ERROR = "small_signal_error"
"""L'EMT temporal ha acabat però l'anàlisi small-signal (autovalors de
Floquet) ha fallat; detall a `error_message`. La resta de resultats es desen
igualment."""

STATUS_EXCEPTION = "exception"
"""Excepció inesperada durant el càlcul (detall a `error_message`)."""

# Paràmetres de l'anàlisi small-signal (Floquet): nombre de modes dominants a
# calcular i passos d'integració per període de la xarxa.
SMALL_SIGNAL_MODES = 12
STEPS_PER_PERIOD = 600


def resolve_grid_path(path):
    """
    Resol el camí del grid desat a la base de dades.

    El camí es desa RELATIU al ROOT del repo (vegeu el preprocess a main.py) perquè la
    BD sigui portable entre màquines. Aquí el reconvertim en absolut per poder
    obrir el fitxer. Si el camí ja és absolut (BD antigues), es retorna tal qual.
    """
    if os.path.isabs(path):
        return path
    return os.path.join(config.ROOT, path)


def get_buses_with_few_connections(grid):
    """
    Retorna els busos amb menys de 2 connexions actives.

    El constructor del problema EMT (EmtProblemDae._validate_connections)
    exigeix que cada fase de cada bus estigui connectada a com a mínim 2
    elements amb model EMT. Un bus amb 0 o 1 connexions queda
    rebutjat pel recompte del validador del motor, que llença
    EmtTopologyError ("Floating bus phases detected"). Aquest recompte no
    demostra per si sol aïllament físic ni singularitat matemàtica.

    El criteri de recompte replica exactament el conjunt de dispositius als
    quals `attach_emt_models` adjunta models EMT:
      - Línies (grid.lines) i transformadors 2D (grid.transformers2w) actius:
        compten als dos extrems (bus_from i bus_to).
      - Generadors (grid.generators), càrregues (grid.loads) i shunts
        (grid.shunts) actius.

    Args:
        grid: MultiCircuit amb la contingència ja aplicada.

    Returns:
        list: Busos (objectes Bus) amb menys de 2 connexions actives.
    """
    counts = Counter()
    for branch in chain(grid.lines, grid.transformers2w):
        if branch.active:
            counts.update((branch.bus_from, branch.bus_to))
    for device in chain(grid.generators, grid.loads, grid.shunts):
        if device.active:
            counts[device.bus] += 1
    return [bus for bus in grid.buses if counts[bus] < 2]


def get_islands_info(grid):
    """
    Divideix el circuit numèric en illes i en retorna la informació.

    Una illa és un conjunt de busos connectats elèctricament entre si. Una
    contingència que talla línies o transformadors pot dividir la xarxa en
    diverses illes; en el cas extrem genera illes d'un sol node (busos
    aïllats), que són les que fan inviable la simulació EMT.

    Args:
        grid: Objecte MultiCircuit amb la contingència aplicada.

    Returns:
        tuple: (n_islands, island_sizes), el nombre d'illes i una llista amb
               el nombre de busos de cada illa.
    """
    nc = vge.compile_numerical_circuit_at(grid, t_idx=None)
    islands_list = nc.split_into_islands()

    return len(islands_list), [island.nbus for island in islands_list]


def run_small_signal_emt_analysis(grid, pf_results, pf_results_3):
    """
    Executa una simulació EMT curta (comprovació de salut numèrica).

    L'EMT s'inicialitza a partir de les solucions dels power flows (balancejat
    i trifàsic), que han d'haver convergit abans de cridar aquesta funció.

    ATENCIÓ: el driver EMT només simula els grups d'esdeveniments declarats a
    `grid.emt_events_groups` i, si no n'hi ha cap, no fa cap pas temporal i
    retorna resultats buits. Com que `np.array([]).all() == True`, això
    hauria marcat com a "OK" qualsevol contingència sense simular-la. Per
    això es declara un grup sense esdeveniments (cas base pur), igual que
    fan els exemples del motor (p. ex. emt_generator_models_compare.py), i es
    comprova explícitament que els arrays de resultats no siguin buits.

    Aquesta comprovació NO és un criteri d'estabilitat modal: un transitori de
    20 ms no pot revelar inestabilitats febles (p. ex. Re(lambda) = 2.5 1/s
    només creix un 5% en 20 ms). El veredicte d'estabilitat final el posa el
    criteri modal de `calculate_contingency`.

    Args:
        grid: MultiCircuit amb la contingència aplicada i els models EMT
              adjunts (vegeu `attach_emt_models`).
        pf_results: Resultats del power flow balancejat (han d'haver convergit).
        pf_results_3: Resultats del power flow trifàsic (han d'haver convergit).

    Returns:
        dict: {"emt_ok": bool, "error": bool}; `emt_ok` indica que almenys un
              grup s'ha simulat, que tots els grups s'han inicialitzat bé i
              que el solver ha convergit a tots els passos.

    Raises:
        EmtTopologyError: Si la topologia post-contingència té fases flotants
                          (busos amb menys de 2 elements connectats per fase).
    """
    if not grid.emt_events_groups:
        grid.add_emt_events_group(vge.EmtEventsGroup(name="base_case"))

    emt_options = EmtOptions(
        time_step=1e-6,
        simulation_time=0.02,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralAD,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Auto,
        verbose=0,
    )
    driver = EmtSimulationDriver(grid=grid, options=emt_options, pf_results=pf_results, pf_results_3ph=pf_results_3)
    driver.run()
    emt_results = driver.results

    # Guàrdia contra arrays buits: .all() sobre un array buit retorna True.
    well_init = np.asarray(emt_results.well_initialized, dtype=bool)
    converged = np.asarray(emt_results.converged, dtype=bool)
    emt_ok = bool(
        well_init.size > 0
        and converged.size > 0
        and well_init.all()
        and converged.all()
    )

    return {
        "emt_ok": emt_ok,
        "error": False,
    }


def run_small_signal_eigenvalues(grid, pf_results, pf_results_3):
    """
    Calcula SMALL_SIGNAL_MODES exponents de Floquet (lambda=log(mu)/T).

    El driver construeix un únic problema EMT amb els dos power flows.
    Es captura un període amb pas T/STEPS_PER_PERIOD i s'usa el camí
    Arnoldi/ARPACK estàndard. Els errors de construcció s'eleven abans
    d'executar el càlcul; el caller els classifica com a small_signal_error.
    """
    period = 1.0 / grid.fBase
    emt_options = EmtOptions(
        time_step=period / STEPS_PER_PERIOD,
        simulation_time=period,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralAD,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Auto,
        verbose=0,
    )
    sss_options = SmallSignalStabilityEmtOptions(
        k=SMALL_SIGNAL_MODES,
        target_period=period,
        max_krylov_dim=max(30, 2 * SMALL_SIGNAL_MODES),
        ss_assessment_time=period,
        verbose=0,
        max_restarts=0,
        build_type=SmallSignalEmtBuildTypes.Arnoldi,
    )
    driver = SmallSignalStabilityEmtDriver(
        grid=grid,
        emt_options=emt_options,
        sss_options=sss_options,
        pf_results=pf_results,
        pf_results_3ph=pf_results_3,
    )
    error_entries = [entry for entry in driver.logger.entries if entry.severity == LogSeverity.Error]
    if error_entries:
        raise RuntimeError("; ".join(str(entry) for entry in error_entries))
    driver.run()

    if driver.results is None:
        raise RuntimeError("EMT small-signal analysis returned no results")

    return driver.results.eigenvalues


def _set_model_parameter(block: Any, base_name: str, model_name: str, value: float) -> None:
    """
    Fixa el valor d'un paràmetre d'un template EMT.

    Prova primer el nom sense sufix i després el nom llegat amb el sufix del
    model (`<base_name>_<model_name>`), per ser compatible amb les dues
    convencions de noms dels templates.

    Raises:
        KeyError: Si cap dels dos noms existeix al bloc.
    """
    available_names = {
        variable.name
        for variable in list(block.event_dict.keys()) + list(block.parameters.keys())
    }
    for candidate in (base_name, f"{base_name}_{model_name}"):
        if candidate in available_names:
            block.set_parameter_in_model(var_name=candidate, new_value=value)
            return
    raise KeyError(f"Parameter '{base_name}' was not found in block '{block.name}'")


def _set_constant_impedance_reactive_zip_coefficients(block: Any, model_name: str) -> None:
    """
    Configura un model ZIP com a impedància constant pura (a4=1, resta=0).

    S'utilitza per als shunts: tot el terme reactiu es modela com a
    impedància constant i no hi ha components de corrent ni potència
    constants.
    """
    for coefficient, value in (("a1", 0.0), ("a2", 0.0), ("a3", 0.0),
                               ("a4", 1.0), ("a5", 0.0), ("a6", 0.0)):
        _set_model_parameter(block, coefficient, model_name, value)


def _set_event_constant_by_name(block: Any, var_factory: Any, var_name: str, value: float) -> None:
    """
    Fixa una variable d'un bloc EMT com a constant, buscant-la pel nom.

    Cerca la variable (amb o sense el sufix del model) primer al event_dict i
    als paràmetres del bloc i després al api_obj_mapping, i en substitueix
    l'entrada per una constant del var_factory.

    Raises:
        KeyError: Si la variable no es troba enlloc del bloc.
    """
    suffix = f"_{block.name}"
    candidate_names = {var_name}
    if var_name.endswith(suffix):
        candidate_names.add(var_name[:-len(suffix)])

    for variable in list(block.event_dict.keys()) + list(block.parameters.keys()):
        if variable.name in candidate_names:
            block.event_dict[variable] = var_factory.add_const(value)
            return

    for variable in list(block.api_obj_mapping.values()):
        if variable is not None and variable.name in candidate_names:
            block.event_dict[variable] = var_factory.add_const(value)
            return

    raise KeyError(f"Variable '{var_name}' was not found in block '{block.name}'")


def attach_emt_models(grid):
    """
    Adjunta els models EMT a tots els dispositius del grid.

    Només reben model els dispositius actius: un dispositiu desactivat per la
    contingència no ha d'aparèixer al problema EMT (i, de fet, la validació de
    topologia del motor només compta connexions de dispositius amb model).
    Els models són:
      - Busos: template de bus trifàsic (sempre, per tenir les tensions).
      - Línies: PI-equivalent trifàsic sense neutre.
      - Generadors: template complet de generador convencional.
      - Transformadors 2D: transformador sèrie amb les seves R, X i tap.
      - Càrregues: RLC en estrella flotant (R sempre, L només si Q != 0).
      - Shunts: ZIP configurat com a impedància constant reactiva (vegeu
        `_set_constant_impedance_reactive_zip_coefficients`).

    Args:
        grid: MultiCircuit amb la contingència aplicada.
    """
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    for line in grid.lines:
        if line.active:
            model = get_pi_line_emt_template(
                vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True,
                name=f"{line.name}", numerical_damping_conductance=0.0,
            ).block
            set_emt_model(device=line, model=model, var_factory=grid.var_factory)

    for gen in grid.generators:
        if gen.active:
            model = get_complete_generator_template_emt(
                vf=grid.var_factory).block
            set_emt_model(device=gen, model=model, var_factory=grid.var_factory)

    for trafo in grid.transformers2w:
        if trafo.active:
            model = get_series_transformer_emt_template(
                vf=grid.var_factory, name=f"{trafo.name}",
                r=trafo.R, x=trafo.X, tap_module=trafo.tap_module,
            ).block
            set_emt_model(device=trafo, model=model, var_factory=grid.var_factory)

    for load in grid.loads:
        if load.active:
            model = get_shunt_rlc_combo_emt_template(
                vf=grid.var_factory, include_r=True,
                include_l=abs(load.Q) > 1.0e-15, include_c=False,
                phA=True, phB=True, phC=True,
                connection_type=ShuntConnectionType.FloatingStar,
                name=f"{load.name}_RL_emt",
            ).block
            set_emt_model(device=load, model=model, var_factory=grid.var_factory)

    for shunt in grid.shunts:
        if shunt.active:
            model = get_load_ZIP_emt_template(
                vf=grid.var_factory,
                phA=True,
                phB=True,
                phC=True,
                connection_type=None,
                name=f"emt_{shunt.name}",
                conventional_three_phase_base=True,
            ).block
            model_name = model.name
            phase_q_pu = -shunt.B / grid.Sbase / 3.0
            _set_constant_impedance_reactive_zip_coefficients(block=model, model_name=model_name)
            _set_event_constant_by_name(
                block=model,
                var_factory=grid.var_factory,
                var_name=f"omega_{model_name}",
                value=2.0 * np.pi * grid.fBase,
            )
            for phase in ("A", "B", "C"):
                _set_event_constant_by_name(
                    block=model,
                    var_factory=grid.var_factory,
                    var_name=f"P0_{phase}_{model_name}",
                    value=0.0,
                )
                _set_event_constant_by_name(
                    block=model,
                    var_factory=grid.var_factory,
                    var_name=f"Q0_{phase}_{model_name}",
                    value=phase_q_pu,
                )
            set_emt_model(device=shunt, model=model, var_factory=grid.var_factory)


def calculate_contingency(contingency):
    """
    Calcula una contingència i en retorna el resultat classificat.

    Flux d'execució:
      1. Carrega el grid i aplica la contingència (desactiva línies,
         generadors i transformadors indicats).
      2. Classifica la topologia post-contingència: compta les illes i
         detecta els busos amb menys de 2 connexions actives que el motor
         EMT rebutja. Es classifiquen sense afirmar singularitat matemàtica
         ni aïllament físic; el nombre d’illes es desa separadament.
      3. Executa el power flow balancejat i, només si l'EMT és viable, el
         trifàsic (amb try/except per un bug conegut del motor a
         apply_from_island). Si algun no convergeix, no s'executa l'EMT
         perquè s'inicialitzaria amb una solució no física (criteri seguit
         per tots els exemples EMT del motor).
      4. Si la topologia és vàlida i els power flows han convergit, adjunta
         els models EMT, executa un transitori curt de comprovació numèrica
         (declarant un grup d'esdeveniments, sense el qual el driver EMT no
         simula res) i calcula els autovalors de Floquet. `stable` és cert
         només si el transitori és numèricament sa I tots els modes tenen
         Re(lambda) <= 0 (criteri modal).

    Args:
        contingency: Diccionari amb la fila de la contingència a la BD
                     (grid_path, lines, generators, transformers).

    Returns:
        dict: Resultat amb les claus powerflow_converged, stable, islands,
              errors, calculated, execution_time, isolated_buses, n_islands,
              status i error_message.
    """
    tic = time.perf_counter()
    grid = vge.open_file(resolve_grid_path(contingency["grid_path"]))

    # Únic canvi sobre les dades elèctriques: desactivar els elements indicats.
    # Es mantenen slack, consignes i paràmetres tal com venen al fitxer.
    for line_id in ast.literal_eval(contingency["lines"]):
        grid.lines[line_id].active = False
    for gen_id in ast.literal_eval(contingency["generators"]):
        grid.generators[gen_id].active = False
    for trafo_id in ast.literal_eval(contingency["transformers"]):
        grid.transformers2w[trafo_id].active = False

    # Classificar la topologia post-contingència abans de simular res:
    # illes i busos aïllats (amb menys de 2 connexions actives).
    isolated_bus_names = [bus.name for bus in get_buses_with_few_connections(grid)]
    n_islands, island_sizes = get_islands_info(grid)

    # Power flow balancejat: és robust amb illes (les parteix internament) i
    # omple el camp powerflow_converged fins i tot en els casos degenerats.
    pf_results = vge.power_flow(grid)

    # L’estudi conserva la configuració de la xarxa: només desconnecta els
    # elements indicats. No reassigna l’slack ni busca un altre despatx amb OPF.
    # Les columnes OPF es mantenen per llegir les BD de versions anteriors.

    def make_result(status, stable=False, errors=False, error_message=None, eigenvalues=None):
        """
        Construeix el diccionari de resultats amb les dades comunes.

        `eigenvalues` és el vector complex amb els modes de Floquet; es
        serialitza com a JSON de parells [real, imag] per poder-lo desar a la
        columna TEXT de la base de dades (None si no s'han calculat).
        """
        return {
            "powerflow_converged": bool(pf_results.converged),
            "stable": bool(stable),
            "islands": bool(n_islands > 1),
            "errors": bool(errors),
            "calculated": True,
            "execution_time": time.perf_counter() - tic,
            "isolated_buses": isolated_bus_names,
            "n_islands": int(n_islands),
            "status": status,
            "error_message": error_message,
            "eigenvalues": None if eigenvalues is None else json.dumps(
                [[float(z.real), float(z.imag)] for z in eigenvalues]
            ),
            "opf_needed": False,
            "opf_converged": None,
        }

    # Cas 1: terminals rebutjats pel recompte de connexions del motor EMT
    # (EmtTopologyError "Floating bus phases detected"). Es classifica i
    # s'ometen el PF trifàsic i l'EMT; no es compta com a error del procés.
    # A més, evitar el PF trifàsic en xarxes amb illes esquiva un bug del
    # motor (IndexError a apply_from_island, vegeu STATUS_PF3_ERROR).
    if isolated_bus_names:
        return make_result(STATUS_ISOLATED_BUSES)

    # Cas 2: no convergeix el punt de funcionament post-contingència.
    # No s’intenta recuperar-lo amb redespatx ni amb un altre bus slack.
    if not pf_results.converged:
        return make_result(STATUS_PF_NOT_CONVERGED)

    # Cas 3: power flow trifàsic (només quan hi ha oportunitat de fer EMT,
    # perquè l'EMT s'inicialitza des d'aquesta solució). Es captura qualsevol
    # excepció: el motor té un bug conegut al mapatge de resultats per illes
    # que llença IndexError quan la mida dels arrays de branca no és
    # múltiple de 4 (p. ex. una illa amb 7 branques: Sf = 7x3 = 21).
    try:
        pf_results_3 = vge.power_flow3ph(grid)
    except Exception as exc:
        return make_result(
            STATUS_PF3_ERROR,
            errors=True,
            error_message=f"{type(exc).__name__}: {exc}",
        )

    if not pf_results_3.converged:
        return make_result(STATUS_PF3_NOT_CONVERGED)

    # Cas 4: topologia vàlida i power flows convergits: executar l'EMT.
    attach_emt_models(grid)
    try:
        emt_results = run_small_signal_emt_analysis(grid, pf_results, pf_results_3)
    except EmtTopologyError as exc:
        # Reserva per a topologies degenerades que el recompte simple de
        # connexions no anticipa (p. ex. models EMT que no cobreixen totes
        # les fases d'un bus).
        return make_result(STATUS_EMT_TOPOLOGY_ERROR, errors=True, error_message=str(exc))

    # Amb l'EMT temporal completat, calcular els autovalors de Floquet
    # dominants i desar-los per a l'anàlisi modal (modal_analysis.py). Si aquest
    # càlcul falla, la contingència es classifica amb un status propi però
    # es conserva la comprovació numèrica del transitori curt.
    try:
        eigenvalues = run_small_signal_eigenvalues(grid, pf_results, pf_results_3)
    except Exception as exc:
        return make_result(
            STATUS_SMALL_SIGNAL_ERROR,
            stable=emt_results["emt_ok"],
            errors=True,
            error_message=f"{type(exc).__name__}: {exc}",
        )

    # Veredicte d'estabilitat final: el transitori curt ha d'haver anat bé
    # numèricament I tots els modes de Floquet han de tenir Re(lambda) <= 0
    # (equivalent a |mu| <= 1). Sense modes calculats no es pot afirmar
    # estabilitat. El transitori de 20 ms sol no la detecta: una inestabilitat
    # feble (p. ex. Re(lambda) = 2.5 1/s) només creix un 5% en aquesta finestra.
    modal_stable = bool(
        eigenvalues.size > 0
        and np.max(eigenvalues.real) <= STABLE_MAX_REAL_PART
    )

    return make_result(
        STATUS_OK,
        stable=emt_results["emt_ok"] and modal_stable,
        errors=emt_results["error"],
        eigenvalues=eigenvalues,
    )


def process_contingency(definition):
    """Calcula una definició sense llegir ni escriure SQLite.

    El mestre carrega la definició, l'envia al worker i desa el resultat.
    Les excepcions de càlcul es converteixen en resultats classificats;
    un error del runtime o de transport continua sent una tasca fallida.
    """
    contingency_id = definition["contingency_id"]
    tic = time.perf_counter()

    try:
        result = calculate_contingency(definition)
    except Exception as exc:
        # Qualsevol excepció no classificada es desa com a `exception` amb el
        # missatge complet, en comptes de valors per defecte poc informatius.
        print(f"Error processing contingency {contingency_id}: {type(exc).__name__}: {exc}")
        result = {
            "powerflow_converged": False,
            "stable": False,
            "islands": False,
            "errors": True,
            "calculated": True,
            "execution_time": time.perf_counter() - tic,
            "isolated_buses": [],
            "n_islands": None,
            "status": STATUS_EXCEPTION,
            "error_message": f"{type(exc).__name__}: {exc}",
            "eigenvalues": None,
            "opf_needed": False,
            "opf_converged": None,
        }

    return result
