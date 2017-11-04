# DNS toy

Despite relying on DNS every day, I realized I have a poor understanding of how it works. This is my little research project to educate myself.

## What will this do?

Construct [DNS packets](https://tools.ietf.org/html/rfc1035) and send them over UDP. When the response comes, parse it and display the IP address. So a bit like **dig**, except ugly and with support only for nonrecursive queries.

I will hack things to work as I go along, using the top 1 million domains list as my testbed.

## How's it progressing?

So far this project has been a success, as I discovered that my own registrar was using a rogue name server that was redirecting all accesses to my homepage through their website.

## What I've learned

List of some things I wanted to know through writing this, and what I've found out.

### Basic socketry

**Q: Do you need one socket per query, or per name server?**
**A: Per name server.**

**Q: Do you need to open a new socket to listen to UDP responses?**
**A: No. You can recvfrom() the socket you used to send the packet.**

**Q: Is libevent usable by mere mortals?**
**A: Yes. You create a libevent base, add sockets to it and then base.loop(libevent.EVLOOP_NONBLOCK) to get a jolt of callbacks if things have happened to them.**

### Socket limits

**Q: How many files can you have open?**
**A: 256 by default on Mac OS X. ulimit -n**

**Q: How do you get more?**
**A: ulimit -n 12345**

**Q: How do you know from Python what the open file limit is?**
**A: The resources module has getrlimit(resource.RLIMIT_NOFILE).**

**Q: How do I know how many files I have open now?**
**A: lsof -p PID HERE**

### DNS corner cases

**Q: Do any name servers actually send out responses with no ANSWER sections?**
**A: Yes.**

## What I want to learn next

**Q: What happens if you query a name server too fast?**
*A: ??? It stops responding at least. Not sure if it complains first somehow, need to look at responses more carefully.*
