#!/bin/bash
# Static mode rules: send IPv4 traffic along the primary path s1 - s2 - s4.
# Each rule says: "IPv4 packet for this destination -> out of this port".
# There are no rules on s3 and no flood rules, so the loop stays harmless.
# ARP needs no rules, because the hosts have static ARP tables.
# Needs root. topo.py runs it after the switches have started.

set -e  # stop at the first command that fails

OFCTL="ovs-ofctl -O OpenFlow13"

# s1 ports: 1=h1, 2=h2, 3=h3, 4=s2, 5=s3
$OFCTL add-flow s1 "ip,nw_dst=10.0.0.100,actions=output:4"  # to srv: via s2
$OFCTL add-flow s1 "ip,nw_dst=10.0.0.1,actions=output:1"    # to h1
$OFCTL add-flow s1 "ip,nw_dst=10.0.0.2,actions=output:2"    # to h2
$OFCTL add-flow s1 "ip,nw_dst=10.0.0.3,actions=output:3"    # to h3

# s2 ports: 1=s1, 2=s4
$OFCTL add-flow s2 "ip,nw_dst=10.0.0.100,actions=output:2"  # to srv: via s4
$OFCTL add-flow s2 "ip,nw_dst=10.0.0.1,actions=output:1"    # to h1: via s1
$OFCTL add-flow s2 "ip,nw_dst=10.0.0.2,actions=output:1"    # to h2: via s1
$OFCTL add-flow s2 "ip,nw_dst=10.0.0.3,actions=output:1"    # to h3: via s1

# s4 ports: 1=s2, 2=s3, 3=srv
$OFCTL add-flow s4 "ip,nw_dst=10.0.0.100,actions=output:3"  # to srv
$OFCTL add-flow s4 "ip,nw_dst=10.0.0.1,actions=output:1"    # to h1: via s2
$OFCTL add-flow s4 "ip,nw_dst=10.0.0.2,actions=output:1"    # to h2: via s2
$OFCTL add-flow s4 "ip,nw_dst=10.0.0.3,actions=output:1"    # to h3: via s2
