# DNS toy

Despite relying on DNS every day, I realized I have poor understanding on how it works.

This is an attempt to write a simple Python program which can construct and parse DNS packets and send them over UDP. No recursive DNS queries will be attempted.

In its current state, this experiment can construct a packet and send it to Google DNS server, get the response and parse out the header from it.

