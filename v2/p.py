# 16.01.2018: 21 seconds to resolve 50 domains at 50 parallel
# 17.01.2018: 8 seconds
# 18.01.2018: 7 seconds to resolve 500 domains at 500 parallel

import random
import time
import socket
import dns
import dns.message
import dns.query
import dns.zone
import sys
import pickle
import logging
import collections

query_count = collections.defaultdict(int) 

logging.basicConfig(level=logging.INFO)

NO_DATA_ERRNO = 35
DNS_PORT = 53
MAX_CONCURRENT = 1000
REASK_IN_SECONDS = 20.0

A_RECORD_RDTYPE = 1
NS_RDTYPE = 2
CNAME_RECORD_RDTYPE = 5

REFUSED_RCODE = 5
NXDOMAIN_RCODE = 3

# If end up asking about the same domain more than this many times, just give up on it.
QUERY_GIVE_UP_THRESHOLD = 16 # 16 needed to resolve pages.tmall.com

TLD_ZONE_SERVER = 'lax.xfr.dns.icann.org' # https://www.dns.icann.org/services/axfr/

root_servers = [socket.gethostbyname('%s.root-servers.net' % ch) for ch in 'abcdefghijkl']	

logging.info("Reading domain list.")
domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')][0:5000]
# domains = ["pages.tmall.com"]
# domains = ['yandex.ru', 'express.co.uk', 'olx.com.eg', 'dailystar.co.uk', 'e1.ru', 'pku.edu.cn', 'fudan.edu.cn', 'www.gov.cn.qingcdn.com']
# domains = ['www.gov.cn.qingcdn.com']
# domains = ['ns0-e.dns.pipex.net']
# domains = ['ads.gold']

tlds = list(set([d.split(".")[-1] for d in domains]))

# Start by transferring zone describing TLDs
def transfer_zone():
	# https://www.dns.icann.org/services/axfr/
	logging.debug("Resolving %s" % TLD_ZONE_SERVER)
	tld_zone_server = socket.gethostbyname(TLD_ZONE_SERVER)

	tld_nameservers = {}
	logging.info("Transferring zone.")
	z = dns.zone.from_xfr(dns.query.xfr(tld_zone_server, ''))
	names = z.nodes.keys()
	names.sort()
	for i, n in enumerate(names):
		tld = str(n)
		if tld not in tlds: continue # Skip TLDs we aren't interested in

		name_server_hosts = map(str, z[n].get_rdataset(1, NS_RDTYPE))
		logging.debug("Name servers for %s are %s" % (tld, ", ".join(name_server_hosts[:-1]) + " and " + name_server_hosts[-1]))
		logging.debug("Resolving name servers for %s" % n)

		name_servers = []
		for host in name_server_hosts:
			try:
				name_servers.append(socket.gethostbyname(host))
			except socket.gaierror:
				pass # Occasionally can't resolve all, but that's OK as long as we have some servers for this.

		# If we didn't have any for this TLD, start with root instead.
		if not name_servers:
			name_servers = [random.choice(root_servers)]

		tld_nameservers[tld] = name_servers
	return tld_nameservers

def print_results(domains_for_which_response_received, domains):
	print
	for domain in domains:
		sys.stdout.write("%s\t" % domain)

		d = domains_for_which_response_received[domain]
		while d is not None and not is_ip_address(d):
			sys.stdout.write("%s -> " % d)
			d = domains_for_which_response_received[d]

		if d is None:
			sys.stdout.write("None (NXDOMAIN or no ip)")
		else:
			sys.stdout.write("%s" % d)
		print


# Avoid doing too many zone transfers by caching into a file.
try:
	tld_nameservers = pickle.load(open('zone.pickle', 'r'))
	logging.info("Loaded zone from file.")
	logging.debug(tld_nameservers)
except:
	tld_nameservers = transfer_zone()
	with open('zone.pickle', 'w') as f:
		pickle.dump(tld_nameservers, f)

domains_that_need_querying = [(domain, random.choice(tld_nameservers[domain.split(".")[-1]])) for domain in domains]
logging.debug("Domains that need querying: %s" % domains_that_need_querying)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setblocking(False)

