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

logging.basicConfig(level=logging.DEBUG)

NO_DATA_ERRNO = 35
DNS_PORT = 53
MAX_CONCURRENT = 1
REASK_IN_SECONDS = 5.0

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
# domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')][0:5000]
# domains = ["pages.tmall.com"]
# domains = ['yandex.ru', 'express.co.uk', 'olx.com.eg', 'dailystar.co.uk', 'e1.ru', 'pku.edu.cn', 'fudan.edu.cn', 'www.gov.cn.qingcdn.com']
domains = ['olx.com.eg']
# domains = ['ns0-e.dns.pipex.net']

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
	logging.info("All done!")

	for domain in domains:
		sys.stdout.write("\t%s\t" % domain)

		d = domains_for_which_response_received[domain]
		while d is not None and not is_ip_address(d):
			sys.stdout.write("%s -> " % d)
			d = domains_for_which_response_received[d]

		if d is None:
			sys.stdout.write("None (NXDOMAIN or no ip)")
		else:
			sys.stdout.write("%s" % d)
		print

# domains = []
# domains = ['detail.tmall.com'] # CNAME example
# domains = ['detail.tmall.com', 'thistotally1234doesnexist.com']
# domains = ['asdfg.pro']

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

# domains_that_need_querying = [('ns1-d.dns.pipex.net', 'ns0-d.dns.pipex.net'), ('ns0-e.dns.pipex.net', 'ns1-d.dns.pipex.net')]

# domains_that_need_querying = [('express.co.uk', 'ns0-e.dns.pipex.net')]
# domains = ['lacloop.info']
# domains_that_need_querying = [('lacloop.info', '88.208.5.2')]

# If I query about "fr", the result cannot be an IP because there is no IP address for "fr" because
# it's a zone.

# Query TLDs first, then use their name servers for the rest of questions to spread work easily.
# tlds = ["fr"]
# domains_that_need_querying = [(tld, random.choice(tld_nameservers[tld])) for tld in tlds]

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

