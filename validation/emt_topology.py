"""Diagnòstic del cas base: PF/PF3 i validador EMT original, sense relaxar-lo.

Executar com a mòdul amb les dependències del motor. No modifica la xarxa,
el motor ni les bases de dades. La comprovació de connexions s'invoca sobre
un context mínim: no compila ni integra el problema DAE complet.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import traceback


def inspect_grid(grid_path):
    from contingencies import contingency as ct
    from VeraGridEngine.basic_structures import Logger
    from VeraGridEngine.Devices.Dynamic.static_parameter_mapping import build_line_static_matrices
    from VeraGridEngine.Simulations.EMT.problems import emt_problem_dae as engine

    tic = time.perf_counter()
    path = Path(grid_path).resolve()
    grid = ct.vge.open_file(str(path))
    slack_before = [b.idtag for b in grid.buses if b.is_slack]
    report = {
        'grid': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'scope': 'unmodified base case; original validator only, no DAE compilation',
        'islands': ct.get_islands_info(grid),
        'slack_buses': [b.name for b in grid.buses if b.is_slack],
        'stage': 'balanced_pf',
    }
    try:
        pf = ct.vge.power_flow(grid)
        report['balanced_pf_converged'] = bool(pf.converged)
        report['stage'] = 'three_phase_pf'
        try:
            pf3 = ct.vge.power_flow3ph(grid)
            report['three_phase_pf_converged'] = bool(pf3.converged)
        except Exception as exc:
            report['three_phase_pf_error'] = f'{type(exc).__name__}: {exc}'
        rejected = ct.get_buses_with_few_connections(grid)
        report['rejected_buses'] = []
        for bus in rejected:
            entry = {
                'bus': bus.name, 'idtag': bus.idtag,
                'is_slack': bool(bus.is_slack), 'vnom_kv': float(bus.Vnom),
                'branches': [],
                'injections': [
                    {'type': kind, 'name': device.name}
                    for kind, devices in [('generator', grid.generators),
                                          ('load', grid.loads), ('shunt', grid.shunts)]
                    for device in devices if device.active and device.bus is bus
                ],
            }
            for branch in list(grid.lines) + list(grid.transformers2w):
                if not branch.active or bus not in (branch.bus_from, branch.bus_to):
                    continue
                detail = {
                    'name': branch.name, 'from': branch.bus_from.name,
                    'to': branch.bus_to.name, 'R': float(branch.R),
                    'X': float(branch.X), 'B': float(branch.B),
                }
                if branch in grid.lines:
                    r, l, c = build_line_static_matrices(grid, branch)
                    detail['emt_R'] = r.tolist()
                    detail['emt_L'] = l.tolist()
                    detail['emt_C_per_terminal'] = c.tolist()
                entry['branches'].append(detail)
            report['rejected_buses'].append(entry)
        report['stage'] = 'attach_models'
        ct.attach_emt_models(grid)
        report['stage'] = 'original_engine_connection_validator'
        # Only these fields are read by _validate_connections. No monkeypatch,
        # no changes to the original validation criterion.
        context = engine.EmtProblemDae.__new__(engine.EmtProblemDae)
        context.grid = grid
        context.logger = Logger()
        context._device_type_disposition = engine._build_emt_device_type_disposition_table()
        try:
            context._validate_connections()
            report['original_engine_validator'] = {'accepted': True}
        except engine.EmtTopologyError as exc:
            report['original_engine_validator'] = {'accepted': False, 'error': str(exc)}
        report['stage'] = 'complete'
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    report['slack_assignments_unchanged'] = slack_before == [b.idtag for b in grid.buses if b.is_slack]
    report['execution_time_s'] = time.perf_counter() - tic
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = inspect_grid(args.grid)
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2, allow_nan=False))
    if 'error' in report:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
