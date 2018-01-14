import dns
import dns.message
import socket
from event_loop import add_event

# Since this is UDP, just one socket to represent our endpoint is enough.
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setblocking(False)

def send_async_dns_query(domain, where_to_ask):
	data = dns.message.make_query(domain, 'A').to_wire()
	send_nonblocking_packet(data, where_to_ask)
	add_event()
	dest = (ip_address, DNS_PORT)
	s.sendto(data, dest)
	print "Sent packet to %s" % dest[0]

def root_servers():
	return [socket.gethostbyname('%s.root-servers.net' % ch) for ch in 'abcdefghijkl']	

def got_packet(socket):
	if s in closed_sockets:
		print "Trying to read from closed socket!"
		exit()

	response, addr = s.recvfrom(1024)
	server_ip = addr[0]
	print "Received packet from %s!" % server_ip

