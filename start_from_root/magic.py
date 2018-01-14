import time
import socket
import random
import networking

domains_for_which_response_received = {
	# 'google.com' : '1.2.3.4' 
	# None means NXDOMAIN
}

max_concurrent = 1
domains_queried_latest_last = [
	# ('google.com', 5), ('example.com', 100)...
]

domains_that_need_querying = [
	# (domain, where to ask),
	# (domain, where to ask), ...
]

root_servers = networking.root_servers()

print "Reading domain list..."
domains = [l.split(",")[1].strip() for l in open('../opendns-top-1m.csv')][0:1000]
domains_that_need_querying = [(domain, random.choice(root_servers)) for domain in domains]
print domains_that_need_querying[0]
print "Read domain list."

def init():
	pass

def tick():
	domain, where_to_ask = domains_that_need_querying.pop()
	networking.send_async_dns_query(domain, where_to_ask)
	domains_queried_latest_last.append((domain, time.time()))
	print domains_queried_latest_last
	exit()

	pass