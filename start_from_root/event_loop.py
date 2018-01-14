import sys
import networking
import libevent
import time

def event_ready(event, fd, type_of_event, s):
	print "Event ready"
	if type_of_event & libevent.EV_READ:
		networking.got_packet(s)

base = libevent.Base()

while True:
	sys.stdout.write(".")
	sys.stdout.flush()
	time.sleep(0.1)
	base.loop(libevent.EVLOOP_NONBLOCK)
