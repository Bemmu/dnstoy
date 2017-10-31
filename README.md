# DNS toy

Despite relying on DNS every day, I realized I have a poor understanding of how it works. This is my little research project to educate myself.

## What will this do?

To elaborate, this is an attempt to write a simple Python program which can construct and parse [DNS packets](https://tools.ietf.org/html/rfc1035) and send them over UDP. So a bit like **dig**, except ugly and with support only for nonrecursive DNS queries.

I will hack things to work as I go along, using the top 1 million domains list as my testbed.

## How's it progressing?

So far this project has been a success, as I discovered that my own registrar was using a rogue name server that was redirecting all accesses to my homepage through their website.