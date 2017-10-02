import socket
# import libevent
import dns

DNS_PORT = 53

# Send the data
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dest = ('8.8.8.8', DNS_PORT)
s.sendto(dns.make_dns_query_packet(), dest)

s_ip, s_port = s.getsockname()
print "Sending DNS packet via UDP %s:%s -> %s:%s" % (s_ip, s_port, dest[0], dest[1])

response, addr = s.recvfrom(1024)
print "Received DNS packet!"

response_hexed = " ".join(hex(ord(c)) for c in response)
print "Parsing response"
dns.parse_response(response)

