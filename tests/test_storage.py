"""Persistència atòmica i correspondència dels resultats sense motor EMT."""
import ast
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contingencies import storage


def result(cid, stable=True):
    return {'contingency_id':cid,'result':dict(errors=False,powerflow_converged=True,stable=stable,
        islands=False,execution_time=1.5,calculated=True,isolated_buses=['bus 0'],n_islands=1,
        status='ok',error_message=None,eigenvalues='[[-0.1,1]]',opf_needed=False,opf_converged=None)}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'results.db'
        definitions=['contingency_id INTEGER PRIMARY KEY', 'grid_name TEXT', 'grid_path TEXT',
                     'lines TEXT', 'generators TEXT', 'transformers TEXT', 'level INTEGER']
        definitions += [f'{name}' for name in storage.RESULT_COLUMNS]
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE contingency_results ('+','.join(definitions)+')')
            c.executemany("INSERT INTO contingency_results (contingency_id,grid_name,grid_path,lines,generators,transformers,level,status) VALUES (?,'test','grid.raw','[0]','[]','[]',1,'pending')",[(1,),(2,),(3,)])

    def statuses(self):
        with sqlite3.connect(self.db) as c:
            return list(c.execute('SELECT contingency_id,status FROM contingency_results ORDER BY contingency_id'))

    def test_load_preserves_order_and_returns_only_definition_columns(self):
        before=self.db.read_bytes()
        rows=storage.load_definitions(self.db,[3,1])
        self.assertEqual([r['contingency_id'] for r in rows],[3,1])
        self.assertEqual(set(rows[0]),set(storage.DEFINITION_COLUMNS))
        self.assertEqual(before,self.db.read_bytes())
        with self.assertRaises(ValueError): storage.load_definitions(self.db,[1,999])
        with self.assertRaises(ValueError): storage.load_definitions(self.db,[1,1])

    def test_large_id_selections_are_chunked(self):
        with sqlite3.connect(self.db) as c:
            c.executemany('INSERT INTO contingency_results (contingency_id) VALUES (?)',[(i,) for i in range(4,1101)])
        ids=list(range(1100,0,-1))
        self.assertEqual([r['contingency_id'] for r in storage.load_definitions(self.db,ids)],ids)

    def test_missing_database_is_never_created(self):
        path=Path(self.tmp.name)/'missing.db'
        with self.assertRaises(sqlite3.OperationalError): storage.load_definitions(path,[1])
        with self.assertRaises(sqlite3.OperationalError): storage.save_results(path,[result(1)],[1])
        self.assertFalse(path.exists())

    def test_result_id_controls_assignment_even_if_results_are_reordered(self):
        storage.save_results(self.db,[result(2,False),result(1,True)],[1,2])
        with sqlite3.connect(self.db) as c:
            rows=list(c.execute('SELECT contingency_id,stable,isolated_buses,opf_converged FROM contingency_results WHERE contingency_id<3 ORDER BY contingency_id'))
        self.assertEqual(rows,[(1,1,'["bus 0"]',None),(2,0,'["bus 0"]',None)])

    def test_missing_duplicate_or_unexpected_results_leave_batch_untouched(self):
        for returned in ([result(1)], [result(1),result(1)], [result(1),result(3)]):
            with self.subTest(returned=returned),self.assertRaises(ValueError):
                storage.save_results(self.db,returned,[1,2])
        self.assertTrue(all(status=='pending' for _,status in self.statuses()))

    def test_incomplete_result_is_rejected_before_any_write(self):
        bad=result(2)
        del bad['result']['stable']
        with self.assertRaises(KeyError): storage.save_results(self.db,[result(1),bad],[1,2])
        self.assertTrue(all(status=='pending' for _,status in self.statuses()))

    def test_database_error_rolls_back_entire_batch(self):
        with sqlite3.connect(self.db) as c:
            c.execute("CREATE TRIGGER fail_second BEFORE UPDATE ON contingency_results WHEN OLD.contingency_id=2 BEGIN SELECT RAISE(ABORT,'write failed'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            storage.save_results(self.db,[result(1),result(2)],[1,2])
        self.assertEqual(self.statuses(),[(1,'pending'),(2,'pending'),(3,'pending')])

    def test_previous_batches_survive_later_failure(self):
        storage.save_results(self.db,[result(1)],[1])
        with self.assertRaises(ValueError):
            storage.save_results(self.db,[result(2),result(999)],[2,999])
        self.assertEqual(self.statuses(),[(1,'ok'),(2,'pending'),(3,'pending')])
        pending=[cid for cid,status in self.statuses() if status=='pending']
        storage.save_results(self.db,[result(cid) for cid in pending],pending)
        self.assertTrue(all(status=='ok' for _,status in self.statuses()))

    def test_calculation_exception_is_a_result_without_sqlite_access(self):
        # Executa la funció real aïllada dels imports pesants del motor.
        path=Path(__file__).resolve().parents[1]/'contingencies'/'contingency.py'
        tree=ast.parse(path.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='process_contingency')
        def fail(definition): raise RuntimeError('numerical failure')
        scope={'time':time,'calculate_contingency':fail,'STATUS_EXCEPTION':'exception'}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),scope)
        with patch.object(sqlite3,'connect',side_effect=AssertionError('worker SQLite access')), contextlib.redirect_stdout(io.StringIO()):
            computed=scope['process_contingency']({'contingency_id':3})
        self.assertEqual(computed['status'],'exception')
        self.assertIn('RuntimeError: numerical failure',computed['error_message'])
        self.assertGreaterEqual(computed['execution_time'],0)
        storage.save_results(self.db,[{'contingency_id':3,'result':computed}],[3])
        self.assertEqual(self.statuses()[-1],(3,'exception'))


if __name__=='__main__':
    unittest.main()
