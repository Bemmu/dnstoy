import code
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

# Initially ask about each domain from a random root server.
root_servers = [socket.gethostbyname('%s.root-servers.net' % ch) for ch in 'abcdefghijkl']	
domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')][0:10]
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
	print "Should ask about %s from %s" % (domain, name_server_ip_address)
	data = dns.message.make_query(domain, 'A').to_wire()
	dest = (name_server_ip_address, DNS_PORT)
	s.sendto(data, dest)

while True:
	sys.stdout.write(".")
	sys.stdout.flush()

	if len(domains_being_queried_latest_last) < MAX_CONCURRENT:
		try:
			domain, name_server_ip_address = domains_that_need_querying.pop()
			send_async_dns_query(domain, name_server_ip_address)
			domains_being_queried_latest_last.append((domain, time.time()))
		except IndexError:
			if len(domains_being_queried_latest_last) == 0:
				print "All done!"
				print domains_for_which_response_received
				exit()
			else:
				print "Nothing to do, just waiting for replies..."
				time.sleep(1.0)
	else:
		pass
		# print "Too many concurrent."

	# Should allow for multiple recvs per tick

	while True:
		try:
			data, addr = s.recvfrom(1024)
			response = dns.message.from_wire(data)
			domain = str(response.question[0].name)[:-1]

			domains_being_queried_latest_last = [x for x in domains_being_queried_latest_last if x[0] != domain]

			if response.answer:
				answer_name = str(response.answer[0].name)
				answer_ip = str(response.answer[0][0])
				domains_for_which_response_received[answer_name] = answer_ip
				print "The answer is %s: %s" % (answer_name, answer_ip)
				# code.interact(local=locals())

			elif response.authority: # Need to ask forward

				# Looks like authority sections don't always have additional sections with IP addresses listed...
				# Need to plan what to do then. There can be a dependency now? Need to resolve some name before can
				# continue resolving another...

				authority_names = [str(auth) for auth in response.authority[0]]

				additional_ips = {}
				for a in response.additional:
					if a.rdtype == A_RECORD_RDTYPE:
						additional_ips[str(a.name)] = str(a[0])

				authority_name = random.choice(authority_names)
				next_ip = additional_ips[authority_name]
				print "Asking forward about %s to %s (%s)" % (domain, authority_name[:-1], next_ip)
				domains_that_need_querying.append((domain, next_ip))

		except socket.error, e:
			if e.errno == NO_DATA_ERRNO:
				break
			else:
				print "Some other error on socket"

	time.sleep(0.1)
