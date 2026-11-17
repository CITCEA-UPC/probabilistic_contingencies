"""El càlcul només desconnecta els elements; no corregeix slack ni despatx."""
import ast
from collections import Counter
from itertools import chain
import json
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock


class Modes(list):
    @property
    def size(self): return len(self)
    @property
    def real(self): return [z.real for z in self]


class ContingencyPolicyTests(unittest.TestCase):
    def setUp(self):
        source=Path(__file__).resolve().parents[1]/'contingencies/contingency.py'
        tree=ast.parse(source.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='calculate_contingency')
        self.grid=SimpleNamespace(
            lines=[SimpleNamespace(active=True,R=.1,X=.2) for _ in range(3)],
            generators=[SimpleNamespace(active=True,P=70+i*10,Vset=1.0) for i in range(2)],
            transformers2w=[SimpleNamespace(active=True,tap_module=1.0) for _ in range(2)],
            buses=[SimpleNamespace(name=f'bus {i}',is_slack=(i==0)) for i in range(3)])
        self.vge=Mock()
        self.vge.open_file.return_value=self.grid
        self.vge.power_flow.return_value=SimpleNamespace(converged=False)
        self.vge.power_flow3ph.return_value=SimpleNamespace(converged=True)
        self.scope={'time':time,'ast':ast,'json':json,'vge':self.vge,
                    'np':SimpleNamespace(max=max),'STABLE_MAX_REAL_PART':1e-6,
                    'resolve_grid_path':lambda path:path,
                    'get_buses_with_few_connections':Mock(return_value=[]),
                    'get_islands_info':Mock(return_value=(1,[3])),
                    'attach_emt_models':Mock(),
                    'run_small_signal_emt_analysis':Mock(return_value={'emt_ok':True,'error':False}),
                    'run_small_signal_eigenvalues':Mock(return_value=Modes([-.1+1j])),
                    'EmtTopologyError':type('EmtTopologyError',(Exception,),{})}
        for name in ('OK','ISOLATED_BUSES','PF_NOT_CONVERGED','PF3_ERROR','PF3_NOT_CONVERGED','EMT_TOPOLOGY_ERROR','SMALL_SIGNAL_ERROR'):
            self.scope['STATUS_'+name]=name.lower()
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),self.scope)
        self.definition={'grid_path':'test.raw','lines':'[1]','generators':'[0]','transformers':'[1]'}

    def calculate(self): return self.scope['calculate_contingency'](self.definition)

    def assert_network_preserved(self):
        self.assertEqual([l.active for l in self.grid.lines],[True,False,True])
        self.assertEqual([g.active for g in self.grid.generators],[False,True])
        self.assertEqual([t.active for t in self.grid.transformers2w],[True,False])
        self.assertEqual([g.P for g in self.grid.generators],[70,80])
        self.assertEqual([g.Vset for g in self.grid.generators],[1,1])
        self.assertEqual([b.is_slack for b in self.grid.buses],[True,False,False])
        self.assertEqual([t.tap_module for t in self.grid.transformers2w],[1,1])
        self.vge.OptimalPowerFlowDriver.assert_not_called()
        self.vge.PowerFlowDriver.assert_not_called()
        self.vge.PowerFlowDriver3Ph.assert_not_called()

    def test_failed_pf_is_classified_without_redispatch(self):
        result=self.calculate()
        self.assertEqual(result['status'],'pf_not_converged')
        self.assertFalse(result['opf_needed'])
        self.assertIsNone(result['opf_converged'])
        self.vge.power_flow3ph.assert_not_called()
        self.assert_network_preserved()

    def test_successful_case_preserves_original_slack_and_setpoints(self):
        self.vge.power_flow.return_value.converged=True
        result=self.calculate()
        self.assertEqual(result['status'],'ok')
        self.assertTrue(result['stable'])
        self.vge.power_flow3ph.assert_called_once_with(self.grid)
        self.assert_network_preserved()

    def test_pf3_failure_is_not_recovered_with_another_operating_point(self):
        self.vge.power_flow.return_value.converged=True
        self.vge.power_flow3ph.return_value.converged=False
        self.assertEqual(self.calculate()['status'],'pf3_not_converged')
        self.scope['attach_emt_models'].assert_not_called()
        self.assert_network_preserved()

    def test_rejected_terminal_does_not_change_slack_or_add_devices(self):
        self.vge.power_flow.return_value.converged=True
        self.scope['get_buses_with_few_connections'].return_value=[self.grid.buses[0]]
        result=self.calculate()
        self.assertEqual(result['status'],'isolated_buses')
        self.assertEqual(result['n_islands'],1)
        self.assertEqual(result['isolated_buses'],['bus 0'])
        self.scope['attach_emt_models'].assert_not_called()
        self.assert_network_preserved()