domains_for_which_response_received = {
	# 'google.com' : '1.2.3.4' 
	# None means NXDOMAIN
}

domains_being_queried_latest_last = [
	# ('google.com', 5), ('example.com', 100)...
]

# Records timestamps for when a name server was selected for querying, to avoid using same ones too much.
last_pick_timestamps = {}

def send_async_dns_query(domain, name_server_ip_address):
	data = dns.message.make_query(domain, 'A').to_wire()
	dest = (name_server_ip_address, DNS_PORT)
	s.sendto(data, dest)
	logging.debug("Sent packet asking about %s to %s" % (domain, name_server_ip_address))

def is_ip_address(str):
	return all([ch in "0123456789." for ch in str])

last_status_print = time.time()
messages_sent = 0
replies_received_count = 0
bytes_received = 0

def send_queries():
	logging.debug("send_queries()")
	global messages_sent

	while len(domains_being_queried_latest_last) < MAX_CONCURRENT:
		if not domains_that_need_querying and domains_being_queried_latest_last:
			logging.debug("Nothing to do but wait now")
			time.sleep(0.5)
			return

		try:
			# print "Do one (%s)" % len(domains_being_queried_latest_last)
			domain, next_ask = domains_that_need_querying.pop(0)
			logging.debug("Domains that need querying: %s" % domains_that_need_querying)
			if next_ask is None:
				print "Popped a None!"
				exit()

			logging.debug("Doing %s next, need to ask %s" % (domain, next_ask))
			if not is_ip_address(next_ask):
				logging.debug("Not an ip address: %s" % next_ask)

				# Translate name to IP address if we know it already.
				try:
					ip = domains_for_which_response_received[next_ask]
					logging.debug("Knew that %s is %s, asking there for %s later." % (next_ask, ip, domain))
					next_ask = ip

					# If there is nowhere to ask, then give up on this as well.
					if next_ask is None:
						domains_for_which_response_received[domain] = None

				except KeyError:
					logging.debug("Didn't know the ip address for %s yet, try again later." % next_ask)

				if next_ask:
					domains_that_need_querying.append((domain, next_ask))					
					logging.debug("Domains that need querying: %s" % domains_that_need_querying)
					logging.debug("Need to ask about %s to %s" % domains_that_need_querying[-1])
				return

			query_count[domain] += 1
			if query_count[domain] <= QUERY_GIVE_UP_THRESHOLD:
				send_async_dns_query(domain, next_ask)
				messages_sent += 1
				domains_being_queried_latest_last.append((domain, time.time()))
			else:
				logging.warning("Asked about %s too many times (%s), giving up." % (domain, query_count[domain]))
				domains_for_which_response_received[domain] = None

		except IndexError:
			if len(domains_being_queried_latest_last) == 0:
				print_results(domains_for_which_response_received, domains)
				exit()
	else:
		pass

def retry_queries():
	logging.debug("retry_queries()")

	# Retry queries after some time
	if domains_being_queried_latest_last:
		while True:
			domain, query_timestamp = domains_being_queried_latest_last[0]
			oldest_elapsed = time.time() - query_timestamp
			if oldest_elapsed > REASK_IN_SECONDS:
				domains_being_queried_latest_last.pop(0)
				domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))
				logging.debug("Domains that need querying: %s" % domains_that_need_querying)
				logging.debug("Answer for %s took too long, asking again starting from root." % domain)
				break
			else:
				logging.debug("Nothing expired (oldest %.2f seconds old)" % oldest_elapsed)
				break

def recvfrom():
	return s.recvfrom(1024)

def parse(data):
	response = dns.message.from_wire(data)				
	return response

def log_response(response):
	logging.debug(response.to_text())

def receive_next_dns_reply():
	global bytes_received

	data, addr = recvfrom()

	# logging.debug("Received packet from %s" % addr[0])
	try:
		bytes_received += len(data)
		response = parse(data)
		log_response(response)
	except dns.message.TrailingJunk:
		logging.warning("Failed to parse response to %s from %s. Trying again starting from random root." % (domain, addr[0]))
		domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))
		logging.debug("Domains that need querying: %s" % domains_that_need_querying)

	return response, addr

