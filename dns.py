# Very simple DNS stub resolver.
# Doesn't do recursive queries. No error handling. Assumes server is not malicious.
# This is a nice resource to understand the packets: http://www.zytrax.com/books/dns/ch15/
#
# RR = DNS Resource Record

import random
import struct
import pprint

RCODE_NAME_ERROR = 3
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

QTYPES = {
	0x0001: "A",
	0x0002: "NS",
	0x0005: "CNAME",
	0x0006: "SOA",
	0x000B: "WKS",
	0x000C: "PTR",
	0x000F: "MX",
	0x0021: "SRV",
	0x001C: "AAAA"
}
QTYPESi = dict((v, k) for k, v in QTYPES.items())

# Second 16 bits 
flags = [
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

def pack_bits(field_definitions):
	bits = 0
	for i, f in enumerate(field_definitions):
		value, bitcount = f[0], f[1]
		bits <<= bitcount
		bits |= value
	return bits

def make_dns_query_packet(query = "google.com.", id = None):

	# First 16 bits is an ID for the query, so that responses can be matched
	if not id:
		ID = random.randint(0, 65535) # 16
	# print "Picked ID", ID

	# Next values, all 16 bits
	QDCOUNT = 1 # how many questions? 
	ANCOUNT = 0 # how many answers? 
	NSCOUNT = 0 # how many authority records?
	ARCOUNT = 0 # how many additional records?

	header = struct.pack('!HHHHHH', ID, pack_bits(flags), QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT)

	qname = "".join([struct.pack('!B', len(label)) + label for label in query.split('.')])
	QTYPE = QTYPESi['A'] # 1 means querying for A record (CNAME is 5, MX is 15)
	qtype = struct.pack('!H', QTYPE)
	QCLASS = 1 # the Internet
	qclass = struct.pack('!H', QCLASS)

	question = qname + qtype + qclass

	return header + question

def parse_header(header):
	message_id, second = struct.unpack('!HH', header[0:4])
	# print "Second: %s" % bin(second)
	# message_id, a, b = struct.unpack('!HBB', header[0:4])
	# print "(%s %s)" % (bin(a), bin(b))
	out = {
		'id' : message_id
	}
	for _, bitlength, field_name in reversed(flags):
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

def parse_label(chunk):
	# Length of string, followed by actual string bytes for each part of domain name ("label").
	# Zero length label means end of domain name.
	i = 0
	parts = []
	while True:
		part_length = ord(chunk[i])
		if part_length == 0:
			break
		parts.append(chunk[i+1:i+1+part_length])
		i += part_length + 1
	i += 1
	return i, ".".join(parts)

# https://tools.ietf.org/html/rfc1035
# "4.1.2. Question section format"
def parse_question_section(section):
	print "Parsing question section"

	bytes_read, domain_name = parse_label(section)
	qtype, qclass = struct.unpack('!HH', section[bytes_read:bytes_read+4])

	print "Received answer for", domain_name
	print "QTYPE:", QTYPES[qtype]
	print "QCLASS:", "Internet" if qclass == 1 else "Something strange!"

	question_section_length = bytes_read + 4
	return question_section_length, domain_name

def parse_answer_section(section, whole_response):

	# NAME could either be a pointer to previously mentioned domain name, or an actual name.
	# 

	# print " ".join(hex(ord(c)) for c in section)

	# Starts off with NAME like 0xc00c (two bytes)

	first_16_bits = struct.unpack('!H', section[0:2])[0]
	is_pointer = (first_16_bits & 0b1100000000000000) != 0
	if is_pointer:
		pointer = first_16_bits & 0b0011111111111111
		pointed = whole_response[pointer:]
		pointed_label_length, pointed_label = parse_label(pointed)
		print 'Answer section contained pointer to label "' + pointed_label + '"'
		name_length = 2
	else:
		print "Not a pointer... not implemented"
		exit()

	# Then comes the TYPE represented as two bytes which is the requested type (A, MX etc.)
	# And again "Internet" as 0x00 0x01
	qtype = struct.unpack('!H', section[name_length:name_length + 2])[0]
	print "Answer section QTYPE:", QTYPES[qtype]
	record_class = struct.unpack('!H', section[name_length + 2:name_length + 2 + 2])[0]
	print "Answer section class:", {1:"Internet"}.get(record_class, "Unknown")

	print " ".join(hex(ord(c)) for c in section[name_length + 2 + 2:])

	ttl = struct.unpack('!L', section[name_length + 2 + 2:name_length + 2 + 2 + 4])[0]
	print "TTL:", ttl, "(time in seconds record may be cached)"
	rdlength = struct.unpack('!H', section[name_length + 2 + 2 + 4:name_length + 2 + 2 + 4 + 2])[0]
	print "RDLENGTH:", rdlength, "(RDATA section length)"

	total_length = name_length + 2 + 2 + 4 + 2 + rdlength

	print qtype

	if QTYPES[qtype] == "A":
		# Now next comes the actual IP address
		lip = struct.unpack('!BBBB', section[name_length + 2 + 2 + 4 + 2:name_length + 2 + 2 + 4 + 2 + 4])
		ip_address = ".".join([str(b) for b in lip])
		print "\n"
		print "\t\t", pointed_label, "has IP address", ip_address
		print "\n"
	elif QTYPES[qtype] == "SOA":
		print "Ignoring SOA qtype, this happens when domains don't exist" # happens for example for mew-s.jp
		return False
		# exit()
	elif QTYPES[qtype] == "CNAME":
		# For a CNAME, RDATA would be the result?
		rdata = section[name_length + 2 + 2 + 4 + 2:name_length + 2 + 2 + 4 + 2 + rdlength]
		print pointed_label, "-->", parse_label(rdata)[1]
		print "Oh, it's a CNAME, probably pointing to another field in the answer section. Not implemented yet!"
		exit()
	else:
		print "Answer section parsing for this qtype %s not implemented" % QTYPES[qtype]
		exit()

	return total_length, QTYPES[qtype], ip_address

# Returns True if domain existed, False if not
def parse_response(response):
	id_bytes = 2
	flag_bytes = 2
	count_bytes = 2 * 4
	header_length = id_bytes + flag_bytes + count_bytes
	header = response[0:header_length]
	out = parse_header(header)

	print "DNS reply header contents:"
	pprint.pprint(out, indent = 4)

	# Question section is variable size, so can't actually cut out just that without looking at it,
	# so pass the whole rest of the response to question section parser.
	question_section = response[header_length:]
	question_section_length, domain = parse_question_section(question_section)
	print "Question section was", question_section_length, "bytes"

	if out['RCODE'] == RCODE_NAME_ERROR:
		return False, domain, None

	answer_section_count = out['ANCOUNT'][0]


	ip_address = None
	answer_section_offset = 0
	for i in range(0, answer_section_count):

		print
		print
		print "--------------------------------"
		print "Parsing answer section number %s" % i
		answer_section = response[header_length + question_section_length + answer_section_offset:]

		# Answer section may contain pointers to earlier parts because of compression, 
		# which is why entire response needs to be passed in.
		answer_section_length, qtype, ip_address = parse_answer_section(answer_section, response)

		if qtype == 'CNAME':
			print "Got CNAME, pausing here"
			exit()

		answer_section_offset += answer_section_length
		print "--------------------------------"
		print
		print

	# if answer_section_count > 1:
	# 	print "Debug end, fixme"
	# 	exit()

	# Now this is broken!
	if not ip_address:
		return False, domain, None
	else:
		return True, domain, ip_address

