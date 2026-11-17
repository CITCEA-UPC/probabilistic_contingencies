"""Ordre de les etapes i informes finals, sense motor EMT ni runtime COMPSs."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from contingencies import storage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import risk_analysis
import contingencies


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'results.db'
        self.db.touch()
        config = types.ModuleType('config')
        config.DB_FILE = str(self.db)
        config.ROOT = Path(self.tmp.name)
        contingency = types.ModuleType('contingencies.contingency')
        contingency.STATUS_OK = 'ok'
        engine = types.ModuleType('VeraGridEngine')
        engine.__path__ = []
        api = types.ModuleType('VeraGridEngine.api')
        engine.api = api
        spec = importlib.util.spec_from_file_location('pipeline_under_test', Path(__file__).resolve().parents[1] / 'main.py')
        self.pipeline = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'config': config, 'contingencies.contingency': contingency,
                                     'VeraGridEngine': engine, 'VeraGridEngine.api': api}), \
             patch.dict('os.environ', {'CONTINGENCIES_LOCAL': '1'}), \
             patch.object(contingencies, 'contingency', contingency, create=True):
            spec.loader.exec_module(self.pipeline)

    def run_main(self, args, ids, report=None, wait=None, persist=None):
        events = []
        def task(definition):
            cid = definition['contingency_id']
            events.append(('task', cid))
            result = dict(errors=False, powerflow_converged=True, stable=True, islands=False,
                          execution_time=1.0, calculated=True, isolated_buses=[], n_islands=1,
                          status='ok', error_message=None, eigenvalues='[[-0.1,1]]',
                          opf_needed=False, opf_converged=None)
            return {'contingency_id': cid, 'result': result}
        def synchronize(futures):
            events.append('wait')
            return wait(futures) if wait else futures
        def save(*args, **kwargs):
            events.append('save')
            return persist(*args, **kwargs) if persist else None
        def reports(*args, **kwargs):
            events.append('risk')
            return report(*args, **kwargs) if report else None
        with patch.object(sys, 'argv', ['main.py', *args]), \
             patch.object(self.pipeline, 'select_contingency_ids', return_value=ids), \
             patch.object(self.pipeline, 'process_contingency_task', side_effect=task), \
             patch.object(self.pipeline, 'compss_wait_on', side_effect=synchronize), \
             patch.object(storage, 'load_definitions', return_value=[{'contingency_id':cid} for cid in ids]), \
             patch.object(storage, 'save_results', side_effect=save), \
             patch.object(self.pipeline, 'run_preprocess') as preprocess, \
             patch.object(risk_analysis, 'run_analysis', side_effect=reports) as risk, \
             contextlib.redirect_stdout(io.StringIO()):
            self.pipeline.main()
        return events, risk, preprocess

    def test_reports_run_once_after_wait_on_selected_tasks(self):
        events, risk, preprocess = self.run_main(['--ids', '1,13', '--risk-out', self.tmp.name], [1,13])
        self.assertEqual(events, [('task',1), ('task',13), 'wait', 'save', 'risk'])
        risk.assert_called_once_with(str(self.db), out_dir=self.tmp.name)
        preprocess.assert_not_called()

    def test_default_pipeline_preprocesses_and_reports(self):
        events, risk, preprocess = self.run_main([], [1])
        preprocess.assert_called_once()
        risk.assert_called_once()
        self.assertEqual(events[-3:], ['wait','save','risk'])

    def test_skip_risk_preserves_processing(self):
        events, risk, _ = self.run_main(['--ids','13','--skip-risk'], [13])
        self.assertEqual(events, [('task',13),'wait','save'])
        risk.assert_not_called()

    def test_completed_database_still_generates_reports(self):
        events, risk, _ = self.run_main(['--pending'], [])
        self.assertEqual(events, ['risk'])
        risk.assert_called_once()
        events, risk, _ = self.run_main(['--pending','--skip-risk'], [])
        self.assertEqual(events, [])
        risk.assert_not_called()

    def test_preprocess_only_never_reports(self):
        events, risk, preprocess = self.run_main(['--preprocess'], [])
        self.assertEqual(events, [])
        preprocess.assert_called_once()
        risk.assert_not_called()

    def test_failed_synchronization_never_reports(self):
        report = Mock()
        with self.assertRaises(RuntimeError):
            self.run_main(['--pending'], [1], report=report,
                          wait=Mock(side_effect=RuntimeError('worker failed')))
        report.assert_not_called()

    def test_report_reads_results_committed_by_master(self):
        with sqlite3.connect(self.db) as connection:
            self.pipeline.ensure_schema(connection)
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO contingency_results (contingency_id,grid_name,grid_path,lines,generators,transformers,level,status) VALUES (1,'test','test.raw','[0]','[]','[]',1,'pending')")
        def complete(futures):
            with sqlite3.connect(self.db) as c:
                self.assertEqual(c.execute('SELECT status FROM contingency_results').fetchone()[0], 'pending')
            return futures
        original_report = risk_analysis.run_analysis
        out = Path(self.tmp.name) / 'reports'
        def report(db_file, **kwargs):
            with patch.object(risk_analysis, 'plot_risk'):
                summary = original_report(db_file, **kwargs)
            self.assertEqual(summary['diagnoses'], {'stable':1})
        self.run_main(['--pending','--risk-out',str(out)], [1], wait=complete, report=report, persist=storage.save_results)
        self.assertTrue((out/'risk_index.csv').exists())
        self.assertTrue((out/'summary.json').exists())
        self.assertTrue((out/'scenarios.csv').exists())

    def test_multiple_batches_commit_before_reports_without_serializing_submission(self):
        events, _, _ = self.run_main(['--pending','--batch-size','2'], [1,2,3])
        self.assertEqual(events, [('task',1),('task',2),('task',3),'wait','save','wait','save','risk'])

    def test_worker_returns_id_and_result_without_storage_access(self):
        definition = {'contingency_id':13, 'grid_path':'test.raw'}
        self.pipeline.contingency.process_contingency = Mock(return_value={'status':'ok'})
        with patch.object(storage, 'load_definitions', side_effect=AssertionError('worker read')), \
             patch.object(storage, 'save_results', side_effect=AssertionError('worker write')):
            result = self.pipeline.process_contingency_task(definition)
        self.assertEqual(result, {'contingency_id':13, 'result':{'status':'ok'}})
        self.pipeline.contingency.process_contingency.assert_called_once_with(definition)

    def test_invalid_batch_size_is_rejected_before_preprocess(self):
        for value in ('0','-1','bad'):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    self.run_main(['--batch-size',value], [])
                self.assertEqual(error.exception.code,2)

    def test_separate_database_is_used_for_processing_and_reports(self):
        copy = Path(self.tmp.name) / 'copy.db'
        copy.touch()
        _, risk, _ = self.run_main(['--pending','--db',str(copy)], [1])
        risk.assert_called_once_with(str(copy), out_dir=None)
        self.assertEqual(self.pipeline.config.DB_FILE, str(copy))

    def test_database_directory_is_created_in_a_fresh_workspace(self):
        nested = Path(self.tmp.name) / 'outputs' / 'databases' / 'fresh.db'
        with patch.object(self.pipeline.config, 'DB_FILE', str(nested)), \
             contextlib.redirect_stdout(io.StringIO()):
            connection = self.pipeline.check_database_and_tables()
        try:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM contingency_results').fetchone()[0], 0)
        finally:
            connection.close()
        self.assertTrue(nested.is_file())

    def test_report_failure_is_visible_and_results_are_preserved(self):
        before = self.db.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaisesRegex(OSError,'disk full'):
                self.run_main(['--pending'], [], report=Mock(side_effect=OSError('disk full')))
        self.assertIn('simulation results remain saved',stderr.getvalue())
        self.assertEqual(self.db.read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
