#######################################################################
#
# static - MakeStatic and MakeClass
#
# These functions are used to make all the instance methods in a class
# into static or class methods.
#

class StaticMethodsError(Exception):
	pass

def MakeStatic(cls):
	"""turn instance methods into static ones

	The methods (that don't begin with _) of any class that
	subclasses this will be turned into static methods.

	"""
	for name in dir(cls):
		if name[0] != "_":
			cls.__dict__[name] = staticmethod(cls.__dict__[name])


def MakeClass(cls):
	"""Turn instance methods into classmethods.  Ignore _ like above"""
	for name in dir(cls):
		if name[0] != "_":
			cls.__dict__[name] = classmethod(cls.__dict__[name])
