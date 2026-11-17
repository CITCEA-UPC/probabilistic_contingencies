"""Referència analítica escalar de Floquet: x'=a*x, amb a negatiu i positiu.

Prova numèrica petita, sense xarxes, sense contingències i sense modificar
el motor. Executar amb les dependències de VeraGrid instal·lades.
"""
import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class State:
    uid: int


@dataclass(frozen=True)
class Derivative:
    uid: int
    base_var: State


class ScalarProblem:
    def __init__(self):
        self.state=State(1)
        self.diff=Derivative(2,self.state)
    def get_state_vars(self): return [self.state]
    def get_diff_vars(self): return [self.diff]
    def get_states_number(self): return 1
    def get_algebraic_var_number(self): return 0


def run_reference():
    import config  # incorpora el codi del submòdul a sys.path
    import numpy as np
    from scipy import sparse
    from VeraGridEngine.enumerations import DynamicIntegrationMethod
    from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_operator import EmtFloquetOperator
    reports=[]
    period=.02
    for rate in (-2.0,2.0):
        previous_error=float('inf')
        for steps in (100,200,400,1200):
            h=period/steps
            def jacobian(*,h=None,**kwargs):
                return sparse.csc_matrix([[2.0/h-rate]])
            op=EmtFloquetOperator(problem=ScalarProblem(),trajectory=np.zeros((steps+1,1)),
                h=h,n_states=1,method=DynamicIntegrationMethod.DaeTrapezoidal,
                jac_evaluator=jacobian,static_params=np.empty(0),n_event_params=0,
                t_trajectory=np.arange(steps+1)*h,d_trajectory=np.zeros((steps+1,1)))
            multiplier=float(op.matvec(np.ones(1))[0])
            exponent=math.log(abs(multiplier))/period
            error=abs(exponent-rate)
            # El contracte actual comença la història tangent derivada a zero.
            # Es verifica el guany discret real i la convergència cap a exp(a*T).
            discrete=(1/(1-rate*h/2))*((1+rate*h/2)/(1-rate*h/2))**(steps-1)
            assert math.isclose(multiplier,discrete,rel_tol=1e-10,abs_tol=1e-12)
            assert exponent*rate>0 and error<previous_error
            previous_error=error
            reports.append({'rate':rate,'steps':steps,'target_multiplier':math.exp(rate*period),
                'multiplier':multiplier,'exponent':exponent,'absolute_exponent_error':error})
    return reports


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    reports=run_reference()
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(reports,indent=2)+'\n')
    for row in reports:
        print(f"a={row['rate']:+g} steps={row['steps']:4d} lambda={row['exponent']:+.9f} error={row['absolute_exponent_error']:.3g}")
