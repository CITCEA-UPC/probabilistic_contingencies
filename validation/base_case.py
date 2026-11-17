"""Valida el cas base sense modificar la xarxa ni la BD de contingències.

Aplicació PyCOMPSs per a proves petites a gp_debug. Executa el mateix model
amb passos temporals diferents, mesura el tancament del cicle i compara
Arnoldi amb l'espectre dens del mateix operador quan la dimensió ho permet.
La comparació d'operadors no és una validació física amb un motor independent.
"""
import argparse
import json
import math
from pathlib import Path

try:
    from pycompss.api.task import task
    from pycompss.api.api import compss_wait_on
    from pycompss.api.constraint import constraint
except ImportError:
    from contingencies.pycompss_dummies.task import task
    from contingencies.pycompss_dummies.api import compss_wait_on
    from contingencies.pycompss_dummies.constraint import constraint


def cycle_closure(trajectory, names, n_states):
    """Diferència entre extrems, escalada per variable; theta es compara mòdul 2π."""
    if len(trajectory) < 2 or not 0 < n_states <= len(names):
        raise ValueError('Invalid cycle dimensions')
    if any(len(row) != len(names) for row in trajectory):
        raise ValueError('Variable names do not match trajectory')
    if any(not math.isfinite(float(x)) for row in trajectory for x in row):
        raise ValueError('Non-finite trajectory')
    errors=[]
    for i,name in enumerate(names):
        delta=float(trajectory[-1][i]-trajectory[0][i])
        angle='theta' in name.lower()
        if angle: delta=math.remainder(delta,2*math.pi)
        scale=max(1.0,max(abs(float(row[i])) for row in trajectory))
        # Per angles, l'escala no ha de créixer amb el nombre de voltes acumulades.
        if angle: scale=1.0
        errors.append({'variable':name,'state':i<n_states,'angle_wrapped':angle,
                       'endpoint_difference':delta,'scaled_error':abs(delta)/scale})
    return {'max_state_error':max(e['scaled_error'] for e in errors[:n_states]),
            'max_all_variables_error':max(e['scaled_error'] for e in errors),
            'largest_errors':sorted(errors,key=lambda e:-e['scaled_error'])[:10],
            'wrapped_angles':[e['variable'] for e in errors if e['angle_wrapped']]}


