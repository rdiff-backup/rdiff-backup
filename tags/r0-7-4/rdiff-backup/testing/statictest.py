import unittest, types
execfile("commontest.py")
rbexec("static.py")


class D:
	def foo(x, y):
		return x, y
	def bar(self, x):
		return 3, x
	def _hello(self):
		return self

MakeStatic(D)


class C:
	_a = 0
	def get(cls):
		return cls._a
	def inc(cls):
		cls._a = cls._a + 1

MakeClass(C)


class StaticMethodsTest(unittest.TestCase):
	"""Test StaticMethods module"""
	def testType(self):
		"""Methods should have type StaticMethod"""
		assert type(D.foo) is types.FunctionType
		assert type(D.bar) is types.FunctionType

	def testStatic(self):
		"""Methods should be callable without instance"""
		assert D.foo(1,2) == (1,2)
		assert D.bar(3,4) == (3,4)

	def testBound(self):
		"""Methods should also work bound"""
		d = D()
		assert d.foo(1,2) == (1,2)
		assert d.bar(3,4) == (3,4)

	def testStatic_(self):
		"""_ Methods should be untouched"""
		d = D()
		self.assertRaises(TypeError, d._hello, 4)
		assert d._hello() is d


class ClassMethodsTest(unittest.TestCase):
	def test(self):
		"""Test MakeClass function"""
		assert C.get() == 0
		C.inc()
		assert C.get() == 1
		C.inc()
		assert C.get() == 2
	

if __name__ == "__main__":
	unittest.main()
