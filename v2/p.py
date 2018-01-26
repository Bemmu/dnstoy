MAX_CONCURRENT = 500
REASK_IN_SECONDS = 30.0

# 16.01.2018: 21 seconds to resolve 50 domains at 50 parallel
# 17.01.2018: 8 seconds
# 18.01.2018: 7 seconds to resolve 500 domains at 500 parallel (71 per second)
# 24.01.2018: 33 seconds to resolve 5000 domains at 5000 parallel (151 per second)
# 25.01.2018: 0.5% of domains could not be resolved, seems acceptable and could do second pass on those

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
import inspect

def exit():
	print "Exiting because asked to: %s" % str(inspect.stack()[1])
	sys.exit()

query_count = collections.defaultdict(int) 

logging.basicConfig(level=logging.INFO)

A_RECORD_RDTYPE = 1
NS_RDTYPE = 2
CNAME_RECORD_RDTYPE = 5
REFUSED_RCODE = 5
NXDOMAIN_RCODE = 3
NO_DATA_ERRNO = 35
DNS_PORT = 53

# If end up asking about the same domain more than this many times, just give up on it.
QUERY_GIVE_UP_THRESHOLD = 16 # 16 needed to resolve pages.tmall.com

TLD_ZONE_SERVER = 'lax.xfr.dns.icann.org' # https://www.dns.icann.org/services/axfr/

resolved_domains = {
	# 'google.com' : '1.2.3.4' 
	# None means NXDOMAIN
}

# For printing status info
last_status_print = time.time()
messages_sent = 0
replies_received_count = 0
bytes_received = 0
retry_count = 0
resolved_count = 0

root_servers = []
def resolve_root_servers():
	for ch in 'abcdefghijklm':
		domain = '%s.root-servers.net' % ch
		ip = socket.gethostbyname(domain)
		root_servers.append(ip)
		resolved_domains[domain] = ip

resolve_root_servers()
print resolved_domains

logging.info("Reading domain list.")
domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')]#[0:1000000]
# domains = ["pages.tmall.com"]
# domains = ['yandex.ru', 'express.co.uk', 'olx.com.eg', 'dailystar.co.uk', 'e1.ru', 'pku.edu.cn', 'fudan.edu.cn', 'www.gov.cn.qingcdn.com']
# domains = ['www.gov.cn.qingcdn.com']
# domains = ['ns0-e.dns.pipex.net']
# domains = ['ads.gold']
# domains = ['oxforddictionaries.com']
# domains = ['google.com']
# domains = ['ahram.org.eg']

tlds = list(set([d.split(".")[-1] for d in domains]))

def random_name_server_by_tld(domain):
	tld = domain.split(".")[-1].lower()
	try:
		name_server = random.choice(tld_nameservers[tld])
	except KeyError:
		name_server = random.choice(root_servers)

	return name_server

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
	logging.info("Resolving each TLD name server sequentially.")
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

def print_results(resolved_domains, domains):
	fn = "resolved_domains.csv"
	logging.info("Writing results to %s" % fn)
	with open(fn, "w") as f:
		for domain in domains:
			f.write("%s, " % domain)

			d = resolved_domains.get(domain, None)
			while d is not None and not is_ip_address(d):
				# f.write("%s -> " % d)
				d = resolved_domains.get(d, None)

			if d is None:
				# f.write("None (NXDOMAIN or no ip)")
				f.write("None")
			else:
				f.write("%s" % d)
			f.write("\n")

# Avoid doing too many zone transfers by caching into a file.
try:
	tld_nameservers = pickle.load(open('zone.pickle', 'r'))
	logging.info("Loaded zone from file.")
	logging.debug(tld_nameservers)
except:
	tld_nameservers = transfer_zone()
	with open('zone.pickle', 'w') as f:
		pickle.dump(tld_nameservers, f)

# Just to make lookups faster, records whether a domain is in domains_that_need_querying or domains_being_queried_newest_last
in_todo_or_ongoing = {}

domains_that_need_querying = [(domain, random_name_server_by_tld(domain)) for domain in domains]
for domain, _ in domains_that_need_querying:
	in_todo_or_ongoing[domain] = True

def add_to_todo(domain, first = True, next_ask = None):
	if domain in in_todo_or_ongoing:
		logging.debug("Domain %s was already being queried" % domain)
		# print domains_that_need_querying
		# print domains_being_queried_newest_last
	else:
		if not next_ask:
			next_ask = random_name_server_by_tld(domain)

		if first:
			domains_that_need_querying.insert(0, (domain, next_ask))
		else:			
			domains_that_need_querying.append((domain, next_ask))

		in_todo_or_ongoing[domain] = True

	# logging.debug("Domains that need querying: %s" % domains_that_need_querying)

