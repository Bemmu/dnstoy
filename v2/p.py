# 21 seconds to resolve 50 domains at 50 parallel

import random
import time
import socket
import dns
import dns.message
import sys

NO_DATA_ERRNO = 35
DNS_PORT = 53
MAX_CONCURRENT = 1
A_RECORD_RDTYPE = 1
CNAME_RECORD_RDTYPE = 5
REASK_IN_SECONDS = 5

# Initially ask about each domain from a random root server.
root_servers = [socket.gethostbyname('%s.root-servers.net' % ch) for ch in 'abcdefghijkl']	
# domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')][0:125]
domains = ['detail.tmall.com']
domains_that_need_querying = [(domain, random.choice(root_servers)) for domain in domains]

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setblocking(False)

domains_for_which_response_received = {
	# 'google.com' : '1.2.3.4' 
	# None means NXDOMAIN
}

domains_being_queried_latest_last = [
	# ('google.com', 5), ('example.com', 100)...
]

def send_async_dns_query(domain, name_server_ip_address):
	data = dns.message.make_query(domain, 'A').to_wire()
	dest = (name_server_ip_address, DNS_PORT)
	s.sendto(data, dest)
	print "Sent packet asking about %s to %s" % (domain, name_server_ip_address)

def is_ip_address(str):
	return all([ch in "0123456789." for ch in str])

while True:
	ongoing_count = len(domains_being_queried_latest_last)
	todo_count = len(domains_that_need_querying)
	print "Looping, %s queries ongoing (%s), %s to do (%s)" % (ongoing_count, [x[0] for x in domains_being_queried_latest_last], todo_count, [x[0] for x in domains_that_need_querying])

	if ongoing_count > 0 and todo_count == 0:
		print "Sleeping a bit since just waiting for replies..."
		time.sleep(0.05)

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
				print "Answer for %s took too long, asking again starting from root." % domain
				break
			else:
				print "Nothing expired (oldest %.2f seconds old)" % oldest_elapsed
				break

	if len(domains_being_queried_latest_last) < MAX_CONCURRENT:
		try:
			domain, next_ask = domains_that_need_querying.pop(0)
			print "Doing %s next, need to ask %s" % (domain, next_ask)
			if not is_ip_address(next_ask):
				print "Not an ip address: %s" % next_ask

				# Translate name to IP address if we know it already.
				try:
					ip = domains_for_which_response_received[next_ask]
					print "Knew that %s is %s, asking there for %s later." % (next_ask, ip, domain)
					next_ask = ip
				except KeyError:
					print "Didn't know the ip address for %s yet, try again later." % next_ask

				domains_that_need_querying.append((domain, next_ask))
				continue

			send_async_dns_query(domain, next_ask)
			domains_being_queried_latest_last.append((domain, time.time()))
		except IndexError:
			if len(domains_being_queried_latest_last) == 0:
				print
				print domains_for_which_response_received
				print
				print "All done!"

				for domain in domains:
					print "\t%s\t%s" % (domain, domains_for_which_response_received[domain])

				exit()
	else:
		pass
		# print "Too many concurrent."

	# Loop until nothing more to read from socket.
	while True:
		try:
			data, addr = s.recvfrom(1024)
			print "Received packet from %s" % addr[0]
			response = dns.message.from_wire(data)
			domain = str(response.question[0].name)[:-1]

			domains_being_queried_latest_last = [x for x in domains_being_queried_latest_last if x[0] != domain]

			if response.answer:
				if response.answer[0].rdtype == CNAME_RECORD_RDTYPE:
					cname = str(response.answer[0][0])[:-1]
					print "Got CNAME for %s: %s" % (domain, cname)

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


					exit()
				elif response.answer[0].rdtype == A_RECORD_RDTYPE:
					answer_name = str(response.answer[0].name)[:-1]
					answer_ip = str(response.answer[0][0])
					domains_for_which_response_received[answer_name] = answer_ip
					print "The answer is %s: %s" % (answer_name, answer_ip)
				else:
					print "Answer rdtype for %s was not A but %s" % (domain, response.answer[0].rdtype)
					exit()

			elif response.authority: # Need to ask forward

				# Looks like authority sections don't always give IP addresses for all authority servers.
				# So now there is a dependency, need to resolve some name of server in auth section to continue.

				# Authority section has the name servers to ask next.
				authority_names = [str(auth) for auth in response.authority[0]]

				# Additional section sometimes provides IP addresses for some of those servers for convenience.
				for a in response.additional:
					if a.rdtype == A_RECORD_RDTYPE:
						print "Recording %s as %s" % (str(a.name)[:-1], str(a[0]))
						domains_for_which_response_received[str(a.name)[:-1]] = str(a[0])

				# There might now be a number of name servers that could be asked next. To make things faster,
				# prefer one for which IP address is already known.
				known_ones = [auth[:-1] for auth in authority_names if auth[:-1] in domains_for_which_response_received]
				if known_ones:
					authority_name = random.choice(known_ones)
					print "Picked random known authority: %s" % authority_name
				else:
					authority_name = random.choice(authority_names)[:-1]
					print "Didn't know any of them, so picked random authority: %s" % authority_name

				# If this IP was not in additional, then need to resolve it first.
				print "Do we know %s?" % authority_name,
				next_ask = domains_for_which_response_received.get(authority_name)
				if not next_ask:
					print "No."
					domains_that_need_querying.insert(0, (authority_name, random.choice(root_servers)))
					next_ask = authority_name
				else:
					print "Yes."

				print "Asking forward about %s to %s (%s)" % (domain, authority_name, next_ask)
				domains_that_need_querying.append((domain, next_ask))
				print domains_that_need_querying

		except socket.error, e:
			if e.errno == NO_DATA_ERRNO:
				break
			else:
				print "Some other error on socket"
