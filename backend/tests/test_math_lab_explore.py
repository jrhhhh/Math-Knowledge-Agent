import math
import unittest
import numpy as np
from app.api.math_lab_explore import ExploreInput, explore, rational_matrix


def run(kind,**kwargs):return explore(ExploreInput(kind=kind,**kwargs).model_dump())


class ExploreTests(unittest.TestCase):
    def test_taylor_and_nonsmooth_rejection(self):
        d=run('taylor',expression='exp(x)',order=3)
        self.assertEqual(d['curves'][1]['points'][150],[0,1])
        for expression in ['abs(x)','sqrt(x)','1/x']:
            with self.assertRaises(ValueError):run('taylor',expression=expression,center=0)

    def test_sequence_error_is_sampled(self):
        d=run('sequence',expression='x^n',index=100,left=0,right=.9)
        self.assertAlmostEqual(d['max_sample_error'],.9**100)
        self.assertTrue(d['within_band'])
        d=run('sequence',expression='x^n',index=100,left=0,right=1)
        self.assertEqual(d['max_sample_error'],1)
        self.assertFalse(d['within_band'])
        d=run('sequence',expression='n*x/(1+n^2*x^2)',index=300,left=0,right=1)
        self.assertTrue(math.isfinite(d['max_sample_error']))

    def test_path_counterexample(self):
        f='x^2*y/(x^4+y^2)'
        d=run('path',expression=f,path_y='t^2')
        self.assertEqual(d['right_limit'],r'\frac{1}{2}')
        self.assertTrue(all(abs(row['value']-.5)<1e-12 for row in d['table']))
        self.assertEqual(run('path',expression=f,path_y='0')['right_limit'],'0')
        with self.assertRaises(ValueError):run('path',expression=f,path_x='t+1')
        self.assertIn('未确认',run('path',expression='sqrt(x)',path_y='0')['left_limit'])

    def test_gradient_nonsmooth(self):
        d=run('gradient',expression='x^2+y^2',angle=0)
        self.assertAlmostEqual(d['directional_candidate'],2)
        self.assertEqual(d['point']['dy'],2)
        self.assertIsNone(run('gradient',expression='abs(x)+y',x=0,y=0)['directional_candidate'])

    def test_system_exact_steps_and_solution_types(self):
        d=run('system',matrix=[['1','1'],['2','-1']],rhs=['3','0'])
        self.assertEqual(d['status'],'唯一解')
        self.assertEqual(d['steps'][-1]['matrix'],[['1','0','1'],['0','1','2']])
        self.assertEqual(run('system',matrix=[['1','2'],['2','4']],rhs=['1','3'])['status'],'无解')
        d=run('system',matrix=[['1','2','3'],['2','4','6']],rhs=['1','2'])
        self.assertEqual(d['status'],'无穷多解')
        self.assertEqual(d['free_variables'],2)
        self.assertIn('交换',run('system',matrix=[['0','1'],['1','0']],rhs=['2','3'])['steps'][1]['label'])
        with self.assertRaises(ValueError):run('system',rhs=['1'])

    def test_quadratic_axes_and_classification(self):
        d=run('quadratic');Q=np.array(d['orthogonal'])
        self.assertEqual(d['classification'],'正定')
        self.assertTrue(np.allclose(Q.T@np.array([[2,1],[1,2]])@Q,np.diag(d['eigenvalues'])))
        self.assertEqual(run('quadratic',matrix=[['1','0'],['0','-1']])['classification'],'不定')
        self.assertEqual(run('quadratic',matrix=[['0','0'],['0','0']])['classification'],'半正定')
        with self.assertRaises(ValueError):run('quadratic',matrix=[['1','2'],['0','1']])

    def test_svd_and_iteration(self):
        for matrix in [[['1','2'],['0','1']],[['0','0'],['0','0']],[['0','-1'],['1','0']]]:
            d=run('decomposition',matrix=matrix,iterations=4);A=np.array(matrix,dtype=float)
            self.assertTrue(np.allclose(np.array(d['U'])@np.diag(d['singular_values'])@np.array(d['Vt']),A))
            self.assertTrue(np.allclose(d['trajectory'][-1],np.linalg.matrix_power(A,4)@np.ones(2)))
        self.assertEqual(run('decomposition',matrix=[['0.5','0'],['0','0.5']])['spectral_radius'],.5)

    def test_security_and_invalid_ranges(self):
        for expr in ['__import__("os")','x.__class__']:
            with self.assertRaises((ValueError,SyntaxError)):run('taylor',expression=expr)
        with self.assertRaises(ValueError):run('sequence',left=1,right=0)
        with self.assertRaises(ValueError):rational_matrix([['1/0']])
        with self.assertRaises(ValueError):rational_matrix([['1'],['1','2']])


if __name__=='__main__':unittest.main()
