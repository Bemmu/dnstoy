import types
import code
from task import Task
import dns.message
import dns.rdatatype

message = dns.message.make_query("google.com.", "A")
data = message.to_wire()

questions = [
	# Task('google.com')
]

def dummy_questions():
	print "dummy_questions"
	global questions
	for i in range(10**2):
		questions.append(Task('google.com'))

def send_next_query():
	print "send_next_query"
	pass
	# questions.

def foo():
	print "foo"

# Decorate functions so they display what is being called
functions = [(k, v) for k, v in globals().items() if type(v) == types.FunctionType]
for function_name, function in functions:
	def make_function(function_name, function):
		def f(*args, **kwargs):
			print "%s" % function_name
			function(*args, **kwargs)
		return f
		# print "Setting %s to %s" % (function_name, f)
	globals()[function_name] = make_function(function_name, function)

dummy_questions()
send_next_query()
foo()

# globals["send_next_query"] = foo

# code.interact(local=locals())

exit()

questions = [
	('google.com.', '192.5.6.30')
]


('216.239.34.10', 'google.com.')

import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# destination = ('192.5.6.30', 53)
# destination = ('198.41.0.4', 53)
destination = ('216.239.32.10', 53)

s.sendto(data, destination)

response, addr = s.recvfrom(1024)
message = dns.message.from_wire(response)

import pprint

def got_message(message):
	print message.to_text()

	print pprint.pprint(dir(message))

	# What domain name did we ask about again?
	answer_for = str(message.question[0].name)[:-1]

	got_result = False
	if message.answer:
		for answer in message.answer:
			if answer.rdtype == dns.rdatatype.A and answer.name == message.question[0].name:

				# ip_address = 

				print "Got A record for %s: %s!" % (answer_for, answer[0].to_text())
				got_result = True
				break

	print dir(message.answer[0])

	# Now it's either "I don't know, ask this server"
	# OR "The ip address is..."

	print answer_for
	print "Received answer for %s" % answer_for

got_message(message)
exit()

print "%s" % type(message.authority[0])
print message.to_text()

exit()

print response

exit()

import dns.resolver

# print help(dns.resolver.query)
# exit()

# answers = dns.resolver.query('dnspython.org', 'MX')
# for rdata in answers:
#     print 'Host', rdata.exchange, 'has preference', rdata.preference
	      
import dns.query
import dns.zone

print help(dns.query.send_udp)
exit()

# z = dns.zone.from_xfr(dns.query.xfr('192.0.32.132', ''))
z = dns.zone.from_xfr(dns.query.xfr('192.41.162.30', ''))
# l.gtld-servers.net

names = z.nodes.keys()
# names.sort()
for n in names:
    print z[n].to_text(n)