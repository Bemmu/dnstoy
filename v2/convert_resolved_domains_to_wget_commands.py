import csv
for domain, ip in csv.reader(open('resolved_domains.csv')):
	ip = ip.strip()

	print domain, ip

# with open('resolved_domains.csv', 'r') as r, open('wget_commands', 'w') as w:
# 	for line in r:



