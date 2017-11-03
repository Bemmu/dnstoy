import time
import sys
import math

class TaskThrottler():
	def __init__(self, run_task_callback, data_to_pass_to_callback):
		self.run_task_callback = run_task_callback
		self.data_to_pass_to_callback = data_to_pass_to_callback

		self.throttle_per_second = 20.0
		self.prev_task_timestamp = time.time() - 1 / float(self.throttle_per_second)

		self.currently_running_task_count = 0

		# Keep track of past of when each task was completed, so we can know
		# how many are getting resolved per second. 
		self.timestamps = []

		# This is how many seconds worth of data we'll consider when deciding
		# the current throughput.
		self.timestamp_window = 10 # n

		self.paused = False

	# Attempt more tasks per second
	def faster(self, factor = 1.1):
		print "FASTER!"
		self.throttle_per_second *= factor

	def tick(self):
		if self.paused:
			return

		sys.stdout.write(".")
		sys.stdout.flush()

		# How many tasks should we have run since we last checked?
		elapsed = time.time() - self.prev_task_timestamp
		tasks_to_run = int(math.floor(elapsed * self.throttle_per_second))

		# Run 'em
		if tasks_to_run >= 1:
			self.prev_task_timestamp = time.time()
			for _ in range(0, tasks_to_run):
				self._run_task()

	def _remove_timestamps_beyond_window(self):
		falloff, now = self.timestamp_window, time.time()
		self.timestamps = [ts for ts in self.timestamps if now - ts < falloff]

	def current_throughput(self):
		self._remove_timestamps_beyond_window()
		return len(self.timestamps) / float(self.timestamp_window)

	def _run_task(self):
		task_was_available = self.run_task_callback(self.data_to_pass_to_callback, self.task_completed)

		if task_was_available:
			print
			print "Task assigned"
			self.currently_running_task_count += 1
		else:
			print "No task was available"

	def task_completed(self):
		self.timestamps.append(time.time())
		print "Task completed"
		self.currently_running_task_count -= 1
		if self.currently_running_task_count < 0:
			print "Current queries < 0, panic"
			exit()
