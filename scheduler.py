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
DNS_PORT = 53
RETRY_THRESHOLD = 10 # seconds

base = libevent.Base()

# Use top 1 million domains as test data
print "Reading domain list..."
domain_list = [l.split(",")[1].strip()+"." for l in open('opendns-top-1m.csv')][55:56]
# domain_list = [x for x in domain_list if "govuk" in x]

# domain_list = ['the-epic-outfitter.myshopify.com.']
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

# List of domains that are in STARTED state, for a quicker
# lookup when scanning for stalled domains.
started_domains = []

throttlers = None

# At first nothing is resolved yet.
def set_all_domains_to_initial_state():
	for domain in domain_list:
		domain_state[domain] = {
			"ip" : None,
			"status" : None,
			"started" : None
		}

# Haven't gotten a response? Try again.
def make_stalled_domains_get_retried_later():
	for domain in started_domains:
		# If took too long, reset to initial state, which will 
		# make this domain get retried at a later point.
		elapsed = time.time() - domain_state[domain]['started']
		if elapsed > RETRY_THRESHOLD:
			domain_state[domain] = {
				"ip" : None,
				"status" : None,
				"started" : None
			}
			domain_list.append(domain)

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
	"""Print how fast each domain name server is"""

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
			# print ip, "tick"
			throttler.tick()

			#if throttler.current_throughput() > 
			no_errors_recently = True
			if no_errors_recently:
				throttler.faster() # Things seem to be going well, try using this server more

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

def event_ready(event, fd, type_of_event, s):
	# if type_of_event & libevent.EV_TIMEOUT:
	# 	print "Timeout"
	# 	exit()

	if type_of_event & libevent.EV_READ:
		response, addr = s.recvfrom(1024)
		server_ip = addr[0]
		print "Received DNS packet from %s!" % server_ip

		# import code
		# code.InteractiveConsole(locals=locals()).interact()

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
		started_domains.remove(domain + '.')

		throttlers[server_ip].task_completed()
#		task_completed


resolve_all()
for domain, state in domain_state.items():
	if state['status'] == 'DONE':
		print "%s\t%s" % (domain, state['ip'])
	if state['status'] == 'DIDNOTEXIST':
		print "%s\t%s" % (domain, '-')


