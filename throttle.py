import time
import sys
import timeout

class TaskThrottler():
	def __init__(self):
		self.throttle_per_second = 1.0
		self.next_task_timestamp = 0

		self.currently_running_task_count = 0
		self.latest_query_timestamp = None

		# Keep track of past of when each task was completed, so we can know
		# how many are getting resolved per second. 
		self.timestamps = []

		# This is how many seconds worth of data we'll consider when deciding
		# the current throughput.
		self.timestamp_window = 60 # n

	def tick(self):
		sys.stdout.write(".")
		sys.stdout.flush()
		# If server resolve say 5 domains per second
		# Then start off by sending it a task every 1/5 seconds
		now = time.time()
		if now > self.next_task_timestamp:
			self.task_assigned()
			self.next_task_timestamp = now + 1 / float(self.throttle_per_second)

	def remove_timestamps_beyond_window(self):
		falloff, now = self.timestamp_window, time.time()
		self.timestamps = [ts for ts in self.timestamps if now - ts < falloff]

	def current_throughput(self):
		self.remove_timestamps_beyond_window()
		return len(self.timestamps) / float(self.timestamp_window)

	def task_assigned(self):
		print
		print "Task assigned"
		self.currently_running_task_count += 1

		# Simulate task completion latency
		delay = random.betavariate(1, 5) # Mostly low latency, sometimes not.
		timeout.set(self.task_completed, delay)	

	def task_completed(self):
		self.timestamps.append(time.time())
		print "Task completed"
		self.currently_running_task_count -= 1
		if self.currently_running_task_count < 0:
			print "Current queries < 0, panic"
			exit()
