#!/usr/bin/env bash
# Run once, on the Oracle VM itself, as root (sudo ./setup-firewall.sh).
#
# Oracle requires the SAME three ports opened in TWO separate places — miss
# either one and the site is unreachable even though everything else is
# correct:
#
#   1. THIS SCRIPT — the instance's own OS-level firewall (iptables). Oracle's
#      stock images ship with iptables already dropping everything but SSH.
#
#   2. THE ORACLE CLOUD CONSOLE — a Security List (or Network Security Group)
#      on the VCN, which filters traffic before it ever reaches the instance.
#      This cannot be done from a script; it's a manual step in the console:
#        Networking -> Virtual Cloud Networks -> (your VCN) -> Security Lists
#        -> (default list) -> Add Ingress Rules:
#          - Source 0.0.0.0/0, TCP, destination port 80
#          - Source 0.0.0.0/0, TCP, destination port 443
#        (port 22/SSH is almost always already open by default — verify it,
#        don't assume it)
#
# This script assumes Ubuntu (apt / iptables-persistent). If you provisioned
# an Oracle Linux image instead, it uses firewalld, not raw iptables — run
# the firewalld equivalents instead:
#   sudo firewall-cmd --permanent --add-service=ssh
#   sudo firewall-cmd --permanent --add-service=http
#   sudo firewall-cmd --permanent --add-service=https
#   sudo firewall-cmd --reload

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this as root: sudo ./setup-firewall.sh" >&2
  exit 1
fi

echo "Installing iptables-persistent (so rules survive a reboot)..."
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables-persistent

echo "Setting rules..."
iptables -F
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Already-open connections (e.g. your own SSH session) keep working.
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# SSH, HTTP, HTTPS. Nothing else needs to be reachable from the internet —
# Postgres, Redis and ClamAV are not published to the host at all (see
# docker-compose.prod.yml), so there is nothing else to open.
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# ICMP (ping) — harmless, useful for diagnostics.
iptables -A INPUT -p icmp -j ACCEPT

echo "Saving rules so they survive a reboot..."
netfilter-persistent save

echo "Done. Current rules:"
iptables -L -n -v
echo
echo "Reminder: this only covers the instance's own firewall. You still need"
echo "to open 80 and 443 in the Oracle Cloud console's Security List — see"
echo "the comment block at the top of this script."