# logging.debug("Domains that need querying: %s" % domains_that_need_querying)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setblocking(False)

domains_being_queried_newest_last = [
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


def send_queries():
	logging.debug("send_queries()")
	global messages_sent

	domains_being_queried_count = len(domains_being_queried_newest_last)
	new_queries_added_inside_loop = 0

	while domains_being_queried_count + new_queries_added_inside_loop < MAX_CONCURRENT:
		try:
			# print "Do one (%s)" % len(domains_being_queried_newest_last)
			domain, next_ask = domains_that_need_querying.pop(0)
			try:
				del in_todo_or_ongoing[domain]
			except KeyError, e: # Not sure how this can happen, but it does.
				# This is normal, because some packet thought to be expired might have responded later and contained
				# the answer, clearing the dict entry.
				pass

				# logging.warning("Tried to remove %s from in_todo_or_ongoing, but it wasn't there!?" % domain)
				# exit()

			if domain in resolved_domains:
				logging.debug("Almost asked about %s despite knowing answer %s already" % (domain, resolved_domains[domain]))
				continue

			# logging.debug("Domains that need querying: %s" % domains_that_need_querying)
			if next_ask is None:
				print "Popped a None!"
				exit()

			logging.debug("Doing %s next, need to ask %s" % (domain, next_ask))
			if not is_ip_address(next_ask):
				logging.debug("Not an ip address: %s" % next_ask)

				# Translate name to IP address if we know it already.
				try:
					try:
						ip = resolved_domains[next_ask]
					except TypeError, e:
						print "Next ask is", next_ask
						print "%s" % e
						exit()
					logging.debug("Knew that %s is %s, asking there for %s later." % (next_ask, ip, domain))
					next_ask = ip

					# If there is nowhere to ask, then give up on this as well.
					if next_ask is None:
						resolved_domains[domain] = None

				except KeyError:
					logging.debug("Didn't know the ip address for %s yet, try again later." % next_ask)

				if next_ask:
					if "root-servers.net" in domain:
						print "Foo1"
						exit()

					add_to_todo(domain, first = False)

					# logging.debug("Domains that need querying: %s" % domains_that_need_querying)
					logging.debug("Need to ask about %s to %s" % domains_that_need_querying[-1])

				continue

			query_count[domain] += 1
			if query_count[domain] <= QUERY_GIVE_UP_THRESHOLD:
				if "ns8-l2.nic.ru" in domain:
					print "Sending packet about %s to %s" % (domain, next_ask)
				send_async_dns_query(domain, next_ask)
				messages_sent += 1
				domains_being_queried_newest_last.append((domain, time.time()))
				new_queries_added_inside_loop += 1
				in_todo_or_ongoing[domain] = True
			else:
				logging.warning("Asked about %s too many times (%s), giving up." % (domain, query_count[domain]))
				logging.warning("Would have asked %s" % next_ask)
				resolved_domains[domain] = None

		except IndexError:
			if len(domains_being_queried_newest_last) == 0:
				print_results(resolved_domains, domains)
				exit()
			else:
				logging.debug("No domains to query, but some are still ongoing so waiting for those.")
				time.sleep(0.5)

	logging.info("%s new queries" % new_queries_added_inside_loop)

def oldest_elapsed():
	domain, query_timestamp = domains_being_queried_newest_last[0]
	return time.time() - query_timestamp

def newest_elapsed():
	domain, query_timestamp = domains_being_queried_newest_last[-1]
	return time.time() - query_timestamp

def retry_queries():
	global retry_count
	logging.debug("retry_queries()")

	# Retry queries after some time
	if domains_being_queried_newest_last:
		while domains_being_queried_newest_last and oldest_elapsed() > REASK_IN_SECONDS:
			retry_count += 1
			domain, timestamp = domains_being_queried_newest_last.pop(0)
			try:
				del in_todo_or_ongoing[domain]
			except KeyError, e:
				logging.warning("Tried to delete %s from lookup dict, but it wasn't there." % domain)

			if "root-servers.net" in domain:
				print "Foo2"
				exit()

			add_to_todo(domain, first = True)
			logging.debug("Answer for %s took too long, asking again starting from root." % domain)

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

	logging.debug("Received packet from %s" % addr[0])
	try:
		bytes_received += len(data)
		response = parse(data)
		# log_response(response)
	except (dns.message.TrailingJunk, dns.exception.FormError): # trailing junk / malformed message
		logging.warning("Failed to parse response to %s from %s. Trying again starting from random root." % (domain, addr[0]))
		if "root-servers.net" in domain:
			print "Foo3"
			exit()

		add_to_todo(domain, first = True)
		return None, addr

	return response, addr

def handle_refused_rcode(domain):
	# Name server didn't play nice, so try again from random root.
	logging.debug("Refused. Resolving %s again from root." % domain)
	if "root-servers.net" in domain:
		print "Foo4"
		exit()

	add_to_todo(domain, first = True)

def handle_nxdomain(domain):
	logging.debug("%s did not exist (NXDOMAIN)" % domain)
	resolved_domains[domain] = None

def handle_answer(response, domain):
	global domains_that_need_querying, resolved_count

	for answer in response.answer:
		if answer.rdtype == CNAME_RECORD_RDTYPE:
			cname = str(answer[0])[:-1].lower()
			logging.debug("Got CNAME for %s: %s" % (domain, cname))
			resolved_domains[domain] = cname

			# Now need to resolve the CNAME as well
			if not cname in resolved_domains:			
				if "root-servers.net" in cname:
					print "Foo5"
					exit()

				add_to_todo(cname, first = True)

			# If you encounter detail.tmall.com with CNAME detail.tmall.com.danuoyi.tbcache.com then
			# you are supposed to connect to the IP of detail.tmall.com.danuoyi.tbcache.com BUT still
			# say Host: detail.tmall.com
		elif answer.rdtype == A_RECORD_RDTYPE:
			answer_name = str(answer.name)[:-1].lower()
			answer_ip = str(answer[0])
			resolved_domains[answer_name] = answer_ip
			resolved_count += 1
			logging.debug("The answer is %s: %s" % (answer_name, answer_ip))
			# print resolved_domains

			# Make sure not to ask about this again if we have it queued.
			before = len(domains_that_need_querying)
			domains_that_need_querying = [(d, n) for d,n in domains_that_need_querying if d != answer_name]
			try:
				del in_todo_or_ongoing[answer_name]
			except KeyError:
				pass # not necessarily there
			# logging.debug("Domains that need querying: %s" % domains_that_need_querying)
			after = len(domains_that_need_querying)
			if before != after:
				logging.debug("Removed %s from todo list." % answer_name)

		else:
			logging.warning("Ignoring answer rdtype for %s was not A but %s in:\n%s" % (domain, answer.rdtype, response.to_text()))

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

		is_ip_known = server[:-1] in resolved_domains
		seconds_elapsed_since_last_picked = get_seconds_elapsed_since_last_picked(server)

		priority = seconds_elapsed_since_last_picked + is_ip_known
		priorities_for_servers.append((priority, server))

	return priorities_for_servers

def get_authority_names(response):
	# Authority section has the name servers to ask next.
	authority_names = [str(auth).lower() for auth in response.authority[0] if auth.rdtype == NS_RDTYPE]

	# Remove ones that didn't resolve.
	authority_names = [a for a in authority_names if not (a[:-1] in resolved_domains and resolved_domains[a[:-1]] is None)]

	return authority_names

def set_last_pick_timestamp(authority_name):
	last_pick_timestamps[authority_name] = time.time()

def choose_authority(authority_names):
	priorities_for_servers = prioritize_servers(authority_names)

	# No options? I guess we failed.
	if not priorities_for_servers:
		logging.warning("No options for %s" % domain)
		return

	# logging.debug("Priorities: %s" % sorted(priorities_for_servers, reverse = True))
	authority_name = sorted(priorities_for_servers, reverse = True)[0][1]
	authority_name = authority_name[:-1].lower()
	# logging.debug("Picked %s" % authority_name)
	return authority_name

def ask_forward(authority_name, domain):
	# If this IP was not in additional, then need to resolve it first.
	# logging.debug("%s known?" % authority_name)

	try:
		next_ask = resolved_domains[authority_name]
		# logging.debug("Yes. Knew %s has ip %s." % (authority_name, next_ask))

		if not next_ask:
			print "Was going to put None to next_ask part 1 because authority %s of domain %s was resolved to None!" % (authority_name, domain)
			exit()
	except KeyError:
		# logging.debug("No. Resolving %s first." % authority_name)
		if "root-servers.net" in authority_name:
			print authority_name
			print "Foo6"
			exit()

		add_to_todo(authority_name, first = True)
		next_ask = authority_name

		if not next_ask:
			print "Was going to put None to next_ask part 2!"
			exit()

	if "root-servers.net" in domain:
		print "Foo7"
		exit()

	add_to_todo(domain, first = False, next_ask = next_ask)

	# domains_that_need_querying.append((domain, next_ask))
	# logging.debug("Domains that need querying: %s" % domains_that_need_querying)
	# logging.debug("Will try to resolve %s by asking %s" % domains_that_need_querying[-1])
	# print domains_that_need_querying

def handle_authority(response, domain):
	# logging.debug("Handling auth section for %s" % domain)

	authority_names = get_authority_names(response)
	if not authority_names:

		# Looks like this doesn't have an IP, for example googleusercontent.com
		resolved_domains[domain] = None
		return

	authority_name = choose_authority(authority_names)
	if authority_name:
		set_last_pick_timestamp(authority_name)
		ask_forward(authority_name, domain)

def handle_response(response, domain):
	global domains_that_need_querying

	# This makes this resolver gullible. Believe any IP given by any response, even if not in their authority.
	for a in response.additional:
		if a.rdtype == A_RECORD_RDTYPE:
			# logging.debug("Recording %s as %s" % (str(a.name)[:-1], str(a[0])))
			resolved_domains[str(a.name)[:-1]] = str(a[0])

	if response is None:
		if "root-servers.net" in domain:
			print "Foo8"
			exit()
		# domains_that_need_querying.insert(0, (domain, random_name_server_by_tld(domain)))

		add_to_todo(domain, first = True)

		# logging.debug("Domains that need querying: %s" % domains_that_need_querying)

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
		if "root-servers.net" in domain:
			print "Foo9"
			exit()
		# domains_that_need_querying.append((domain, random_name_server_by_tld(domain)))

		add_to_todo(domain, first = False)

		# logging.debug("Domains that need querying: %s" % domains_that_need_querying)


def remove_from_domains_being_queried(domain):
	global domains_being_queried_newest_last
	domains_being_queried_newest_last = [x for x in domains_being_queried_newest_last if x[0] != domain]
	try:
		del in_todo_or_ongoing[domain]
	except:
		pass

def read_all_from_socket():

	logging.debug("read_all_from_socket()")

	global domains_being_queried_newest_last
	global replies_received_count

	# Loop until nothing more to read from socket.
	while True:
		try:
			response, addr = receive_next_dns_reply()
			if not response: # parsing failed, already caused a retry later
				continue

			if len(response.question) == 0:
				logging.warning("Ignoring packet from %s because it did not contain a question section: %s" % (addr[0], response.to_text()))
				continue

			if len(response.question[0].name) == 0:
				logging.warning("Ignoring packet from %s because it had zero-sized name section: %s" % (addr[0], response.to_text()))
				continue

			domain = str(response.question[0].name)[:-1]
			remove_from_domains_being_queried(domain)

			replies_received_count += 1

			# It's possible that when receiving this packet, we had already learned the answer from another one.
			if domain in resolved_domains:
				logging.debug("%s was already known, skipping packet from %s" % (domain, addr[0]))
				continue

			handle_response(response, domain)

		except socket.error, e:
			if e.errno == NO_DATA_ERRNO:
				# print "No data"
				break
			else:
				logging.warning("Some other error (%s) on socket" % e.errno)

def print_status():
	global last_status_print
	elapsed_since_last_status_print = time.time() - last_status_print
	if elapsed_since_last_status_print > 1.0:
		status = "%s resolved, %s ongoing, %s retry, %s to do, %s sent, %s responses / %s kB"
		fields = (resolved_count, ongoing_count, retry_count, todo_count, messages_sent, replies_received_count, bytes_received/1024)
		if domains_being_queried_newest_last:
			status += ", oldest %.2fs, newest %.2fs"
			fields += (oldest_elapsed(), newest_elapsed()) 
		logging.info(status % fields)

		last_status_print = time.time()

		if ongoing_count < 10:
			logging.info('ongoing: %s' % [x[0] for x in domains_being_queried_newest_last])
		if todo_count < 10:
			logging.info('todo: %s' % [x for x in domains_that_need_querying])	

while True:
	ongoing_count = len(domains_being_queried_newest_last)
	todo_count = len(domains_that_need_querying)

	print_status()
	# time.sleep(0.4)

	sys.stdout.flush()

	logging.debug("Checking for multiples")
	if len(set(domains_that_need_querying)) != len(domains_that_need_querying):
		logging.warning("Some domain appeared multiple times!")
		exit()
	logging.debug("Done check")

	retry_queries()
	send_queries()
	# exit()
	read_all_from_socket()