while True:
	ongoing_count = len(domains_being_queried_latest_last)
	todo_count = len(domains_that_need_querying)
	logging.info("%s queries ongoing, %s to do" % (ongoing_count, todo_count))

	if ongoing_count < 80:
		logging.info('ongoing: %s' % [x[0] for x in domains_being_queried_latest_last])
	if todo_count < 80:
		logging.info('todo: %s' % [x for x in domains_that_need_querying])

	time.sleep(0.4)

	if ongoing_count > 0 and todo_count == 0:
		logging.debug("Sleeping a bit since just waiting for replies...")
		time.sleep(0.5)

	# sys.stdout.write(".")
	sys.stdout.flush()

	# Retry queries after some time
	if domains_being_queried_latest_last:
		while True:
			domain, query_timestamp = domains_being_queried_latest_last[0]
			oldest_elapsed = time.time() - query_timestamp
			if oldest_elapsed > REASK_IN_SECONDS:
				domains_being_queried_latest_last.pop(0)
				domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))
				logging.debug("Answer for %s took too long, asking again starting from root." % domain)
				break
			else:
				logging.debug("Nothing expired (oldest %.2f seconds old)" % oldest_elapsed)
				break

	if len(domains_being_queried_latest_last) < MAX_CONCURRENT:
		try:
			domain, next_ask = domains_that_need_querying.pop(0)
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
				continue

			query_count[domain] += 1
			if query_count[domain] <= QUERY_GIVE_UP_THRESHOLD:
				send_async_dns_query(domain, next_ask)
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

	# Loop until nothing more to read from socket.
	while True:
		try:
			data, addr = s.recvfrom(1024)
			logging.debug("Received packet from %s" % addr[0])
			try:
				response = dns.message.from_wire(data)
				logging.debug(response.to_text())
				domain = str(response.question[0].name)[:-1]
				domains_being_queried_latest_last = [x for x in domains_being_queried_latest_last if x[0] != domain]
			except dns.message.TrailingJunk:
				logging.debug("Failed to parse it. Trying again starting from random root.")

			# It's possible that when receiving this packet, we had already learned the answer from another one.
			if domain in domains_for_which_response_received:
				logging.debug("%s was already known, skipping packet from %s" % (domain, addr[0]))
				continue

			if response is None:
				domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))

			elif response.rcode() == REFUSED_RCODE:
				# Name server didn't play nice, so try again from random root.
				logging.debug("Refused. Resolving %s again from root." % domain)
				domains_that_need_querying.insert(0, (domain, random.choice(root_servers)))

			elif response.rcode() == NXDOMAIN_RCODE:
				logging.debug("%s did not exist (NXDOMAIN)" % domain)
				domains_for_which_response_received[domain] = None

			elif response.answer:
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

					# If I were the one doing the resolving... and got a cname. How would I want the answer
					# shown? What am I going to do with the answer? You're going to send a HTTP GET. So you 
					# need to know the Host: right? You can't just replace the IP, you need the name too.
					#
					# No actually...
					# If you encounter detail.tmall.com with CNAME detail.tmall.com.danuoyi.tbcache.com then
					# you are supposed to connect to the IP of detail.tmall.com.danuoyi.tbcache.com BUT still
					# say Host: detail.tmall.com
					#
					# So I don't need to record that it was a CNAME, IP should be enough.

					# exit()
				elif response.answer[0].rdtype == A_RECORD_RDTYPE:
					answer_name = str(response.answer[0].name)[:-1].lower()
					answer_ip = str(response.answer[0][0])
					domains_for_which_response_received[answer_name] = answer_ip
					logging.debug("The answer is %s: %s" % (answer_name, answer_ip))

					# Make sure not to ask about this again if we have it queued.
					before = len(domains_that_need_querying)
					domains_that_need_querying = [(d, n) for d,n in domains_that_need_querying if d != answer_name]
					after = len(domains_that_need_querying)
					if before != after:
						logging.debug("Removed %s from todo list." % answer_name)

				else:
					logging.debug("Answer rdtype for %s was not A but %s" % (domain, response.answer[0].rdtype))
					exit()

			elif response.authority: # Need to ask forward

				# Looks like authority sections don't always give IP addresses for all authority servers.
				# So now there is a dependency, need to resolve some name of server in auth section to continue.

				# for a in response.authority:
				# 	try:
				# 		ns = str(a[0].mname)[:-1]
				# 		print "Resolving %s by gethostbyname" % ns
				# 		ip = socket.gethostbyname(ns)
				# 		print "Authoritative name server for TLD %s is %s (%s)" % (domain, ns, ip)
				# 	except Exception, e:
				# 		print e
				# 		pass

					# print dir(a)
					# print dir(a[0])
					# print a.rdtype
					# print str(a)
					# print str(a[0])

				# Authority section has the name servers to ask next.
				# print "\n\t".join([str(a.rdtype) for a in response.authority[0]])
				authority_names = [str(auth) for auth in response.authority[0] if auth.rdtype == NS_RDTYPE]
				# print authority_names
				# exit()

				if not authority_names:

					# Looks like this doesn't have an IP, for example googleusercontent.com
					domains_for_which_response_received[domain] = None

					# print "This is the end."
					continue

				# Additional section sometimes provides IP addresses for some of those servers for convenience.
				for a in response.additional:
					if a.rdtype == A_RECORD_RDTYPE:
						logging.debug("Recording %s as %s" % (str(a.name)[:-1], str(a[0])))
						domains_for_which_response_received[str(a.name)[:-1]] = str(a[0])

				# There might now be a number of name servers that could be asked next. To make things faster,
				# prefer one for which IP address is already known.
# 				known_ones = [auth[:-1] for auth in authority_names if auth[:-1] in domains_for_which_response_received]
# 				if known_ones:
# 					options = known_ones
# #					authority_name = random.choice(known_ones)
# 					logging.debug("Picked random known authority: %s" % authority_name)
# 				else:
# #					authority_name = random.choice(authority_names)[:-1]
# 					options = authority_names
# 					logging.debug("Didn't know any of them, so picked random authority: %s" % authority_name)
			
				# Prioritize name servers as follows. 
				#
				# Most importantly pick one we haven't asked from recently.
				# If there are multiple choices among those we haven't asked recently, then pick one we know IP for.
				#
				# Prefer a name server we haven't asked recently.

				priorities_for_servers = []
				for server in authority_names:
					if server.lower()[:-1] == domain.lower():
						logging.debug("Prevented asking name server %s for itself." % server)
						continue

					is_ip_known = server[:-1] in domains_for_which_response_received

					try:
						print "Checking %s for %s" % (last_pick_timestamps, server[:-1])
						seconds_elapsed_since_last_picked = time.time() - last_pick_timestamps[server[:-1]]
					except KeyError:
						seconds_elapsed_since_last_picked = 10**9

					priority = seconds_elapsed_since_last_picked + is_ip_known
					priorities_for_servers.append((priority, server))

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
					next_ask = authority_name

				if not next_ask:
					print "Was going to put None to next_ask!"
					exit()

				domains_that_need_querying.append((domain, next_ask))
				logging.debug("Will try to resolve %s by asking %s" % domains_that_need_querying[-1])
				# print domains_that_need_querying

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

		except socket.error, e:
			if e.errno == NO_DATA_ERRNO:
				break
			else:
				logging.warning("Some other error (%s) on socket" % e.errno)
