import time
import sys
import timeout

class PublicDNSServer():
	def __init__(self, ip = '8.8.8.8'):
		self.ip = ip
		self.queries_per_second = 1.0
		self.next_attempt_timestamp = 0

		# self.how_many_queries_per_second_can_this_server_resolve

		self.current_queries = 0
		self.latest_query_timestamp = None
		self.timestamps = []
		self.falloff_seconds = 60

	def tick(self):
		sys.stdout.write(".")
		sys.stdout.flush()
		# If server resolve say 5 domains per second
		# Then start off by sending it a task every 1/5 seconds
		now = time.time()
		if now > self.next_attempt_timestamp:
			self.task_assigned()
			self.next_attempt_timestamp = now + 1 / float(self.queries_per_second)

	def task_timestamp_falloff(self):
		falloff, now = self.falloff_seconds, time.time()
		print len(self.timestamps),
		self.timestamps = [ts for ts in self.timestamps if now - ts < falloff]
		print " -> ",
		print len(self.timestamps)

	# def resolve_next_domain():
	# 	domain = domain_list.pop()

	def task_assigned(self):
		print
		print "Task assigned"
		self.current_queries += 1
		self.timestamps.append(time.time())

		# resolve_next_domain()

		# Simulate response latency
		delay = random.betavariate(1, 5) # Mostly low latency, sometimes not.
		timeout.set(self.task_completed, delay)

	def current_per_second_usage(self):
		self.task_timestamp_falloff()
		return len(self.timestamps) / float(self.falloff_seconds)

	def task_completed(self):
		print "Task completed"
		self.current_queries -= 1
		if self.current_queries < 0:
			print "Current queries < 0, panic"
			exit()
