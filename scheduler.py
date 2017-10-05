import sys
sys.path.append('/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/python_libevent-0.9.2-py2.7-macosx-10.6-intel.egg')

import socket
import libevent
import dns
import datetime
import sys
import time
import timeout
import random
DNS_PORT = 53

# Based on example https://github.com/fancycode/python-libevent/blob/master/samples/hello.py
def event_ready(event, fd, what, s):
	print "event_ready"

	if what & libevent.EV_TIMEOUT:
		print "Timeout"
		exit()

	if what & libevent.EV_READ:
		print "Received DNS packet!"
		response, addr = s.recvfrom(1024)
		response_hexed = " ".join(hex(ord(c)) for c in response)
		print "Parsing response"
		dns.parse_response(response)

base = libevent.Base()
data = dns.make_dns_query_packet("google.com.")

class PublicDNSServer():
	def __init__(self, ip = '8.8.8.8'):
		self.ip = ip
		self.attempt_queries_per_second = 1.0
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
			self.next_attempt_timestamp = now + 1 / float(self.attempt_queries_per_second)

	def task_timestamp_falloff(self):
		falloff, now = self.falloff_seconds, time.time()
		print len(self.timestamps),
		self.timestamps = [ts for ts in self.timestamps if now - ts < falloff]
		print " -> ",
		print len(self.timestamps)

	def task_assigned(self):
		print
		print "Task assigned"
		self.current_queries += 1
		self.timestamps.append(time.time())

		# Simulate response latency
		delay = random.betavariate(1, 5) # Mostly low latency, sometimes not.
		timeout.set(self.task_completed, delay)

	def current_per_second_usage(self):
		self.task_timestamp_falloff()
		return len(self.timestamps) / float(self.falloff_seconds)

	def task_completed(self):
		self.current_queries -= 1
		if self.current_queries < 0:
			print ""

public_dns_servers = [
	PublicDNSServer()
]

server = PublicDNSServer()

domain_list = [
	"www.google.com.",
	"google.com.",
	"yahoo.com"
]

map_domains_to_ip_addresses = {}

def resolve_domains(domain_list):
	print "Resolving..."
	while True:
		for server in public_dns_servers:
			server.tick()
		time.sleep(0.01)

resolve_domains(domain_list)

# def send_nonblocking_packet(data):
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s = AnotherSocket(socket.AF_INET, socket.SOCK_DGRAM)
s.setblocking(False)
print s.fileno()
event = libevent.Event(base, s.fileno(), libevent.EV_READ|libevent.EV_PERSIST, event_ready, s)
event.add(5)
dest = ('8.8.8.8', DNS_PORT)
s_ip, s_port = s.getsockname()
print "Sending DNS packet via UDP %s:%s -> %s:%s" % (s_ip, s_port, dest[0], dest[1])
s.sendto(data, dest)

# send_nonblocking_packet(data)
base.loop()



