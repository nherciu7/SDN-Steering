# Project 8 — SDN steering of IoT traffic to the cloud

Data Communications group project 2026–2027 · Group 442G · Politehnica Bucharest

IoT sensors at a gateway site send telemetry to a cloud server over two
possible paths (fast primary, slow backup). We compare **static routing**
with **controller-driven (SDN) routing** in RTT, packet loss, throughput,
first-packet delay and (final) recovery after a link failure.

Plan: [`docs/Project8_Roadmap_442G_v2.pdf`](docs/Project8_Roadmap_442G_v2.pdf)

## Team

| Member | Part | Folder | Docs |
|---|---|---|---|
| Georgescu Mihai | A — Network & emulation | `topology/` | [topology/README.md](topology/README.md) |
| Dragu Stefan | B — Control plane (Ryu) | `controller/` | [controller/README.md](controller/README.md) |
| Herciu Nichita | C — Measurement & automation | `measurement/`, `results/` | this file |

## How to reproduce

### 1. Environment

- Official **Mininet 2.3.0 VM** (Ubuntu 20.04, Python 3.8) in VirtualBox.
  Mininet, Open vSwitch and iperf3 are preinstalled.
- **Ryu** (installed for the normal user; the newest eventlet breaks
  Ryu 4.34, so pin it):
  ```bash
  pip3 install --user ryu==4.34 eventlet==0.30.2
  pip3 install --user matplotlib
  ```
- Clone the repo and work from its root folder:
  ```bash
  git clone https://github.com/nherciu7/SDN-Steering.git
  cd SDN-Steering
  ```

### 2. One run

```bash
sudo python3 measurement/run_test.py --mode static --bulk 1 --rep 1 --duration 30
```
- `--mode static|reactive`, `--bulk 0|1` (1 = 5 Mbit/s UDP from h3),
  `--rep` = repetition number, `--duration` in seconds (default 30).
- It cleans Mininet (`mn -c`), starts Ryu in reactive mode, builds the
  network, makes h1 and h2 ping srv every 0.2 s (and h3 send iperf3 load if
  `--bulk 1`), then stops everything. There is no warm-up traffic: the first
  ping measures the first-packet delay.

### 3. The whole midterm matrix (about 10 minutes)

```bash
bash measurement/run_all.sh        # 12 runs, then parser and plots
```
Or only the analysis (no sudo needed):
```bash
python3 measurement/parse_results.py
python3 measurement/plot_results.py
```

### 4. Where the output goes

| Path | Content |
|---|---|
| `results/raw/<mode>_bulk<b>_rep<r>/` | `ping_h1.txt`, `ping_h2.txt`, `iperf.json` (bulk=1), `controller.log` (reactive). Not in git, regenerate with the scripts. |
| `results/summary.csv` | one row per run and host: RTT avg/min/max, loss %, first ping, first-packet delay, throughput |
| `results/plots/` | `rtt.png`, `first_packet_delay.png`, `throughput.png` |

KPIs: **first-packet delay** = first ping RTT − median RTT of the other
pings. **Throughput** = UDP rate received by srv (from iperf3).
Plots show the average over the 3 repetitions, with min/max error bars.

## Midterm experiment

**2 modes** (static, reactive) × **2 loads** (none, 5 Mbit/s UDP h3 → srv) ×
**3 repetitions** = 12 runs of 30 s. The 5 Mbit/s load was chosen after
8 Mbit/s overloaded the shaped 10 Mbit/s link in the VM.

Results (average over the 3 runs, h1 and h2 together):

| Mode | Load | RTT avg (ms) | RTT min (ms) | Loss | First-packet delay (ms) | Throughput (Mbit/s) |
|---|---|---|---|---|---|---|
| static | none | 35.0 | 26.3 | 0 % | −3.9 | — |
| static | 5 Mbit/s | 34.9 | 25.2 | 0 % | (not meaningful) | 5.00 |
| reactive | none | 31.3 | 25.6 | 0 % | **+5.5** | — |
| reactive | 5 Mbit/s | 46.0 | 25.1 | 0 % | (not meaningful) | 5.00 |

- In reactive mode the first packet waits ≈ 5.5 ms for the controller; in
  static mode there is no extra wait (≈ 0 within the VM's jitter).
- Minimum RTT ≈ 25 ms in all cases (expected 24 ms): same path, same delay.
- No loss, and the full 5 Mbit/s load gets through in both modes.
- Under load, reactive's average RTT was higher, but it varied a lot
  between runs (one run had spikes up to 534 ms), so with 3 runs we do not
  treat it as a real difference.
- First-packet delay is reported only without load: with load, the queue
  fills after the first ping, so "first minus the rest" is meaningless.

## After the midterm

Failover mode (`controller/failover_app.py`), link failure during a run
(`topology/link_failure.sh`), and the failover-time KPI.
