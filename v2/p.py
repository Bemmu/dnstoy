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

# Initially ask about each domain from a random root server.
root_servers = [socket.gethostbyname('%s.root-servers.net' % ch) for ch in 'abcdefghijkl']	
domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')][0:1000]
domains_that_need_querying = [(domain, random.choice(root_servers)) for domain in domains]

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setblocking(False)

domains_queried_latest_last = [
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

	if len(domains_queried_latest_last) < MAX_CONCURRENT:
		domain, name_server_ip_address = domains_that_need_querying.pop()
		send_async_dns_query(domain, name_server_ip_address)
		domains_queried_latest_last.append((domain, time.time()))

	# Should allow for multiple recvs per tick

	while True:
		try:
			data, addr = s.recvfrom(1024)
			response = dns.message.from_wire(data)
			domain = str(response.question[0].name)[:-1]
			code.interact(local=locals())
		except socket.error, e:
			if e.errno == NO_DATA_ERRNO:
				break
			else:
				print "Some other error on socket"

	time.sleep(0.1)
