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
import resource
import os
import subprocess
import collections 

DNS_PORT = 53
RETRY_THRESHOLD = 5 # seconds

# Processes have a limit of how many files are allowed to be open. Opening a socket
# bumps against this limit, crossing it means program gets aborted.
def estimate_how_many_more_files_can_be_opened():
	max_open_files = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
	cmd = ['lsof', '-p', str(os.getpid())]
	currently_open_files = len(subprocess.check_output(cmd).split("\n"))
	return max_open_files - currently_open_files

base = libevent.Base()
max_socket_count = estimate_how_many_more_files_can_be_opened()

# Use a selection of top 1 million domains as test data
print "Reading domain list..."
domain_list = [l.split(",")[1].strip()+"." for l in open('opendns-top-1m.csv')][0:5]
domain_list.append("rutracker.org.")
# print domain_list
# domain_list = ["rutracker.org"]
print "Read domain list."

public_dns_servers = [
	"109.69.8.51",
	"8.8.8.8",
	"84.200.69.80",
	"208.67.222.222",
	"209.244.0.3",
	"64.6.64.6",
	"8.26.56.26",
	"199.85.126.10",
	"81.218.119.11",
	"195.46.39.39",
	"23.94.60.240",
	"208.76.50.50",
	"216.146.35.35",
	"37.235.1.174",
	"198.101.242.72",
	"77.88.8.8",
	"91.239.100.100",
	"74.82.42.42",
	"109.69.8.51"
]

# Keep track of which servers have trouble giving responses
dns_server_timeout_count = collections.defaultdict(int)

domain_state = {
	# "www.google.com" : {
	# 	"resolved_ip" : "216.58.211.110",
	# 	"status" : "DONE", # "DIDNOTEXIST" / "DONE" / "STARTED"
	# 	"started" : "123456789" # some timestamp
	# }
}

# List of domains that are in STARTED state, for a quicker
# lookup when scanning for stalled domains.
started_domains = []

throttlers = None

# At first nothing is resolved yet.
def set_all_domains_to_initial_state():
	for domain in domain_list:
		domain_state[domain] = {
			"resolved_ip" : None,
			"status" : None,
			"started" : None
		}

# Haven't gotten a response? Try again.
def make_stalled_domains_get_retried_later():
	for domain in started_domains:
		# If took too long, reset to initial state, which will 
		# make this domain get retried at a later point.
		try:
			elapsed = time.time() - domain_state[domain]['started']
			if elapsed > RETRY_THRESHOLD:

				# Keep track of how many times each server timed out
				server_ip = domain_state[domain]['server_ip']
				dns_server_timeout_count[server_ip] += 1

				# This domain can be tried again by other servers
				domain_state[domain] = {
					"resolved_ip" : None,
					"status" : None,
					"started" : None
				}
				domain_list.append(domain)

				# So that we don't check this again right away
				started_domains.remove(domain)
		except Exception, e:
			print str(e)
			import code; code.interact(local=locals() + globals())

events = [] # just for reference counting issue with libevent

# One socket for each name server.
sockets = {}

def send_nonblocking_packet(data, ip_address = '8.8.8.8'):

	try:
		s = sockets[ip_address]
		print "Reusing socket"
	except KeyError:
		print "Opening new socket"
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sockets[ip_address] = s
		print "%d / %d sockets open" % (len(sockets), max_socket_count)
		s.setblocking(False)
		event = libevent.Event(base, s.fileno(), libevent.EV_READ|libevent.EV_PERSIST, event_ready, s)
		event.add(1)

		# Without this the event is garbage collected (issue with reference counting?)
		events.append(event)

	dest = (ip_address, DNS_PORT)
	s.sendto(data, dest)
	print "Sent packet to %s" % dest[0]

def run_task(dns_server, task_completed_callback):
	try:		
		next_domain_to_resolve = domain_list.pop()

		print "Should run next task %s for %s" % (next_domain_to_resolve, dns_server)
		task_was_available = True

		# Update domain state so that later if resolution fails we'll know to retry
		domain_state[next_domain_to_resolve].update({
			"server_ip" : dns_server,
			"status" : "STARTED",
			"started" : time.time()
		})
		started_domains.append(next_domain_to_resolve)
		pprint(domain_state[next_domain_to_resolve])

		# Should send DNS packet to resolve next_domain_to_resolve with dns_server
		packet = dns.make_dns_query_packet(next_domain_to_resolve)
		send_nonblocking_packet(packet, dns_server)

	except IndexError:
		print "All domains have been assigned"
		task_was_available = False
	return task_was_available

def all_done():
	states = domain_state.values()
	return all([s['status'] in ['DONE', 'DIDNOTEXIST'] for s in states])

def print_progress():
	"""Print % of domains checked"""
	states = domain_state.values()
	done_count = sum([s['status'] in ['DONE', 'DIDNOTEXIST'] for s in states])
	total_count = len(states)
	percentage = done_count * 100.0 / total_count
	print "%.5f%% of domains checked" % percentage

def print_throughput(throttlers):
	"""Print how fast each name server is"""

	print
	print

	# Print throughput of each server
	print "Current throughput (in domains resolved per second):"
	for dns_ip, throttler in throttlers.items():
		print "%s\t%.2f DPS" % (dns_ip, throttler.current_throughput())

def resolve_all():
	global throttlers
	set_all_domains_to_initial_state()
	throttlers = dict([(ip, TaskThrottler(run_task, ip)) for ip in public_dns_servers])
	while not all_done():
		for ip, throttler in throttlers.items():
			throttler.tick()

			#if throttler.current_throughput() > 
			# no_errors_recently = True
			# if no_errors_recently:
			# 	throttler.faster() # Things seem to be going well, try using this server more

		time.sleep(0.1)

		print_throughput(throttlers)
		print_progress()
		make_stalled_domains_get_retried_later()

		# NONBLOCK means return immediately if no events available
		# EVLOOP_NO_EXIT_ON_EMPTY would mean block indefinitely even if no events available
		base.loop(libevent.EVLOOP_NONBLOCK)

	print
	print
	print "ALL DONE:"

closed_sockets = set()

def event_ready(event, fd, type_of_event, s):
	# if type_of_event & libevent.EV_TIMEOUT:
	# 	print "Timeout"
	# 	exit()

	if type_of_event & libevent.EV_READ:
		if s in closed_sockets:
			print "Trying to read from closed socket!"
			exit()
		response, addr = s.recvfrom(1024)
		server_ip = addr[0]
		print "Received DNS packet from %s!" % server_ip

		# import code
		# code.InteractiveConsole(locals=locals()).interact()
		# response_hexed = " ".join(hex(ord(c)) for c in response)
		print "Parsing response from %s" % server_ip
		did_domain_exist, domain, ip_address = dns.parse_response(response)
		print "Domain did %sexist." % "not " if not did_domain_exist else ""
		print "Domain in question was %s." % domain

		state = domain_state[domain + '.']
		if did_domain_exist:
			state.update({
				'resolved_ip' : ip_address,
				'status' : 'DONE'
			})
		else:
			state.update({
				'status' : 'DIDNOTEXIST'
			})
		started_domains.remove(domain + '.')

		throttlers[server_ip].task_completed()

resolve_all()
for domain, state in domain_state.items():
	if state['status'] == 'DONE':
		print "%s\t%s" % (domain, state['resolved_ip'])
	if state['status'] == 'DIDNOTEXIST':
		print "%s\t%s" % (domain, '-')

print
print
print "STALL STATS:"
pprint(dns_server_timeout_count)