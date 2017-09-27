# RR = DNS Resource Record

# Simple DNS stub resolver
# (doesn't do recursive queries)

import random
import struct
import pprint

# First 16 bits is an ID for the query, so that responses can be matched
ID = random.randint(0, 65535) # 16

# Second 16 bits 
second_fields = [
	# value, bitcount, description 
	(0, 1, 'QR'), # (ZERO means YES) message is a query? 1 bit 
	(0, 4, 'OPCODE'), # standard query, 4 bits
	(0, 1, 'AA'), # valid in responses 1 bit
	(0, 1, 'TC'), # truncated? 1 bit
	(1, 1, 'RD'), # recursion desired? 1 bit
	(0, 1, 'RA'), # recursion available? 1 bit
	(0, 3, 'Z'), # always 0, reserved for future use 3 bits
	(0, 4, 'RCODE') # 4 bits, in responses only, 0 means no error
]

# Next values, all 16 bits
QDCOUNT = 1 # how many questions? 
ANCOUNT = 0 # how many answers? 
NSCOUNT = 0 # how many authority records?
ARCOUNT = 0 # how many additional records?

def pack_bits(field_definitions):
	bits = 0
	for i, f in enumerate(field_definitions):
		value, bitcount = f[0], f[1]
		bits <<= bitcount
		bits |= value
	return bits

header = struct.pack('!HHHHHH', ID, pack_bits(second_fields), QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT)

# header = struct.pack('!H', 0) # shortcut since all were zeroes
# print " ".join(hex(ord(c)) for c in header)

query = "google.com."
qname = "".join([struct.pack('!B', len(label)) + label for label in query.split('.')])
QTYPE = 1 # 1 means querying for A record (CNAME is 5, MX is 15)
qtype = struct.pack('!H', QTYPE)
QCLASS = 1 # the Internet
qclass = struct.pack('!H', QCLASS)

question = qname + qtype + qclass

data = header + question
# Seemed to be valid, matching data in the screenshot at 
# https://superuser.com/questions/523917/dns-queries-returning-no-answer-section

# print " ".join(hex(ord(c)) for c in data)

message_id, a, b = struct.unpack('!HBB', data[0:4])
# print "(%s %s)" % (bin(a), bin(b))

# qname, qtype, qclass

# Send the data
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
DNS_PORT = 53
dest = ('8.8.8.8', DNS_PORT)
s.sendto(data, dest)
s_ip, s_port = s.getsockname()

print "Sending DNS packet via UDP %s:%s -> %s:%s" % (s_ip, s_port, dest[0], dest[1])

# Listen for response?
# Where does the server send the answer to?
# Does it know the source port and send it there?

# s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# s2.bind(('0.0.0.0', s_port))
response, addr = s.recvfrom(1024)
print "Received DNS packet!"

RCODES = {
	0: "No error condition.",
	1: "Format error - The name server was unable to interpret the query.",
	2: "Server failure - The name server was unable to process this query due to a problem with the name server.",
	3: "Name Error - Meaningful only for responses from an authoritative name server, this code signifies that the domain name referenced in the query does not exist.",
	4: "Not Implemented - The name server does not support the requested kind of query.",
	5: "Refused - The name server refuses to perform the specified operation for policy reasons.  For example, a name server may not wish to provide the information to the particular requester, or a name server may not wish to perform a particular operation (e.g., zone transfer) for particular data."
}
for x in range(6, 16): 
	RCODES[x] = "Reserved for future use."

def parse_header(header):
	message_id, second = struct.unpack('!HH', header[0:4])
	# print "Second: %s" % bin(second)
	# message_id, a, b = struct.unpack('!HBB', header[0:4])
	# print "(%s %s)" % (bin(a), bin(b))
	out = {
		'id' : message_id
	}
	for _, bitlength, field_name in reversed(second_fields):
		found = second & (2**bitlength-1)
		out[field_name] = found
		second >>= bitlength

	out.update({
		'QDCOUNT' : struct.unpack('!H', header[4:6]), 	# Query count
		'ANCOUNT' : struct.unpack('!H', header[2+4:2+6]), # Answer count
		'NSCOUNT' : struct.unpack('!H', header[4+4:4+6]), # Authority count
		'ARCOUNT' : struct.unpack('!H', header[6+4:6+6])  # Additional information count
	})
	return out

def parse_question_section(section):
	pass

def parse_response(response):
	id_bytes = 2
	flag_bytes = 2
	count_bytes = 2 * 4
	header_length = id_bytes + flag_bytes + count_bytes
	header = response[0:header_length]
	out = parse_header(header)

	print RCODES[out["RCODE"]]
	print "DNS reply header contents:"
	pprint.pprint(out, indent = 4)

	# Question section is variable size, so can't actually cut out just that without looking at it,
	# so pass the whole rest of the response to question section parser.
	question_section = response[header_length:]

	return out

response_hexed = " ".join(hex(ord(c)) for c in response)
# print "Received message len %s from %s: %s" % (len(response), addr, response_hexed)
# print ID
print "Parsing response"
parse_response(response)