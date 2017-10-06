import time

timeouts = []

def set(callback, delay):
	print "Timeout set"
	now = time.time()
	timeouts.append({
		'time' : now + delay,
		'callback' : callback
	})

def poll():
	now = time.time()
	for timeout in timeouts:
		if timeout['time'] < now:
			print "Timeout firing"
			timeout['callback'].__call__()
			timeouts.remove(timeout)


