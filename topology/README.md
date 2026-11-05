# Part A — Network & emulation (Georgescu Mihai)

Files: `topo.py` (Mininet topology), `static_flows.sh` (flows for static mode).

## Topology

```
     IoT gateway site                                   Cloud DC
  h1 ──1┐                    1┌── s2 ──┐2               (primary, 5 ms links)
  h2 ──2┼── s1 4─────────────┘          └─1  s4 3── srv
  h3 ──3┘      5─────────────┐          ┌─2
                             1└── s3 ──┘2               (backup, 15 ms links)
```
(numbers = OpenFlow port numbers on the switch next to them)

| Host | IP | Role |
|---|---|---|
| h1 | 10.0.0.1 | IoT sensor (telemetry pings) |
| h2 | 10.0.0.2 | IoT sensor (telemetry pings) |
| h3 | 10.0.0.3 | bulk sender (iperf3 load) |
| srv | 10.0.0.100 | cloud server |

Switches s1..s4 (dpid 1..4), Open vSwitch, OpenFlow 1.3.

| Switch | Port 1 | Port 2 | Port 3 | Port 4 | Port 5 |
|---|---|---|---|---|---|
| s1 | h1 | h2 | h3 | s2 | s3 |
| s2 | s1 | s4 | | | |
| s3 | s1 | s4 | | | |
| s4 | s2 | s3 | srv | | |

## Link parameters (TCLink)

| Links | Bandwidth | Delay |
|---|---|---|
| host – switch | 100 Mbit/s | 1 ms |
| s1–s2, s2–s4 (primary) | 10 Mbit/s | 5 ms |
| s1–s3, s3–s4 (backup) | 10 Mbit/s | 15 ms |

- **10 Mbit/s on the WAN links** so the background load (5 Mbit/s UDP) is a
  big share of the link and has a visible effect on the pings.
- **5 ms primary vs 15 ms backup** so the two paths are clearly different
  (backup RTT ≈ 2 × (1+15+15+1) = 64 ms).
- **Expected RTT on the primary path** = 2 × (1 + 5 + 5 + 1) = **24 ms**.
  The minimum RTT measured in every run is **≈ 25 ms**, so the delays work.

## Why `failMode='secure'` and static ARP

The two paths s1–s2–s4 and s1–s3–s4 form a **loop**. Any flooded packet
(e.g. an ARP broadcast) would go around it forever. So nothing may flood:

- `failMode='secure'`: a switch forwards **only** by its flow rules. Without
  it, OVS falls back to a learning switch when it has no controller, and
  that floods.
- `net.staticArp()`: every host already knows every MAC address, so no ARP
  broadcast is ever sent.

## What `static_flows.sh` installs (static mode)

One rule per destination: "IPv4 to this IP → out of this port"
(`ovs-ofctl -O OpenFlow13 add-flow`).

| Switch | to srv (10.0.0.100) | to h1 | to h2 | to h3 |
|---|---|---|---|---|
| s1 | port 4 (→ s2) | port 1 | port 2 | port 3 |
| s2 | port 2 (→ s4) | port 1 (→ s1) | port 1 | port 1 |
| s4 | port 3 (→ srv) | port 1 (→ s2) | port 1 | port 1 |
| s3 | — | — | — | — |

**s3 stays empty**: all traffic uses the primary path. With no rules and
`failMode='secure'`, s3 drops anything it gets, so the loop can do no harm.
The price: if a primary link fails, static mode does **not** recover.

## How to run

```bash
sudo mn -c                                        # clean leftovers first
sudo python3 topology/topo.py --mode static       # flows from static_flows.sh
sudo python3 topology/topo.py --mode reactive     # start Ryu first (controller/README.md)
```
Both open the Mininet CLI (try `h1 ping srv`, `exit` to stop). The
measurement scripts use the same network through `create_net(mode)`.

## After the midterm

`link_failure.sh`: takes the s1–s2 link down in the middle of a run, to
measure how long failover mode needs to move traffic to the backup path.
