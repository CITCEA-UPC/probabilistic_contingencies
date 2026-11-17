"""Ordre de les etapes i informes finals, sense motor EMT ni runtime COMPSs."""
import contextlib
import importlib.util
import io
import json
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

    def capture_processing_metrics(self, fail_second_save=False):
        clock = [100.0]
        saves = []
        def load(*args):
            clock[0] += 2.0
            return [{'contingency_id': cid} for cid in [1,2,3]]
        def submit(definition):
            clock[0] += 1.0
            return {'contingency_id': definition['contingency_id'], 'result': {'status':'ok'}}
        def wait(batch):
            clock[0] += 3.0
            return batch
        def save(db, results, **kwargs):
            clock[0] += 5.0
            saves.append(results)
            if fail_second_save and len(saves) == 2:
                raise RuntimeError('transaction failed')
        output = io.StringIO()
        with patch.object(self.pipeline, 'perf_counter', side_effect=lambda:clock[0]), \
             patch.object(storage, 'load_definitions', side_effect=load), \
             patch.object(self.pipeline, 'process_contingency_task', side_effect=submit), \
             patch.object(self.pipeline, 'compss_wait_on', side_effect=wait), \
             patch.object(storage, 'save_results', side_effect=save), \
             patch.object(self.pipeline, 'compss_delete_object'), \
             contextlib.redirect_stdout(output):
            if fail_second_save:
                with self.assertRaisesRegex(RuntimeError, 'transaction failed'):
                    self.pipeline.process_selected_contingencies([1,2,3],2)
            else:
                self.assertEqual(self.pipeline.process_selected_contingencies([1,2,3],2),(3,0))
        summaries = [line.removeprefix('PROCESS_PERFORMANCE ') for line in output.getvalue().splitlines()
                     if line.startswith('PROCESS_PERFORMANCE ')]
        self.assertEqual(len(summaries),1)
        return json.loads(summaries[0])

    def test_master_timings_separate_wait_from_persistence(self):
        metrics = self.capture_processing_metrics()
        self.assertTrue(metrics['completed'])
        self.assertEqual(metrics['selected'],3)
        self.assertEqual(metrics['submitted'],3)
        self.assertEqual(metrics['committed'],3)
        self.assertEqual(metrics['committed_batches'],2)
        self.assertEqual(metrics['load_definitions_s'],2.0)
        self.assertEqual(metrics['submit_s'],3.0)
        self.assertEqual(metrics['wait_results_s'],6.0)
        self.assertEqual(metrics['persist_results_s'],10.0)
        self.assertEqual(metrics['processing_total_s'],21.0)

    def test_failed_transaction_retains_partial_progress_in_timing_summary(self):
        metrics = self.capture_processing_metrics(fail_second_save=True)
        self.assertFalse(metrics['completed'])
        self.assertEqual(metrics['submitted'],3)
        self.assertEqual(metrics['committed'],2)
        self.assertEqual(metrics['committed_batches'],1)
        self.assertEqual(metrics['persist_results_s'],10.0)

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

    def test_grid_and_reset_select_full_pipeline_without_editing_config(self):
        grid = Path(self.tmp.name) / 'IEEE118.raw'
        grid.touch()
        copy = Path(self.tmp.name) / 'fresh118.db'
        copy.touch()
        events, risk, preprocess = self.run_main(
            ['--grid',str(grid),'--db',str(copy),'--reset-db'],[1])
        preprocess.assert_called_once()
        self.assertEqual(self.pipeline.config.GRID_NAME,'IEEE118.raw')
        self.assertEqual(self.pipeline.config.GRID_PATH,str(grid))
        self.assertEqual(self.pipeline.config.DB_FILE,str(copy))
        self.assertTrue(self.pipeline.config.CLEAR_DB_ON_START)
        self.assertEqual(events,[('task',1),'wait','save','risk'])

    def test_grid_derives_database_name_in_existing_database_directory(self):
        grid = Path(self.tmp.name) / 'IEEE 118.raw'
        grid.touch()
        _, _, preprocess = self.run_main(['--preprocess','--grid',str(grid)],[])
        self.assertEqual(self.pipeline.config.DB_FILE,str(Path(self.tmp.name)/'results_IEEE_118.db'))
        preprocess.assert_called_once()

    def test_invalid_grid_and_conflicting_reset_are_rejected_before_deleting_database(self):
        self.db.write_bytes(b'preserve existing results')
        for args in (['--grid',str(Path(self.tmp.name)/'missing.raw'),'--reset-db'],
                     ['--pending','--reset-db'],['--all','--grid','anything.raw'],
                     ['--ids','1','--reset-db']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    self.run_main(args,[])
                self.assertEqual(error.exception.code,2)
                self.assertEqual(self.db.read_bytes(),b'preserve existing results')

    def test_explicit_reset_replaces_old_catalogue_when_config_default_is_false(self):
        grid = Path(self.tmp.name) / 'IEEE118.raw'
        grid.touch()
        self.pipeline.config.CLEAR_DB_ON_START=False
        self.pipeline.vge.open_file=Mock(return_value=types.SimpleNamespace(
            lines=[object()],generators=[object()],transformers2w=[],
            transformers3w=[],loads=[]))
        self.db.write_bytes(b'old database to replace')
        with patch.object(sys,'argv',['main.py','--grid',str(grid),'--db',str(self.db),
                                      '--reset-db','--preprocess']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.pipeline.main()
        with sqlite3.connect(self.db) as c:
            rows=c.execute('SELECT grid_name,level,status FROM contingency_results').fetchall()
        self.assertEqual(rows,[('IEEE118.raw',1,'pending'),('IEEE118.raw',1,'pending'),
                               ('IEEE118.raw',2,'pending')])

    def test_preprocess_creates_only_unique_n1_and_n2_definitions(self):
        self.pipeline.config.GRID_NAME='test.raw'
        self.pipeline.config.GRID_PATH=str(Path(self.tmp.name)/'test.raw')
        self.pipeline.vge.open_file=Mock(return_value=types.SimpleNamespace(
            lines=[object(),object()],generators=[object()],transformers2w=[object()],
            transformers3w=[],loads=[]))
        with contextlib.redirect_stdout(io.StringIO()):
            self.pipeline.run_preprocess()
        with sqlite3.connect(self.db) as c:
            self.assertEqual(dict(c.execute('SELECT level,count(*) FROM contingency_results GROUP BY level')),{1:4,2:6})
            definitions=list(c.execute('SELECT lines,generators,transformers FROM contingency_results'))
            self.assertEqual(len(definitions),len(set(definitions)))
            self.assertEqual(c.execute('SELECT level FROM contingency_results WHERE contingency_id=1').fetchone()[0],1)

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
