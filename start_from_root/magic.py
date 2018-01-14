import socket

domains_for_which_response_received = {
	# 'google.com' : '1.2.3.4' 
	# None means NXDOMAIN
}

domains_queried_latest_last = [
	# ('google.com', 5), ('example.com', 100)...
]

domains_that_need_querying = [
	# (domain, where to ask),
	# (domain, where to ask), ...
]

root_servers = [socket.gethostbyname('%s.root-servers.net' % ch) for ch in 'abcdefghijkl']
print root_servers
exit()

def load_domains():
	print "Reading domain list..."
	domain_list = [l.split(",")[1].strip()+"." for l in open('opendns-top-1m.csv')][0:1000]
	domain_list.append("rutracker.org.")
	# print domain_list
	# domain_list = ["rutracker.org"]
	print "Read domain list."

def init():
	pass

def tick():
	pass