def handle_refused_rcode(domain):
	# Name server didn't play nice, so try again from random root.
	logging.debug("Refused. Resolving %s again from root." % domain)
	domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))
	logging.debug("Domains that need querying: %s" % domains_that_need_querying)

def handle_nxdomain(domain):
	logging.debug("%s did not exist (NXDOMAIN)" % domain)
	domains_for_which_response_received[domain] = None

def handle_answer(response, domain):
	global domains_that_need_querying

	if response.answer[0].rdtype == CNAME_RECORD_RDTYPE:
		cname = str(response.answer[0][0])[:-1]
		logging.debug("Got CNAME for %s: %s" % (domain, cname))
		domains_for_which_response_received[domain] = cname

		# Now need to resolve the CNAME as well
		if not cname in domains_for_which_response_received:
			if addr[0] is None:
				print "addr[0] was None!"
				exit()
			domains_that_need_querying.insert(0, (cname, addr[0]))
			logging.debug("Domains that need querying: %s" % domains_that_need_querying)

		# If you encounter detail.tmall.com with CNAME detail.tmall.com.danuoyi.tbcache.com then
		# you are supposed to connect to the IP of detail.tmall.com.danuoyi.tbcache.com BUT still
		# say Host: detail.tmall.com
	elif response.answer[0].rdtype == A_RECORD_RDTYPE:
		answer_name = str(response.answer[0].name)[:-1].lower()
		answer_ip = str(response.answer[0][0])
		domains_for_which_response_received[answer_name] = answer_ip
		logging.debug("The answer is %s: %s" % (answer_name, answer_ip))

		# Make sure not to ask about this again if we have it queued.
		before = len(domains_that_need_querying)
		domains_that_need_querying = [(d, n) for d,n in domains_that_need_querying if d != answer_name]
		logging.debug("Domains that need querying: %s" % domains_that_need_querying)
		after = len(domains_that_need_querying)
		if before != after:
			logging.debug("Removed %s from todo list." % answer_name)

	else:
		logging.debug("Answer rdtype for %s was not A but %s" % (domain, response.answer[0].rdtype))
		exit()

def get_seconds_elapsed_since_last_picked(server):
	try:
		seconds_elapsed_since_last_picked = time.time() - last_pick_timestamps[server[:-1]]
	except KeyError:
		seconds_elapsed_since_last_picked = 10**9
	return seconds_elapsed_since_last_picked

def prioritize_servers(authority_names):
	# Prioritize name servers as follows:
	#
	# 1. Most importantly pick one we haven't asked from recently.
	# 2. Multiple choices among those we haven't asked recently? Pick one we know IP for.
	priorities_for_servers = []
	for server in authority_names:
		if server.lower()[:-1] == domain.lower():
			logging.debug("Prevented asking name server %s for itself." % server)
			return

		is_ip_known = server[:-1] in domains_for_which_response_received
		seconds_elapsed_since_last_picked = get_seconds_elapsed_since_last_picked(server)

		priority = seconds_elapsed_since_last_picked + is_ip_known
		priorities_for_servers.append((priority, server))

	return priorities_for_servers

