import unittest
from app.api.math_lab import expression, calculus, matrix_analysis
import sympy as s

class MathLabTests(unittest.TestCase):
    def calc(self,expr,**kwargs):
        return calculus(dict(expression=expr,mode='derivative',x=1,h=.1,a=0,b=1,n=20,**kwargs))
    def test_parser_rejects_code_and_large_power(self):
        for text in ["__import__('os')",'x.__class__','[x for x in x]','sin(x,1)','x^999','1/0','unknown(x)']:
            with self.assertRaises((ValueError,SyntaxError)):expression(text)
        self.assertEqual(expression('2^x').subs(s.Symbol('x',real=True),2),4)
    def test_derivative_polynomial_and_nondifferentiable_point(self):
        self.assertAlmostEqual(self.calc('x^3')['tangent'],3)
        data=calculus(dict(expression='abs(x)',mode='derivative',x=0,h=.1,a=-1,b=1,n=20))
        self.assertIsNone(data['tangent'])
        data=calculus(dict(expression='sqrt(x)',mode='derivative',x=0,h=.1,a=0,b=1,n=20))
        self.assertIsNone(data['tangent'])
    def test_integral_sign_domain_and_non_elementary_primitive(self):
        def integral(expr,a,b):return calculus(dict(expression=expr,mode='integral',x=1,h=.1,a=a,b=b,n=20))
        self.assertAlmostEqual(integral('x^2',0,1)['exact_value'],1/3)
        self.assertAlmostEqual(integral('x^2',1,0)['exact_value'],-1/3)
        self.assertAlmostEqual(integral('abs(x)',-1,1)['exact_value'],1)
        self.assertGreater(integral('exp(-x^2)',-1,1)['exact_value'],1)
        for expr,a,b in [('1/x',-1,1),('log(x)',-1,1),('tan(x)',0,2)]:
            with self.assertRaises(ValueError):integral(expr,a,b)
    def test_periodic_domains_and_trig_primitives(self):
        import math
        for expr,x,a,b in [('tan(x)',.5,0,1),('cot(x)',1,.5,1),('sec(x)',.5,0,1),('csc(x)',1,.5,1)]:
            data=calculus(dict(expression=expr,mode='derivative',x=x,h=.1,a=a,b=b,n=20))
            self.assertIsNotNone(data['tangent'])
            data=calculus(dict(expression=expr,mode='integral',x=x,h=.1,a=a,b=b,n=20))
            self.assertIsNotNone(data['exact_value'])
            self.assertAlmostEqual(data['sum'],data['exact_value'],delta=.002)
        for expr,a,b in [('tan(2*x+1)',0,1),('cot(x)',-1,1),('sec(x)',0,2),('csc(x)',-1,1)]:
            with self.assertRaises(ValueError):calculus(dict(expression=expr,mode='integral',x=.5,h=.1,a=a,b=b,n=20))
        with self.assertRaises(ValueError):self.calc('log(tan(x))')
        self.assertAlmostEqual(self.calc('tan(x)')['tangent'],1/math.cos(1)**2)
        for expr in ['log(-1)','sec(pi/2)','sqrt(-1)*x']:
            with self.assertRaises(ValueError):self.calc(expr)
    def test_simplification_preserves_original_domain(self):
        for expr,x in [('x/x',0),('(x^2-1)/(x-1)',1),('log(x)-log(x)',-1),('sqrt(x)^2',-1),('tan(x)-tan(x)',1.5707963267948966)]:
            with self.assertRaises(ValueError):calculus(dict(expression=expr,mode='derivative',x=x,h=.1,a=0,b=1,n=20))
        data=self.calc('x/x')
        self.assertEqual(data['tangent'],0)
        self.assertIsNone(next(y for x,y in data['samples'] if x==0))
        with self.assertRaises(ValueError):calculus(dict(expression='x/x',mode='integral',x=1,h=.1,a=-1,b=1,n=20))
    def test_matrix_principal_minors_and_exact_fraction(self):
        data=matrix_analysis({'matrix':[['2','1'],['1','2']]})
        self.assertEqual(data['determinant'],'3');self.assertEqual(data['rank'],2)
        self.assertEqual([v['value'] for v in data['principal_minors']],['2','2','3'])
        self.assertEqual(data['leading_minors'],['2','3']);self.assertTrue(data['positive_definite'])
        self.assertTrue(all(data['checks'].values()))
        self.assertEqual(matrix_analysis({'matrix':[['1/3','0'],['0','1/2']]})['determinant'],'1/6')
    def test_complex_defective_singular_and_high_order(self):
        rotation=matrix_analysis({'matrix':[['0','-1'],['1','0']]})
        self.assertEqual(rotation['directions'],[]);self.assertFalse(rotation['diagonalizable_real']);self.assertTrue(rotation['diagonalizable_complex'])
        jordan=matrix_analysis({'matrix':[['1','1'],['0','1']]})
        self.assertFalse(jordan['diagonalizable_complex']);self.assertIn('2',jordan['minimal'])
        singular=matrix_analysis({'matrix':[['1','2'],['2','4']]})
        self.assertIsNone(singular['inverse']);self.assertEqual(singular['nullity'],1)
        four=matrix_analysis({'matrix':[['1','0','0','0'],['0','2','0','0'],['0','0','3','0'],['0','0','0','4']]})
        self.assertEqual(len(four['principal_minors']),15);self.assertTrue(all(four['checks'].values()))
        for matrix in [[['1','2']], [['x']], [['1/0']]]:
            with self.assertRaises((ValueError,ZeroDivisionError)):matrix_analysis({'matrix':matrix})
