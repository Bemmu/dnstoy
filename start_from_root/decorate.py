import types

# Decorate functions so they display when they are called, for debug purposes.
def decorate_global_functions_with_printouts(globals):
	functions = [(k, v) for k, v in globals.items() if type(v) == types.FunctionType]
	for function_name, function in functions:
		def make_function(function_name, function):
			def f(*args, **kwargs):
				print "%s" % function_name
				function(*args, **kwargs)
			return f
			# print "Setting %s to %s" % (function_name, f)
		globals[function_name] = make_function(function_name, function)

