"""Proves de diagnòstic i dels límits de vulnerabilitat, sense motor EMT."""
import itertools
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import risk_analysis as risk


def row(cid, elements, status="ok", stable=1, eigenvalues=None, **fields):
    return dict(contingency_id=cid, level=len(elements), grid_name="test", grid_path="test.raw",
                lines=str([i for t, i in elements if t == "line"]),
                generators=str([i for t, i in elements if t == "generator"]), transformers="[]",
                status=status, stable=stable, errors=0, n_islands=1, islands=0,
                eigenvalues=json.dumps([[-0.1, 1.0]]) if eigenvalues is None else eigenvalues,
                **fields)


A, B, C = ("line", 0), ("line", 1), ("generator", 0)


class RiskTests(unittest.TestCase):
    def test_emt_rejection_is_unknown_but_islanding_is_failure(self):
        r = row(1, [A], status="isolated_buses", stable=0)
        self.assertEqual(risk.classify(r), ("unknown", "isolated_buses"))
        r["n_islands"] = 2
        self.assertEqual(risk.classify(r), ("failure", "islanding"))

    def test_modal_stability_does_not_override_islanding(self):
        r = row(1, [A], status="ok", stable=1)
        r["n_islands"] = 2
        self.assertEqual(risk.classify(r), ("failure", "islanding"))

    def test_numerical_failures_and_pending_are_unknown(self):
        for status in ("pending", "exception", "pf3_error", "emt_topology_error",
                       "small_signal_error", "pf_not_converged", "pf3_not_converged", "other"):
            with self.subTest(status=status):
                self.assertEqual(risk.classify(row(1, [A], status=status))[0], "unknown")

    def test_modal_instability_and_health_are_distinct(self):
        self.assertEqual(risk.classify(row(1, [A]))[0], "stable")
        self.assertEqual(risk.classify(row(1, [A], stable=0))[0], "unknown")
        self.assertEqual(risk.classify(row(1, [A], stable=0, eigenvalues='[[0.2, 1]]'))[0], "failure")
        for raw in ('null', '[]', 'broken', '[[NaN, 0]]', '[[1]]', '[["1", 0]]'):
            self.assertEqual(risk.classify(row(1, [A], eigenvalues=raw))[0], "unknown")

    def test_unique_pairs_and_historical_rows(self):
        rows = [row(1, [A]), row(2, [B]), row(3, [A, B], eigenvalues='[[1, 0]]'),
                row(4, [B, A], eigenvalues='[[1, 0]]')]
        _, unique, cases = risk.compute_risk_index(rows)
        _, ordered, _ = risk.compute_risk_index(rows, "rows")
        self.assertEqual(len(cases), 3)
        self.assertAlmostEqual(unique[A]["R2_lower"], .05)
        self.assertAlmostEqual(ordered[A]["R2_lower"], .10)
        self.assertEqual(unique[A]["R_lower"], unique[A]["R_upper"])

    def test_conflicting_replicates_are_unknown(self):
        rows = [row(1, [A, B]), row(2, [B, A], eigenvalues='[[1, 0]]')]
        _, cases = risk.prepare_scenarios(rows)
        pair = next(s for s in cases if s["level"] == 2)
        self.assertEqual(pair["reason"], "conflicting_results")
        rows[1]["status"] = "pending"
        _, cases = risk.prepare_scenarios(rows)
        self.assertEqual(next(s for s in cases if s["level"] == 2)["diagnosis"], "stable")

    def test_missing_cases_do_not_appear_as_zero_risk_or_full_coverage(self):
        _, results, cases = risk.compute_risk_index([row(1, [A, B])])
        self.assertEqual(sum(s["reason"] == "missing_scenario" for s in cases), 2)
        self.assertEqual(results[A]["R1_upper"], 1)
        self.assertEqual(results[A]["coverage"], .5)

    def test_bounds_enclose_every_completion_and_match_extremes(self):
        rows = [row(1, [A], status="isolated_buses"), row(2, [B]), row(3, [C]),
                row(4, [A, B], eigenvalues='[[1,0]]'),
                row(5, [A, C], status="small_signal_error"), row(6, [B, C])]
        elements, results, cases = risk.compute_risk_index(rows)
        unknowns = [s for s in cases if s["diagnosis"] == "unknown"]
        observed = {e: [] for e in elements}
        for severities in itertools.product((0, 1), repeat=len(unknowns)):
            assignment = {id(s): value for s, value in zip(unknowns, severities)}
            totals = {e: 0 for e in elements}
            for s in cases:
                severity = assignment.get(id(s), int(s["diagnosis"] == "failure"))
                for e in s["elements"]:
                    weight = 1 if s["level"] == 1 else risk.LAMBDA[next(p for p in s["elements"] if p != e)[0]]
                    totals[e] += weight * severity
            for e in elements:
                observed[e].append(totals[e])
        for e in elements:
            self.assertAlmostEqual(results[e]["R_lower"], min(observed[e]))
            self.assertAlmostEqual(results[e]["R_upper"], max(observed[e]))
        self.assertAlmostEqual(results[A]["weighted_coverage"], .05 / 1.15)

    def test_invalid_definition_and_mixed_grids_rejected(self):
        bad = row(1, [A, A])
        with self.assertRaises(ValueError):
            risk.prepare_scenarios([bad])
        other = row(2, [B])
        other["grid_path"] = "other.raw"
        with self.assertRaises(ValueError):
            risk.prepare_scenarios([row(1, [A]), other])

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.db"
            with self.assertRaises(sqlite3.OperationalError):
                risk.load_rows(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
