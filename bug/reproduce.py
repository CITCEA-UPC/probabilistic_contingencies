"""Standalone reproduction: original EMT topology rejection, no patches.

Requires VeraGridEngine from the reported development checkout and its normal
Python dependencies. No contingency-project imports, PyCOMPSs, Slurm or database.
Default: supplied IEEE118 RAW. --minimal: independent synthetic two-bus case.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import scipy
import VeraGridEngine.api as vge
from VeraGridEngine.__version__ import __VeraGridEngine_VERSION__
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (DynamicIntegrationMethod,
    EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType)
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_problem_factory import build_emt_problem
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtTopologyError
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping import build_line_static_matrices
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_series_transformer_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

# Model attachment mirrors the application settings; no operating data changed.
def _set_model_parameter(block: Any, base_name: str, model_name: str, value: float) -> None:
    available_names = {variable.name for variable in list(block.event_dict.keys()) + list(block.parameters.keys())}
    for candidate in (base_name, f'{base_name}_{model_name}'):
        if candidate in available_names:
            block.set_parameter_in_model(var_name=candidate, new_value=value)
            return
    raise KeyError(f"Parameter '{base_name}' was not found in block '{block.name}'")

def _set_constant_impedance_reactive_zip_coefficients(block: Any, model_name: str) -> None:
    for (coefficient, value) in (('a1', 0.0), ('a2', 0.0), ('a3', 0.0), ('a4', 1.0), ('a5', 0.0), ('a6', 0.0)):
        _set_model_parameter(block, coefficient, model_name, value)

def _set_event_constant_by_name(block: Any, var_factory: Any, var_name: str, value: float) -> None:
    suffix = f'_{block.name}'
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
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)
    for line in grid.lines:
        if line.active:
            model = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name=f'{line.name}', numerical_damping_conductance=0.0).block
            set_emt_model(device=line, model=model, var_factory=grid.var_factory)
    for gen in grid.generators:
        if gen.active:
            model = get_complete_generator_template_emt(vf=grid.var_factory).block
            set_emt_model(device=gen, model=model, var_factory=grid.var_factory)
    for trafo in grid.transformers2w:
        if trafo.active:
            model = get_series_transformer_emt_template(vf=grid.var_factory, name=f'{trafo.name}', r=trafo.R, x=trafo.X, tap_module=trafo.tap_module).block
            set_emt_model(device=trafo, model=model, var_factory=grid.var_factory)
    for load in grid.loads:
        if load.active:
            model = get_shunt_rlc_combo_emt_template(vf=grid.var_factory, include_r=True, include_l=abs(load.Q) > 1e-15, include_c=False, phA=True, phB=True, phC=True, connection_type=ShuntConnectionType.FloatingStar, name=f'{load.name}_RL_emt').block
            set_emt_model(device=load, model=model, var_factory=grid.var_factory)
    for shunt in grid.shunts:
        if shunt.active:
            model = get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True, connection_type=None, name=f'emt_{shunt.name}', conventional_three_phase_base=True).block
            model_name = model.name
            phase_q_pu = -shunt.B / grid.Sbase / 3.0
            _set_constant_impedance_reactive_zip_coefficients(block=model, model_name=model_name)
            _set_event_constant_by_name(block=model, var_factory=grid.var_factory, var_name=f'omega_{model_name}', value=2.0 * np.pi * grid.fBase)
            for phase in ('A', 'B', 'C'):
                _set_event_constant_by_name(block=model, var_factory=grid.var_factory, var_name=f'P0_{phase}_{model_name}', value=0.0)
                _set_event_constant_by_name(block=model, var_factory=grid.var_factory, var_name=f'Q0_{phase}_{model_name}', value=phase_q_pu)
            set_emt_model(device=shunt, model=model, var_factory=grid.var_factory)


def make_minimal():
    """Separate synthetic case, not a reduction or modification of the IEEE118 file."""
    grid = vge.MultiCircuit(name="PI terminal reproduction", Sbase=100, fbase=50)
    source = vge.Bus(name="SOURCE", Vnom=138, is_slack=True)
    terminal = vge.Bus(name="TERMINAL", Vnom=138)
    grid.add_bus(source)
    grid.add_bus(terminal)
    grid.add_generator(source, vge.Generator(name="SOURCE_GEN", P=0, vset=1.0))
    grid.add_line(vge.Line(bus_from=source, bus_to=terminal, name="PI_TERMINAL",
                           r=.00866, x=.0454, b=.01178))
    return grid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid', type=Path, default=Path(__file__).with_name('IEEE118busNREL.raw'))
    parser.add_argument('--minimal', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('result.json'))
    args = parser.parse_args()
    start = time.perf_counter()
    grid = make_minimal() if args.minimal else vge.open_file(str(args.grid.resolve()))
    report = {'case': 'synthetic two-bus' if args.minimal else args.grid.name,
              'environment': {'os': platform.platform(),
                              'os_release': platform.freedesktop_os_release() if hasattr(platform, 'freedesktop_os_release') and sys.platform=='linux' else {},
                              'python': platform.python_version(), 'numpy': np.__version__,
                              'scipy': scipy.__version__, 'VeraGridEngine': __VeraGridEngine_VERSION__},
              'size': {'buses': len(grid.buses), 'lines': len(grid.lines),
                       'generators': len(grid.generators), 'transformers2w': len(grid.transformers2w)},
              'stage': 'power_flow'}
    if not args.minimal:
        report['grid_sha256'] = hashlib.sha256(args.grid.read_bytes()).hexdigest()
    slack_before = [b.idtag for b in grid.buses if b.is_slack]
    try:
        pf = vge.power_flow(grid)
        pf3 = vge.power_flow3ph(grid)
        report['balanced_pf_converged'] = bool(pf.converged)
        report['three_phase_pf_converged'] = bool(pf3.converged)
        target = next(b for b in grid.buses if b.name.strip() == ('TERMINAL' if args.minimal else 'SARGENTS'))
        line = next(l for l in grid.lines if l.active and target in (l.bus_from, l.bus_to))
        r, l, c = build_line_static_matrices(grid, line)
        report['terminal'] = {'bus': target.name, 'line': line.name,
                              'R_pu': float(line.R), 'X_pu': float(line.X), 'B_pu': float(line.B),
                              'C_terminal_emt_pu': c.tolist(), 'C_rank': int(np.linalg.matrix_rank(c)),
                              'active_branches': sum(bool(b.active) for b in list(grid.lines)+list(grid.transformers2w) if target in (b.bus_from,b.bus_to)),
                              'active_injections': sum(bool(d.active) for ds in (grid.generators,grid.loads,grid.shunts) for d in ds if d.bus is target)}
        if not pf.converged or not pf3.converged:
            raise RuntimeError('Power flow did not converge; this is a different failure')
        report['stage'] = 'attach_models'
        attach_emt_models(grid)
        report['stage'] = 'build_emt_problem'
        options = EmtOptions(time_step=1e-6, simulation_time=.02, tolerance=1e-6,
                             solver_type=EmtSolverTypes.StructuralAD,
                             integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
                             initialization_method=EmtInitializationMethod.Auto, verbose=0)
        # Public factory: do not skip or monkeypatch the original validator.
        build_emt_problem(grid=grid, options=options, pf_results=pf,
                          pf_results_3ph=pf3, logger=Logger())
        report['outcome'] = 'constructor accepted the grid; reported rejection not reproduced'
    except EmtTopologyError as exc:
        report['outcome'] = 'original topology rejection reproduced'
        report['exception_type'] = type(exc).__name__
        report['error'] = str(exc)
    except Exception as exc:
        report['outcome'] = 'different error; inspect before interpreting as reproduction'
        report['exception_type'] = type(exc).__name__
        report['error'] = str(exc)
    report['slack_assignments_unchanged'] = slack_before == [b.idtag for b in grid.buses if b.is_slack]
    report['elapsed_s'] = time.perf_counter()-start
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2, allow_nan=False))
    if report['outcome'].startswith('different error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
