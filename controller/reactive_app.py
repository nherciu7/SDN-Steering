"""Reactive routing app for Ryu (OpenFlow 1.3).

Start:  ryu-manager controller/reactive_app.py

1. When a switch connects, it gets a table-miss rule: "send to controller".
2. When an IPv4 packet reaches the controller, we look up its destination
   in PRIMARY_PATH, install a flow for that destination on every switch of
   the primary path (s1 -> s2 -> s4), then send the packet on its way.
   Later packets match the flows and never come to the controller, so only
   the first packet is slow (this is the first-packet delay we measure).

Nothing is ever flooded: the topology has a loop and ARP is static.
"""

from datetime import datetime

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ethernet, ether_types, ipv4, packet
from ryu.ofproto import ofproto_v1_3

# Primary path, built from the port table in CLAUDE.md.
# destination IP -> {switch dpid: output port on that switch}
PRIMARY_PATH = {
    '10.0.0.100': {1: 4, 2: 2, 4: 3},   # to srv: s1->s2, s2->s4, s4->srv
    '10.0.0.1':   {4: 1, 2: 1, 1: 1},   # to h1:  s4->s2, s2->s1, s1->h1
    '10.0.0.2':   {4: 1, 2: 1, 1: 2},   # to h2:  ...,             s1->h2
    '10.0.0.3':   {4: 1, 2: 1, 1: 3},   # to h3:  ...,             s1->h3
}


class ReactiveApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}  # dpid -> datapath (connection to that switch)

    def add_flow(self, dp, priority, match, actions):
        """Send a FlowMod that adds one rule to table 0 of switch dp."""
        parser = dp.ofproto_parser
        inst = [parser.OFPInstructionActions(dp.ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority,
                                      match=match, instructions=inst))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_connected(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        self.datapaths[dp.id] = dp

        # Table-miss: priority 0, match everything, send whole packet to us.
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, parser.OFPMatch(), actions)
        self.logger.info('switch s%d connected, table-miss installed', dp.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser

        # Only IPv4 is routed; everything else is dropped (never flooded).
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype != ether_types.ETH_TYPE_IP:
            return
        dst = pkt.get_protocol(ipv4.ipv4).dst

        path = PRIMARY_PATH.get(dst)
        if path is None:
            self.logger.info('no path for %s, dropped', dst)
            return

        # Install "IPv4 to dst -> out_port" on every switch of the path.
        for dpid, out_port in path.items():
            sw = self.datapaths.get(dpid)
            if sw is None:
                continue  # switch not connected (yet)
            match = sw.ofproto_parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                               ipv4_dst=dst)
            actions = [sw.ofproto_parser.OFPActionOutput(out_port)]
            self.add_flow(sw, 10, match, actions)
        self.logger.info('%s installed path to %s (packet-in from s%d): %s',
                         datetime.now().strftime("%H:%M:%S.%f")[:-3], dst, dp.id,
                         ', '.join('s%d->port %d' % (d, p)
                                   for d, p in path.items()))

        # Send the first packet out of the switch where it arrived.
        out_port = path.get(dp.id)
        if out_port is None:
            return
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp, buffer_id=ofp.OFP_NO_BUFFER, in_port=msg.match['in_port'],
            actions=[parser.OFPActionOutput(out_port)], data=msg.data))