class ModalDriverTests(unittest.TestCase):
    def setUp(self):
        source=Path(__file__).resolve().parents[1]/'contingencies/contingency.py'
        tree=ast.parse(source.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_small_signal_eigenvalues')
        self.modes=[-.1+1j]
        self.driver=SimpleNamespace(logger=SimpleNamespace(entries=[]),
                                    results=SimpleNamespace(eigenvalues=self.modes),run=Mock())
        self.factory=Mock(return_value=self.driver)
        self.scope={'STEPS_PER_PERIOD':600,'SMALL_SIGNAL_MODES':12,
                    'EmtOptions':Mock(),'SmallSignalStabilityEmtOptions':Mock(),
                    'EmtSolverTypes':SimpleNamespace(StructuralAD='ad'),
                    'DynamicIntegrationMethod':SimpleNamespace(DaeTrapezoidal='trapezoidal'),
                    'EmtInitializationMethod':SimpleNamespace(Auto='auto'),
                    'SmallSignalEmtBuildTypes':SimpleNamespace(Arnoldi='arnoldi'),
                    'LogSeverity':SimpleNamespace(Error='error'),
                    'SmallSignalStabilityEmtDriver':self.factory}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),self.scope)
        self.grid=SimpleNamespace(fBase=50)
        self.pf=object()
        self.pf3=object()

    def calculate(self):
        return self.scope['run_small_signal_eigenvalues'](self.grid,self.pf,self.pf3)

    def test_one_driver_receives_both_power_flows(self):
        self.assertIs(self.calculate(),self.modes)
        self.factory.assert_called_once()
        args=self.factory.call_args.kwargs
        self.assertIs(args['grid'],self.grid)
        self.assertIs(args['pf_results'],self.pf)
        self.assertIs(args['pf_results_3ph'],self.pf3)
        self.driver.run.assert_called_once_with()

    def test_construction_errors_prevent_modal_execution(self):
        self.driver.logger.entries=[SimpleNamespace(severity='error',message='invalid model')]
        with self.assertRaises(RuntimeError): self.calculate()
        self.driver.run.assert_not_called()

    def test_missing_modal_results_still_raise(self):
        self.driver.results=None
        with self.assertRaisesRegex(RuntimeError,'no results'): self.calculate()


class ConnectionCountTests(unittest.TestCase):
    def test_active_branches_and_injections_keep_the_same_terminal_rule(self):
        source=Path(__file__).resolve().parents[1]/'contingencies/contingency.py'
        tree=ast.parse(source.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_buses_with_few_connections')
        scope={'Counter':Counter,'chain':chain}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),scope)
        a,b,c,d=[object() for _ in range(4)]
        grid=SimpleNamespace(buses=[a,b,c,d],
            lines=[SimpleNamespace(active=True,bus_from=a,bus_to=b),
                   SimpleNamespace(active=True,bus_from=b,bus_to=c)],
            generators=[SimpleNamespace(active=True,bus=a)],
            loads=[],shunts=[SimpleNamespace(active=False,bus=c)],transformers2w=[])
        count=scope['get_buses_with_few_connections']
        self.assertEqual(count(grid),[c,d])
        grid.transformers2w.append(SimpleNamespace(active=True,bus_from=c,bus_to=d))
        grid.loads.append(SimpleNamespace(active=True,bus=d))
        self.assertEqual(count(grid),[])
        grid.lines[0].active=False
        self.assertEqual(count(grid),[a,b])


if __name__=='__main__': unittest.main()
