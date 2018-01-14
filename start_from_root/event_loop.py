import sys
import libevent
import time

import networking
import magic

events = []

def event_ready(event, fd, type_of_event, s):
	print "Event ready"
	if type_of_event & libevent.EV_READ:
		networking.got_packet(s)

def listen_for_events_on_socket(socket):
	print "Add event"
	event = libevent.Event(base, socket.fileno(), libevent.EV_READ|libevent.EV_PERSIST, event_ready, socket)
	event.add(1)

	# Without this the event is garbage collected (issue with reference counting?)
	events.append(event)

base = libevent.Base()

while True:
	magic.tick()
	sys.stdout.write(".")
	sys.stdout.flush()
	time.sleep(0.1)
	base.loop(libevent.EVLOOP_NONBLOCK)
