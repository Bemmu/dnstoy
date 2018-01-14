RETRY_THRESHOLD_SECONDS = 5 

RESOLVED = 1
ASK_HERE = 2

from datetime import datetime
from datetime import timedelta

class DomainResolutionTask():
	def __init__(self, domain):
		self.domain = domain
		self.query_sent_timestamp = None

	def is_sent(self):
		return bool(self.query_sent_timestamp)
	
	def is_expired(self):
		return datetime.today() - self.query_sent > deltatime(RETRY_THRESHOLD_SECONDS)

# Adding is just one-time bulk thing.
#
# Ways I want to query:
#  - List all where query needs to be sent
# 		> This is either expired one or one that hasn't been sent yet
#  - Find one based on domain name
#		> Hash where key is domain

# This would be used in the end to look at the results.
# domains_for_which_response_received = {
# 	'google.com' : '1.2.3.4' 
# } # might as well store as dict since will probably want to access it that way, makes setting easy too

# This should be ordered such that it's fast to find expired ones
# Priority queue?
# domains_queried_latest_last = [('google.com', 5), ('example.com', 100)...]

# Ways to store the time:
# 	- query time
#	- expiration time
# 	- seconds elapsed
#
# You just have a list and append the latest query on it, along with timestamp.
# [('google.com', 5), ('example.com', 100)...] timestamp is increasing towards end
# Then always look at the first item on the list. If that has expired, then do it again.

# Ordering of this doesn't matter
# domains_that_need_querying = [
# 	(domain, where to ask),
# 	(domain, where to ask), ...
# ]

# load list initially here

# Now the big question. What about partial "see here" results.
# Suppose I have to resolve "google.com", sending it to root name server (later replace by cache based on TLD),
# and then I get the response "I don't know, but ask 1.2.3.4". What do I do with that?
# domains_that_need_querying could have an "ask here" field, so if you get a "I don't know ask here" result,
# then you put it back to domains_that_need_querying 