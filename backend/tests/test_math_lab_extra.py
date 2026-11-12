import math
import unittest
from app.api.math_lab_extra import series, surface, SurfaceInput
from app.api.math_lab import calculus


class ExtraLabTests(unittest.TestCase):
    def test_geometric_sum_and_divergent_boundary(self):
        result=series({'kind':'geometric','n':40,'parameter':.5})
        self.assertAlmostEqual(result['partial_sums'][-1],2,places=10)
        self.assertEqual(result['limit'],2)
        for ratio in [-1,1,2]:
            self.assertFalse(series({'kind':'geometric','n':20,'parameter':ratio})['converges'])
        self.assertEqual(series({'kind':'geometric','n':2,'parameter':0})['terms'],[1,0])

    def test_p_and_alternating_bounds(self):
        self.assertFalse(series({'kind':'p','n':30,'parameter':1})['converges'])
        result=series({'kind':'p','n':30,'parameter':2})
        self.assertAlmostEqual(result['limit'],math.pi**2/6)
        result=series({'kind':'alternating','n':50,'parameter':1})
        self.assertAlmostEqual(result['limit'],math.log(2))
        self.assertLessEqual(result['error'],result['remainder_bound'])
        with self.assertRaises(ValueError):series({'kind':'p','n':10,'parameter':0})

    def test_long_taylor_sum_avoids_factorial_overflow(self):
        for x in [-5,0,5]:
            result=series({'kind':'exp','n':300,'parameter':x})
            self.assertAlmostEqual(result['partial_sums'][-1],math.exp(x),places=10)

    def sample(self,expression,x=1,y=1):
        return surface({'expression':expression,'radius':2,'resolution':15,'x':x,'y':y})

    def test_surface_values_and_partials(self):
        result=self.sample('x^2+y^2')
        self.assertEqual(result['point'],{'x':1,'y':1,'z':2,'dx':2,'dy':2})
        self.assertEqual(result['valid_points'],225)
        result=self.sample('x^2-y^2')
        self.assertEqual(result['point']['dy'],-2)
        self.assertEqual(self.sample('5')['point']['dx'],0)

    def test_domain_holes_and_nonsmooth_partial(self):
        result=self.sample('x/x',0,0)
        self.assertIsNone(result['point']['z'])
        self.assertLess(result['valid_points'],225)
        result=self.sample('abs(x)+y',0,0)
        self.assertIsNone(result['point']['dx'])
        self.assertEqual(result['point']['dy'],1)
        result=self.sample('sqrt(x^2+y^2)',0,0)
        self.assertIsNone(result['point']['dx'])
        self.assertIsNone(result['point']['dy'])
        self.assertIsNone(self.sample('sqrt(x)',0,0)['point']['dx'])

    def test_parameter_changes_and_larger_domain(self):
        for a,b in [(2,-3),(0,0),(-10,10)]:
            payload=SurfaceInput(expression='a*x^2+b*y^2',a=a,b=b,radius=20,x=2,y=3,resolution=15).model_dump()
            result=surface(payload)
            self.assertEqual(result['point']['z'],a*4+b*9)
            self.assertEqual(result['point']['dx'],a*4)
            self.assertEqual(result['point']['dy'],b*6)
            self.assertEqual(result['valid_points'],225)
        result=series({'kind':'geometric','n':300,'parameter':10})
        self.assertTrue(all(math.isfinite(v) for v in result['partial_sums']))

    def test_invalid_observation_still_returns_current_function_graph(self):
        payload={'expression':'log(x)','mode':'derivative','x':-1,'h':.1,'a':0,'b':1,'n':20,'graph_on_invalid_observation':True}
        result=calculus(payload)
        self.assertIn('warning',result)
        self.assertTrue(any(y is not None for x,y in result['samples']))
        self.assertNotIn('tangent',result)
        payload.update(expression='1/x',mode='integral',a=-1,b=1)
        result=calculus(payload)
        self.assertIn('warning',result)
        self.assertNotIn('sum',result)
        self.assertTrue(any(y is not None for x,y in result['samples']))

    def test_custom_series_samples_and_unknown_convergence(self):
        result=series({'kind':'custom','n':40,'parameter':2,'expression':'1/n^p'})
        self.assertAlmostEqual(result['partial_sums'][-1],sum(1/k**2 for k in range(1,41)))
        self.assertIsNone(result['converges'])
        self.assertIsNone(result['limit'])
        result=series({'kind':'custom','n':10,'parameter':1,'expression':'(-1)^(n+1)/n'})
        self.assertEqual(result['terms'][:3],[1,-.5,1/3])
        for expr in ['1/(n-2)','sqrt(2-n)','(n-2)/(n-2)','__import__("os")']:
            with self.assertRaises((ValueError,SyntaxError)):
                series({'kind':'custom','n':5,'parameter':1,'expression':expr})

    def test_custom_expression_is_not_code(self):
        for expression in ['__import__("os")','x.__class__','x^99','sin(x,y)']:
            with self.assertRaises((ValueError,SyntaxError)):self.sample(expression)


if __name__=='__main__':unittest.main()
