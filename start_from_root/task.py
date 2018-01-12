RESOLVED = 1
ASK_HERE = 2

from datetime import datetime
from datetime import timedelta

class Task():
	def __init__(self, domain):
		self.domain = domain
		self.query_sent = None
	
	def is_expired(self):
		return datetime.today() - self.query_sent > deltatime(seconds = 5)
