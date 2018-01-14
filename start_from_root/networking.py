closed_sockets = set()

def got_packet(socket):
	if s in closed_sockets:
		print "Trying to read from closed socket!"
		exit()

	response, addr = s.recvfrom(1024)
	server_ip = addr[0]
	print "Received packet from %s!" % server_ip

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