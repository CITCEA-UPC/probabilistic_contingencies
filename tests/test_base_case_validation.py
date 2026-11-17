"""Mètriques de periodicitat per a la validació del cas base."""
import math
import unittest
from validation.base_case import cycle_closure


class ClosureTests(unittest.TestCase):
    def test_periodic_rotor_angle_is_compared_modulo_two_pi(self):
        result=cycle_closure([[.2,1.0],[.2+2*math.pi,1.0]],['theta_gen0','omega_gen0'],2)
        self.assertLess(result['max_state_error'],1e-12)
        self.assertEqual(result['wrapped_angles'],['theta_gen0'])

    def test_angle_error_is_not_hidden_by_many_rotations(self):
        result=cycle_closure([[1000*math.pi],[1000*math.pi+2*math.pi+.01]],['theta'],1)
        self.assertAlmostEqual(result['max_state_error'],.01)

    def test_nonperiodic_state_and_algebraic_variable_are_reported_separately(self):
        result=cycle_closure([[2.,10.],[3.,20.]],['omega','voltage'],1)
        self.assertAlmostEqual(result['max_state_error'],1/3)
        self.assertAlmostEqual(result['max_all_variables_error'],.5)
        self.assertEqual(result['largest_errors'][0]['variable'],'voltage')

    def test_invalid_or_nonfinite_trajectories_are_rejected(self):
        for data,names,n in [([],['x'],1),([[1]],['x'],1),([[1],[2]],['x'],2),
                             ([[1],[2,3]],['x'],1),([[1],[float('nan')]],['x'],1)]:
            with self.subTest(data=data),self.assertRaises(ValueError):
                cycle_closure(data,names,n)


if __name__=='__main__': unittest.main()