@constraint(computing_units='1')
@task(returns=1)
def assess_base_case(grid_path, out_dir, steps_per_period, settle_periods, mode_count):
    import time
    import numpy as np
    import scipy.linalg as la
    from contingencies import contingency as ct
    from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver
    from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_operator import EmtFloquetOperator
    from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver

    tic=time.perf_counter()
    grid=ct.vge.open_file(grid_path)
    pf=ct.vge.power_flow(grid)
    pf3=ct.vge.power_flow3ph(grid)
    if not pf.converged or not pf3.converged:
        raise RuntimeError('Base power flow did not converge')
    connection_count_candidates=[bus.name for bus in ct.get_buses_with_few_connections(grid)]
    # El recompte és diagnòstic. El constructor ORIGINAL de VeraGrid decideix
    # l'acceptació: un cop corregit el motor, no anticipem el rebuig amb la
    # mateixa heurística antiga. No es relaxa ni substitueix cap validació EMT.
    ct.attach_emt_models(grid)
    period=1/grid.fBase
    h=period/steps_per_period
    emt_options=ct.EmtOptions(time_step=h,simulation_time=settle_periods*period,
        tolerance=1e-6,solver_type=ct.EmtSolverTypes.StructuralAD,
        integration_method=ct.DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=ct.EmtInitializationMethod.Auto,verbose=0)
    options=ct.SmallSignalStabilityEmtOptions(k=mode_count,target_period=period,
        ss_assessment_time=settle_periods*period,verbose=0,
        build_type=ct.SmallSignalEmtBuildTypes.Arnoldi)

    class MeasuredDriver(SmallSignalStabilityEmtDriver):
        def _capture_limit_cycle_and_evaluator(self,h,verbose=0):
            # Mateix solver i contracte de captura del motor; es comproven també
            # les banderes d'inicialització i convergència abans de calcular modes.
            solver=StructuralVectorizedSolver(problem=self.problem,t0=0,
                t_end=self.sss_options.ss_assessment_time,h=h,
                method=self.emt_options.integration_method,verbose=False)
            t,y,d,initialized,converged=solver.simulate()
            self.temporal_health={'initialized':bool(initialized),'converged':bool(converged),
                                  'samples':len(t),'end_time':float(t[-1])}
            if not initialized or not converged: raise RuntimeError(f'Capture failed: {self.temporal_health}')
            samples=int(self.sss_options.target_period/h)+1
            captured=(y[-samples:],d[-samples:],t[-samples:],
                      self.problem.get_floquet_jacobian_evaluator(solver.vec_jacobian),
                      np.array([c.value for c in self.problem.get_parameters_values()],dtype=float),
                      self.problem.get_variable_parameter_number())
            self.captured=captured
            return captured

    driver=MeasuredDriver(grid=grid,emt_options=emt_options,sss_options=options,
                          pf_results=pf,pf_results_3ph=pf3)
    errors=[e for e in driver.logger.entries if e.severity==ct.LogSeverity.Error]
    if errors: raise RuntimeError('; '.join(map(str,errors)))
    driver.run()
    if driver.results is None: raise RuntimeError('No modal results')
    result=driver.results
    if not result.eigenvalues.size or not np.isfinite(result.eigenvalues).all():
        raise RuntimeError('Missing or non-finite eigenvalues')
    y,d,t,jac,params,n_ev=driver.captured
    names=[var.name for var in driver.problem.state_and_algebraic_vars()]
    n_states=driver.problem.get_states_number()
    operator=EmtFloquetOperator(problem=driver.problem,trajectory=y,h=h,n_states=n_states,
        method=emt_options.integration_method,jac_evaluator=jac,static_params=params,
        n_event_params=n_ev,t_trajectory=t,d_trajectory=d)
    residuals=[]
    for mu,v in zip(result.multipliers,result.right_vecs.T):
        mv=operator.matvec(v.real)+1j*operator.matvec(v.imag)
        scale=np.linalg.norm(mv)+abs(mu)*np.linalg.norm(v)
        residuals.append(float(np.linalg.norm(mv-mu*v)/max(scale,1e-300)))
    report={'steps_per_period':steps_per_period,'settle_periods':settle_periods,
        'target_period':period,'captured_period':float(t[-1]-t[0]),
        'powerflow_converged':bool(pf.converged),'pf3_converged':bool(pf3.converged),
        'n_islands':ct.get_islands_info(grid)[0],'temporal_health':driver.temporal_health,
        'connection_count_candidates':connection_count_candidates,
        'state_count':n_states,'operator_dimension':operator.shape[0],
        'cycle_closure':cycle_closure(y,names,n_states),
        'eigenvalues':[[float(z.real),float(z.imag)] for z in result.eigenvalues],
        'max_real_part':float(result.eigenvalues.real.max()),
        'relative_eigenpair_residuals':residuals,'max_relative_residual':max(residuals)}
    report['dense_check']={'skipped':True,'reason':'operator dimension exceeds 256'}
    if operator.shape[0]<=256:
        dense=np.column_stack([operator.matvec(e) for e in np.eye(operator.shape[0])])
        mu_dense=la.eigvals(dense)
        distances=[float(np.min(np.abs(mu_dense-mu))) for mu in result.multipliers]
        report['dense_check']={'mode_count':len(mu_dense),
            'max_real_part':float(np.log(np.abs(mu_dense).max())/period),
            'max_selected_multiplier_distance':max(distances),
            'multipliers':[[float(z.real),float(z.imag)] for z in mu_dense]}
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    stem=f'steps_{steps_per_period}_settle_{settle_periods}'
    np.savez_compressed(out/(stem+'.npz'),time=t,values=y,derivatives=d,names=np.array(names))
    report['execution_time']=time.perf_counter()-tic
    (out/(stem+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--steps',type=int,nargs='+',default=[600,1200])
    parser.add_argument('--settle-periods',type=int,default=1)
    parser.add_argument('--modes',type=int,default=12)
    args=parser.parse_args()
    if min(args.steps)<2 or args.settle_periods<1 or args.modes<1:
        parser.error('steps >= 2, settle-periods >= 1 and modes >= 1 required')
    # Un sol cas físic, executat amb cada configuració numèrica per separat.
    for steps in args.steps:
        report=compss_wait_on(assess_base_case(str(Path(args.grid).resolve()),
            str(Path(args.out).resolve()),steps,args.settle_periods,args.modes))
        print(json.dumps({k:report[k] for k in ['steps_per_period','settle_periods',
            'max_real_part','max_relative_residual','cycle_closure','dense_check','execution_time']},indent=2),flush=True)


if __name__=='__main__': main()
