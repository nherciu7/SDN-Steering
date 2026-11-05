#!/usr/bin/env python3
"""Project network: IoT gateway site (s1) to cloud DC (s4) over two paths.

        h1 ─┐                   ┌── s2 ──┐  (primary, fast)
        h2 ─┼── s1 ─────────────┤        ├── s4 ── srv
        h3 ─┘                   └── s3 ──┘  (backup, slow)

Run on its own:  sudo python3 topology/topo.py --mode static
Use from Python: net = create_net('static') ... net.stop()
"""

import argparse
import os
import subprocess

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo

# static_flows.sh sits in the same folder as this file.
FLOWS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'static_flows.sh')

# Link settings from the fixed spec.
HOST_LINK = {'bw': 100, 'delay': '1ms'}
PRIMARY_LINK = {'bw': 10, 'delay': '5ms'}
BACKUP_LINK = {'bw': 10, 'delay': '15ms'}


class SteeringTopo(Topo):
    """Four switches, four hosts, and the port numbers from the fixed spec."""

    def build(self):
        # failMode='secure': a switch forwards only by its flow rules. Without
        # it OVS acts as a learning switch and floods around the s2/s3 loop.
        s1 = self.addSwitch('s1', dpid='1', protocols='OpenFlow13', failMode='secure')
        s2 = self.addSwitch('s2', dpid='2', protocols='OpenFlow13', failMode='secure')
        s3 = self.addSwitch('s3', dpid='3', protocols='OpenFlow13', failMode='secure')
        s4 = self.addSwitch('s4', dpid='4', protocols='OpenFlow13', failMode='secure')

        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        srv = self.addHost('srv', ip='10.0.0.100/24')

        # port1 is the port on the first node, port2 on the second.
        # Hosts have a single interface, which is number 0 (h1-eth0).
        self.addLink(h1, s1, port1=0, port2=1, **HOST_LINK)
        self.addLink(h2, s1, port1=0, port2=2, **HOST_LINK)
        self.addLink(h3, s1, port1=0, port2=3, **HOST_LINK)
        self.addLink(srv, s4, port1=0, port2=3, **HOST_LINK)

        # Primary path: s1 -> s2 -> s4.
        self.addLink(s1, s2, port1=4, port2=1, **PRIMARY_LINK)
        self.addLink(s2, s4, port1=2, port2=1, **PRIMARY_LINK)

        # Backup path: s1 -> s3 -> s4.
        self.addLink(s1, s3, port1=5, port2=1, **BACKUP_LINK)
        self.addLink(s3, s4, port1=2, port2=2, **BACKUP_LINK)


def create_net(mode):
    """mode = 'static'   -> no controller, static flows installed
       mode = 'reactive' or 'failover' -> RemoteController at 127.0.0.1:6653
       Returns a STARTED Mininet net with net.staticArp() applied.
       The caller stops it with net.stop()."""
    if mode == 'static':
        controller = None
    elif mode in ('reactive', 'failover'):
        controller = RemoteController('c0', ip='127.0.0.1', port=6653)
    else:
        raise ValueError('unknown mode: ' + mode)

    # TCLink is the link type that applies the bw and delay settings.
    net = Mininet(topo=SteeringTopo(), switch=OVSSwitch, link=TCLink,
                  controller=controller)
    net.start()

    # Fill every host's ARP table, so no ARP broadcast can loop in the network.
    net.staticArp()

    # With no controller, the switches get their rules from our script.
    if mode == 'static':
        subprocess.run(['bash', FLOWS_SCRIPT], check=True)

    return net


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the project network.')
    parser.add_argument('--mode', choices=['static', 'reactive', 'failover'],
                        default='static')
    args = parser.parse_args()

    setLogLevel('info')  # make Mininet print what it is doing
    net = create_net(args.mode)
    CLI(net)             # stay in the Mininet prompt until the user types exit
    net.stop()
