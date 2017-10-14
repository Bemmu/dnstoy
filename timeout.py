import time

timeouts = []

def set(callback, delay, data = None):
	print "Timeout set"
	now = time.time()
	timeouts.append({
		'time' : now + delay,
		'callback' : callback,
		'data' : data
	})

def poll():
	now = time.time()
	for timeout in timeouts:
		if timeout['time'] < now:
			print "Timeout firing"
			timeout['callback'].__call__(data = timeout['data'])
			timeouts.remove(timeout)


