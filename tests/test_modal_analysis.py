"""Proves del visor modal i de la interpretació compartida dels resultats."""
import ast
import contextlib
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import modal_analysis as modal
from contingencies import result_diagnostics as diagnostics
import risk_analysis as risk


def row(**updates):
    result = dict(contingency_id=13, grid_name="test", lines="[1]", generators="[]",
                  transformers="[]", level=1, status="ok", stable=1, errors=0,
                  n_islands=1, islands=0, powerflow_converged=1, isolated_buses="[]",
                  eigenvalues='[[-0.1, 1.0]]')
    result.update(updates)
    return result


class ModalTests(unittest.TestCase):
    def test_absolute_threshold_boundaries_do_not_depend_on_other_modes(self):
        tol = diagnostics.STABLE_MAX_REAL_PART
        values = [complex(-2*tol, 0), complex(-tol, 0), 0j, complex(tol, 0),
                  complex(2*tol, 0), complex(-1, 10000)]
        self.assertEqual(modal.classify_modes(values),
                         ["stable", "near_axis", "near_axis", "near_axis", "unstable", "stable"])
        for z, kind in zip(values, modal.classify_modes(values)):
            diagnosis, _ = risk.classify(row(stable=int(kind != "unstable"), eigenvalues=json.dumps([[z.real,z.imag]])))
            self.assertEqual(diagnosis == "failure", kind == "unstable")

    def test_all_consumers_use_shared_threshold(self):
        self.assertIs(modal.classify, risk.classify)
        path = Path(__file__).resolve().parents[1] / 'contingencies' / 'contingency.py'
        tree = ast.parse(path.read_text())
        self.assertTrue(any(isinstance(node, ast.ImportFrom) and node.module == 'contingencies.result_diagnostics'
                            and any(alias.name == 'STABLE_MAX_REAL_PART' for alias in node.names)
                            for node in tree.body))

    def test_invalid_modes_are_rejected(self):
        for raw in ('bad', 'false', '{}', '0', '[[1]]', '[[1, 2, 3]]',
                    '[[NaN,0]]', '[[1,Infinity]]', '[["1",0]]', '[[true,0]]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                diagnostics.parse_eigenvalues(raw)
        for raw in (None, '', 'null', '[]'):
            self.assertIsNone(diagnostics.parse_eigenvalues(raw))
        self.assertEqual(diagnostics.parse_eigenvalues('[[1,-2]]'), [1-2j])

    def test_frequency_and_damping_without_artificial_denominator(self):
        frequency, damping = modal.mode_metrics(-3+4j)
        self.assertAlmostEqual(frequency, 4/(2*math.pi))
        self.assertAlmostEqual(damping, .6)
        self.assertEqual(modal.mode_metrics(0j), (0, None))

    def test_pending_null_is_unknown(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            modal.print_summary(row(status='pending', stable=None, errors=None,
                                    n_islands=None, islands=None, powerflow_converged=None,
                                    eigenvalues=None), None)
        text = output.getvalue()
        self.assertIn('stable (BD)=desconegut', text)
        self.assertIn('Topologia: desconeguda', text)
        self.assertIn('unknown (pending)', text)
        self.assertNotIn('stable (BD)=False', text)

    def test_islanding_and_modal_verdict_are_both_visible(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            modal.print_summary(row(n_islands=2, islands=1), [-.1+1j])
        text = output.getvalue()
        self.assertIn('2 illes: fragmentació', text)
        self.assertIn('failure (islanding)', text)
        self.assertIn('cap mode calculat supera', text)

    def test_database_queries_preserve_nulls_and_handle_missing_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'results.db'
            with self.assertRaises(sqlite3.OperationalError):
                modal.load_result_from_db(1, path)
            self.assertFalse(path.exists())
            with sqlite3.connect(path) as c:
                c.execute('CREATE TABLE contingency_results (contingency_id INTEGER, stable BOOLEAN)')
                c.execute('INSERT INTO contingency_results VALUES (1,NULL)')
            before = path.read_bytes()
            self.assertIsNone(modal.load_result_from_db(1, path)['stable'])
            with self.assertRaises(ValueError):
                modal.load_result_from_db(2, path)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
