# Part B — Control plane (Dragu Stefan)

File: `reactive_app.py`, a Ryu app (OpenFlow 1.3) for **reactive** mode.

## What it does, step by step

1. **Switch connects** → the app installs a **table-miss** rule
   (priority 0, match everything, action: send to controller).
2. **First packet** for a destination finds no rule → the switch sends it
   to Ryu as a **packet-in**.
3. **Path lookup**: the app reads the IPv4 destination and looks it up in
   `PRIMARY_PATH` (destination IP → output port on each switch). The path is
   always the primary one, s1 → s2 → s4.
4. **Install flows**: on **every switch of the path** it adds
   "IPv4 to dst → out_port" with **priority 10** (above the table-miss).
5. **Packet-out**: it sends the first packet out of the switch where it
   arrived, so that packet is not lost.

All later packets match the priority-10 rules and never go to the
controller. Only the first packet pays the controller round trip: this is
the **first-packet delay** we measure.

## Why only IPv4 and no flooding

The topology has a loop (s1–s2–s4 and s1–s3–s4), so a flooded packet would
circulate forever. The hosts have static ARP, so no ARP is needed. The app
therefore routes **only IPv4** and simply ignores anything else. It never
floods and is not a learning switch.

## How to run

```bash
ryu-manager controller/reactive_app.py          # listens on 127.0.0.1:6653
sudo python3 topology/topo.py --mode reactive   # in a second terminal
```
`measurement/run_test.py --mode reactive` starts and stops Ryu by itself and
saves its log as `controller.log` in the run folder.

## Log lines

```
switch s1 connected, table-miss installed
12:32:48.711 installed path to 10.0.0.100 (packet-in from s1): s1->port 4, s2->port 2, s4->port 3
12:32:48.728 installed path to 10.0.0.2 (packet-in from s4): s4->port 1, s2->port 1, s1->port 2
```
- `switch sN connected`: the switch reached the controller and got its
  table-miss rule (one line per switch, 4 in total).
- `installed path to X (packet-in from sN)`: a packet for X reached the
  controller from switch sN, and the rules for X were installed on the
  listed switches and ports. The first line is a ping going to srv; the
  second is its reply coming back to h2 (packet-in at s4).
- The path to srv is usually installed **twice**: the first pings of h1 and
  h2 arrive almost together, both before the rules exist.
- `no path for X, dropped`: the destination is not in `PRIMARY_PATH`.

## Result (midterm)

- **First-packet delay** (no load): **≈ 5.5 ms** in reactive mode (runs
  from 4.8 to 6.9 ms) vs **≈ 0** in static mode (−3.9 ms on average; the
  negative values come from the VM's random jitter). That is the time the
  first packet waits for the controller.
- **After the first packet**, the path is the same as in static mode: the
  minimum RTT is ≈ 25 ms in both modes, and without load the average RTT is
  also similar (31 ms reactive vs 35 ms static, both within the noise).
  With 5 Mbit/s load reactive averaged 46 ms vs 35 ms static, with large
  spikes in one run; 3 runs are too few to call this a real difference.

## After the midterm

`failover_app.py`: reactive + listens for **port-down** events. When a
primary link (s1–s2 or s2–s4) goes down, it deletes the flows and installs
the **backup path s1 → s3 → s4** instead.