def handle_authority(response, domain):
	logging.debug("Handling auth section for %s" % domain)

	# Authority section has the name servers to ask next.
	authority_names = [str(auth) for auth in response.authority[0] if auth.rdtype == NS_RDTYPE]

	if not authority_names:

		# Looks like this doesn't have an IP, for example googleusercontent.com
		domains_for_which_response_received[domain] = None
		return

	# Additional section sometimes provides IP addresses for some of those servers for convenience.
	for a in response.additional:
		if a.rdtype == A_RECORD_RDTYPE:
			logging.debug("Recording %s as %s" % (str(a.name)[:-1], str(a[0])))
			domains_for_which_response_received[str(a.name)[:-1]] = str(a[0])

	priorities_for_servers = prioritize_servers(authority_names)

	# No options? I guess we failed.
	if not priorities_for_servers:
		logging.warning("No options for %s" % domain)
		return

	logging.debug("Priorities: %s" % sorted(priorities_for_servers, reverse = True))
	authority_name = sorted(priorities_for_servers, reverse = True)[0][1]
	authority_name = authority_name[:-1].lower()
	logging.debug("Picked %s" % authority_name)
	last_pick_timestamps[authority_name] = time.time()

	# If this IP was not in additional, then need to resolve it first.
	logging.debug("%s known?" % authority_name)

	try:
		next_ask = domains_for_which_response_received[authority_name]
		logging.debug("Yes. Knew %s has ip %s." % (authority_name, next_ask))
	except KeyError:
		logging.debug("No. Resolving %s first." % authority_name)
		domains_that_need_querying.insert(0, (authority_name, random.choice(root_servers)))
		logging.debug("Domains that need querying: %s" % domains_that_need_querying)
		next_ask = authority_name

	if not next_ask:
		print "Was going to put None to next_ask!"
		exit()

	domains_that_need_querying.append((domain, next_ask))
	logging.debug("Domains that need querying: %s" % domains_that_need_querying)
	logging.debug("Will try to resolve %s by asking %s" % domains_that_need_querying[-1])
	# print domains_that_need_querying


def handle_response(response, domain):
	global domains_that_need_querying

	if response is None:
		domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))
		logging.debug("Domains that need querying: %s" % domains_that_need_querying)

	elif response.rcode() == REFUSED_RCODE:
		handle_refused_rcode(domain)
	elif response.rcode() == NXDOMAIN_RCODE:
		handle_nxdomain(domain)
	elif response.answer:
		handle_answer(response, domain)
	elif response.authority: # Need to ask forward
		handle_authority(response, domain)
	else:
		# No authority and no answer, try again from root. This happened once when
		# asked ns-646.awsdns-16.net (205.251.194.134) about soundcloud.com:
		#
		# Received packet from 205.251.194.134
		# id 4378
		# opcode QUERY
		# rcode NOERROR
		# flags QR AA TC RD
		# ;QUESTION
		# soundcloud.com. IN A
		# ;ANSWER
		# ;AUTHORITY
		# ;ADDITIONAL
		domains_that_need_querying.append((domain, random.choice(root_servers)))
		logging.debug("Domains that need querying: %s" % domains_that_need_querying)


def read_all_from_socket():

	logging.debug("read_all_from_socket()")

	global domains_being_queried_latest_last
	global replies_received_count

	# Loop until nothing more to read from socket.
	while True:
		try:
			response, addr = receive_next_dns_reply()

			domain = str(response.question[0].name)[:-1]
			domains_being_queried_latest_last = [x for x in domains_being_queried_latest_last if x[0] != domain]
			replies_received_count += 1

			# It's possible that when receiving this packet, we had already learned the answer from another one.
			if domain in domains_for_which_response_received:
				logging.debug("%s was already known, skipping packet from %s" % (domain, addr[0]))
				continue

			handle_response(response, domain)

		except socket.error, e:
			if e.errno == NO_DATA_ERRNO:
				# print "No data"
				break
			else:
				logging.warning("Some other error (%s) on socket" % e.errno)

while True:
	ongoing_count = len(domains_being_queried_latest_last)
	todo_count = len(domains_that_need_querying)

	elapsed_since_last_status_print = time.time() - last_status_print
	if elapsed_since_last_status_print > 1.0:
		logging.info("%s queries ongoing, %s to do, %s sent, %s responses / %s kB" % (ongoing_count, todo_count, messages_sent, replies_received_count, bytes_received/1024))
		last_status_print = time.time()

	# if ongoing_count < 80:
	# 	logging.info('ongoing: %s' % [x[0] for x in domains_being_queried_latest_last])
	# if todo_count < 80:
	# 	logging.info('todo: %s' % [x for x in domains_that_need_querying])

	# time.sleep(0.4)

	sys.stdout.flush()

	retry_queries()
	send_queries()
	# exit()
	read_all_from_socket()
