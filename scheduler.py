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
from throttle import TaskThrottler
DNS_PORT = 53

domain_list = [
	"www.google.com.",
	"google.com.",
	"yahoo.com"
]

resolved_ip_addresses = {
	# "www.google.com" : "1.2.3.4" etc.
}

def run_task(data):
	print "Should run next task for %s" % data

t = TaskThrottler(run_task, '8.8.8.8')
while True:
	print "Loop..."
	t.tick()
	time.sleep(0.1)

exit()


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
		did_domain_exist = dns.parse_response(response)
		print "Domain did %sexist." % "not " if not did_domain_exist else ""

base = libevent.Base()
# data = dns.make_dns_query_packet("google.com.")
data = dns.make_dns_query_packet("totallynonexistantdomain123434875.com.")

public_dns_servers = [
	ThrottledDNSServer()
]

server = ThrottledDNSServer()

def resolve_domains(domain_list):
	print "Resolving..."
	while True:
		timeout.poll()
		for server in public_dns_servers:
			server.tick()
		time.sleep(0.01)

# resolve_domains(domain_list)

event = None

def send_nonblocking_packet(data):
	global event # Somehow without a global reference, event won't work (issue with reference counting?)
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.setblocking(False)
	event = libevent.Event(base, s.fileno(), libevent.EV_READ|libevent.EV_PERSIST, event_ready, s)
	event.add(1)
	dest = ('8.8.8.8', DNS_PORT)
	s.sendto(data, dest)

send_nonblocking_packet(data)

while True:
	print "Loop..."
	time.sleep(0.1)

	# NONBLOCK means return immediately if no events available
	# EVLOOP_NO_EXIT_ON_EMPTY would mean block indefinitely even if no events available
	base.loop(libevent.EVLOOP_NONBLOCK)
