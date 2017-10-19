import sys
sys.path.append('/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/python_libevent-0.9.2-py2.7-macosx-10.6-intel.egg')

from pprint import pprint
from throttle import TaskThrottler
import datetime
import dns
import libevent
import random
import socket
import sys
import time
import timeout
DNS_PORT = 53

base = libevent.Base()

# Use top 1 million domains as test data
print "Reading domain list..."
domain_list = [l.split(",")[1].strip()+"." for l in open('opendns-top-1m.csv')]
print "Read domain list."

public_dns_servers = [
	"8.8.8.8",
	# "1.2.3.4"
]

domain_state = {
	# "www.google.com" : {
	# 	"ip" : "216.58.211.110",
	# 	"status" : "DONE", # "DIDNOTEXIST" / "DONE" / "STARTED"
	# 	"started" : "123456789" # some timestamp
	# }
}

# At first nothing is resolved yet.
def set_all_domains_to_initial_state():
	for domain in domain_list:
		domain_state[domain] = {
			"ip" : None,
			"status" : None,
			"started" : None
		}

def domain_resolved(data):
	domain = data['domain']
	print "domain_resolved %s" % domain
	domain_state[domain].update({
		"status" : "DONE",
		"ip" : "255.255.255.255"
	})
	pprint(domain_state[domain])
	time.sleep(1)
	data['callback']()

# event = None

events = [] # just for reference counting issue with libevent

def send_nonblocking_packet(data, ip_address = '8.8.8.8'):
	# global event # Somehow without a global reference, event won't work (issue with reference counting?)
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.setblocking(False)
	event = libevent.Event(base, s.fileno(), libevent.EV_READ|libevent.EV_PERSIST, event_ready, s)
	event.add(1)
	events.append(event)
	dest = (ip_address, DNS_PORT)
	s.sendto(data, dest)

def run_task(dns_server, task_completed_callback):
	try:
		next_domain_to_resolve = domain_list.pop()
		print "Should run next task %s for %s" % (next_domain_to_resolve, dns_server)
		task_was_available = True

		# Update domain state so that later if resolution fails we'll know to retry
		domain_state[next_domain_to_resolve].update({
			"status" : "STARTED",
			"started" : time.time()
		})
		pprint(domain_state[next_domain_to_resolve])

		# Should send DNS packet to resolve next_domain_to_resolve with dns_server
		packet = dns.make_dns_query_packet(next_domain_to_resolve)
		send_nonblocking_packet(packet, dns_server)

		# Simulate DNS resolving latency
		# delay = random.betavariate(1, 5) # Mostly low latency, sometimes not.
		# timeout.set(domain_resolved, delay, data = {
		# 	'callback' : task_completed_callback,
		# 	'domain' : next_domain_to_resolve
		# })

	except IndexError:
		print "All domains have been assigned"
		task_was_available = False
	return task_was_available

def all_done():
	states = domain_state.values()
	return all([s['status'] in ['DONE', 'DIDNOTEXIST'] for s in states])

def print_progress():
	states = domain_state.values()
	done_count = sum([s['status'] in ['DONE', 'DIDNOTEXIST'] for s in states])
	total_count = len(states)
	percentage = done_count * 100.0 / total_count
	print "%.4f%% done" % percentage

def resolve_all():
	set_all_domains_to_initial_state()
	throttlers = dict([(ip, TaskThrottler(run_task, ip)) for ip in public_dns_servers])
	while not all_done():
		for ip, throttler in throttlers.items():
			# print ip, "tick"
			throttler.tick()
		time.sleep(0.1)
		timeout.poll()

		# NONBLOCK means return immediately if no events available
		# EVLOOP_NO_EXIT_ON_EMPTY would mean block indefinitely even if no events available
		base.loop(libevent.EVLOOP_NONBLOCK)

	print
	print
	print "ALL DONE:"

def event_ready(event, fd, type_of_event, s):
	# if type_of_event & libevent.EV_TIMEOUT:
	# 	print "Timeout"
	# 	exit()

	if type_of_event & libevent.EV_READ:
		print "Received DNS packet!"
		response, addr = s.recvfrom(1024)
		response_hexed = " ".join(hex(ord(c)) for c in response)
		print "Parsing response"
		did_domain_exist, domain, ip_address = dns.parse_response(response)
		print "Domain did %sexist." % "not " if not did_domain_exist else ""
		print "Domain in question was %s." % domain

		state = domain_state[domain + '.']
		if did_domain_exist:
			state.update({
				'ip' : ip_address,
				'status' : 'DONE'
			})
		else:
			state.update({
				'status' : 'DIDNOTEXIST'
			})
		print "Updated state for '%s'" % domain
		print_progress()

resolve_all()
for domain, state in domain_state.items():
	if state['status'] == 'DONE':
		print "%s\t%s" % (domain, state['ip'])
	if state['status'] == 'DIDNOTEXIST':
		print "%s\t%s" % (domain, '-')


