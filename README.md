# DNS toy

Despite relying on DNS every day, I realized I have poor understanding of how it works.

This is an attempt to write a simple Python program which can construct and parse DNS packets and send them over UDP. No recursive DNS queries will be attempted.

In its current state, this experiment can construct a packet and send it to Google's DNS server. It then receives the reply packet and prints out response details (currently just the header section).

