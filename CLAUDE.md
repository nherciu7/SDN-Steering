# CLAUDE.md — shared brief for every Claude working on this repo

Read this whole file before doing anything. Three students work on this
project, each with their own Claude session in VS Code. You are one of
those three sessions. The student will tell you who they are in their
first message.

## The project

- Course: Data Communications, group project 2026–2027, Politehnica
  Bucharest, 4th year **bachelor** (group 442G). Project 8.
- Title: **SDN steering of IoT traffic to the cloud.**
- Question: how does static routing compare with controller-driven
  (SDN) routing for IoT traffic going from a gateway site to a cloud
  server, in latency, loss, throughput, first-packet delay and (final)
  recovery after a link failure?
- Repository: https://github.com/nherciu7/SDN-Steering
- The full plan is `docs/Project8_Roadmap_442G_v2.pdf`.

**Level:** this is a bachelor project. The teacher rejected the first
roadmap as "master/PhD level". Keep code short, readable and commented.
No clever abstractions, no extra frameworks, no statistics beyond
average / min / max. If a simpler way works, use it.

## The team — who owns what

Each student commits their own part from their own GitHub account. The
teacher checks the git history against these owners, so **only edit
files in your student's own part** unless they explicitly ask you to.

| Member | Part | Owns these files |
|---|---|---|
| Georgescu Mihai | A — Network & emulation | `topology/` (topo.py, static_flows.sh, link_failure.sh) |
| Dragu Stefan | B — Control plane (Ryu) | `controller/` (reactive_app.py, later failover_app.py) |
| Herciu Nichita | C — Measurement & automation | `measurement/`, `results/`, `README.md` |

`CLAUDE.md`, `.claude/`, `docs/` are shared and only change when the
whole team agrees.

If your student needs something from another part (e.g. Nichita needs
the topology), **use it, don't rewrite it.** If it's missing or broken,
tell your student what to ask the owner for.

## GIT RULES — strict

- **Never run `git commit`, `git push`, `git merge`, `git rebase`, or
  any `gh` command.** The students commit and push by hand so the
  history shows them, not Claude. These are also blocked in
  `.claude/settings.json`.
- `git status`, `git diff`, `git log`, `git pull` are fine.
- When a piece of work is done, stop and tell the student: which files
  changed, and a suggested one-line commit message. They do the rest.
- Never add "Co-authored-by: Claude" or similar anywhere.

## Environment (same for all three)

- Windows laptops running the official **Mininet 2.3.0 VM** (Ubuntu
  20.04, Python 3.8) in VirtualBox. VS Code connects to it over
  Remote-SSH, so you run *inside the VM*. User `mininet`, has sudo.
- Mininet + Open vSwitch come preinstalled. Mininet needs `sudo`.
- Controller: **Ryu** (Python), OpenFlow 1.3, listening on
  127.0.0.1:6653. Start: `ryu-manager controller/reactive_app.py`.
- Tools: `ping`, `iperf3`, `ovs-ofctl -O OpenFlow13`, Python 3 with
  matplotlib.
- Before every Mininet run: `sudo mn -c` to clean leftovers.

## The network — FIXED SPEC (everyone codes against this)

Do not change names, IPs or port numbers without the whole team
agreeing: part B hardcodes the paths and part C hardcodes the hosts.

```
        IoT gateway site                          Cloud DC
   h1 ─┐                   ┌── s2 ──┐  (primary, fast)
   h2 ─┼── s1 ─────────────┤        ├── s4 ── srv
   h3 ─┘                   └── s3 ──┘  (backup, slow)
```

Hosts (static ARP on):

| Host | IP | Role |
|---|---|---|
| h1 | 10.0.0.1 | IoT sensor (telemetry pings) |
| h2 | 10.0.0.2 | IoT sensor (telemetry pings) |
| h3 | 10.0.0.3 | bulk sender (iperf3 load) |
| srv | 10.0.0.100 | cloud server (ping target, iperf3 server) |

Switches: s1..s4, dpid 1..4, OVS, `protocols='OpenFlow13'`.

Port numbers (set explicitly with `port1=`/`port2=` in `addLink`):

| Switch | Port 1 | Port 2 | Port 3 | Port 4 | Port 5 |
|---|---|---|---|---|---|
| s1 | h1 | h2 | h3 | s2 | s3 |
| s2 | s1 | s4 | | | |
| s3 | s1 | s4 | | | |
| s4 | s2 | s3 | srv | | |

Links (`TCLink`):
- switch–switch: `bw=10` Mbit/s. Primary links (s1–s2, s2–s4)
  `delay='5ms'`; backup links (s1–s3, s3–s4) `delay='15ms'`.
- host–switch: `bw=100`, `delay='1ms'`.

Primary path: s1 → s2 → s4. Backup path: s1 → s3 → s4. The topology
has a loop, so **nothing may flood**: no learning switch, no
`ovs-testcontroller`, static ARP in Mininet, rules match IPv4 only.

### Topology interface (part A provides, part C uses)

`topology/topo.py` must expose:

```python
def create_net(mode):
    """mode = 'static'   -> no controller, switches failMode='secure',
                           static flows installed (calls static_flows.sh)
       mode = 'reactive' (later also 'failover')
                        -> RemoteController at 127.0.0.1:6653
       Returns a STARTED Mininet net with net.staticArp() applied.
       The caller stops it with net.stop()."""
```

and run on its own with `sudo python3 topology/topo.py --mode static`
(opens the Mininet CLI). `topology/static_flows.sh` installs the static
mode flows with `ovs-ofctl -O OpenFlow13`. `failMode='secure'` matters:
without it OVS behaves as a learning switch and the loop breaks
everything.

## The three routing modes

1. **static** — no controller; flows preinstalled on the primary path by
   `static_flows.sh`. On link failure it does NOT recover (expected).
2. **reactive** — Ryu app `controller/reactive_app.py`: table-miss sends
   to controller; on packet-in for IPv4 it looks up the destination,
   installs flows along the primary path on all switches of that path,
   then sends the packet out. First packet is slower → this is the
   "first-packet delay" we measure.
3. **failover** (after midterm) — reactive + listens for port-down
   events; when a primary link goes down it deletes the flows and
   installs the backup path.

## Measurements (part C)

- Telemetry: h1 and h2 ping srv (`-i 0.2`, for failover `-i 0.1`).
- Load: bulk = 0 (none) or 1 (h3 → srv `iperf3 -b 8M`, UDP).
- Each run: 30 s (midterm). Raw logs to
  `results/raw/<mode>_bulk<b>_rep<r>/`.
- KPIs: RTT avg/min/max (ms), packet loss (%), first-packet delay
  (first ping RTT − average RTT of the rest), throughput (Mbit/s from
  iperf3); final adds failover time (lost consecutive pings × interval).
- `results/summary.csv` one row per run; plots in `results/plots/`
  (bar charts with min/max error bars across repetitions).

## Midterm goal (Mon 9 Nov 2026)

Topology runs; static and reactive modes both work; 2 modes × 2 load
levels × 3 repetitions = 12 runs done by script; plots of RTT,
first-packet delay and throughput; README explains how to reproduce.
Failover, link failure, and the final matrix come after the midterm.

## How to work

- Small steps. After each step, run it and show the student the
  output.
- If something can't be tested yet (another part missing), say so
  plainly instead of faking it.
- Explain what you did in plain words; the student must be able to
  present every file at the midterm.
