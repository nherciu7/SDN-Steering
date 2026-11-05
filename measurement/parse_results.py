#!/usr/bin/env python3
"""Read every run folder in results/raw/ and write results/summary.csv.
Runs WITHOUT sudo:  python3 measurement/parse_results.py

One row per run and per host (h1, h2). Columns:
  mode, bulk, rep, host, rtt_avg, rtt_min, rtt_max, loss_pct,
  first_ping_ms, first_packet_delay_ms, throughput_mbps
"""
import csv
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(REPO, 'results', 'raw')
OUT = os.path.join(REPO, 'results', 'summary.csv')
COLUMNS = ['mode', 'bulk', 'rep', 'host', 'rtt_avg', 'rtt_min', 'rtt_max', 'loss_pct',
           'first_ping_ms', 'first_packet_delay_ms', 'throughput_mbps']


def parse_ping(path):
    """Return (dict of seq -> rtt in ms, loss in %) from a ping output file."""
    rtts, loss = {}, ''
    for line in open(path):
        # e.g. "64 bytes from 10.0.0.100: icmp_seq=1 ttl=64 time=12.3 ms"
        m = re.search(r'icmp_seq=(\d+) .*time=([\d.]+) ms', line)
        if m:
            rtts[int(m.group(1))] = float(m.group(2))
        # e.g. "150 packets transmitted, 150 received, 0% packet loss, ..."
        m = re.search(r'([\d.]+)% packet loss', line)
        if m:
            loss = float(m.group(1))
    return rtts, loss


def parse_iperf(path):
    """Received UDP throughput in Mbit/s from iperf3 -J output ('' if missing)."""
    if not os.path.exists(path):
        return ''
    try:
        end = json.load(open(path))['end']
    except (ValueError, KeyError):
        return ''  # iperf3 failed, file has no valid result
    if 'sum_received' in end:  # newer iperf3 versions
        return round(end['sum_received']['bits_per_second'] / 1e6, 3)
    # iperf3 3.7 (our VM): 'sum' = sending rate + lost_percent seen by the server
    s = end['sum']
    return round(s['bits_per_second'] * (1 - s['lost_percent'] / 100) / 1e6, 3)


def main():
    rows = []
    for name in sorted(os.listdir(RAW)):
        m = re.match(r'(\w+)_bulk(\d)_rep(\d+)$', name)
        if not m:
            continue  # skip .gitkeep and anything else
        mode, bulk, rep = m.group(1), int(m.group(2)), int(m.group(3))
        run_dir = os.path.join(RAW, name)
        tput = parse_iperf(os.path.join(run_dir, 'iperf.json')) if bulk == 1 else ''

        for host in ('h1', 'h2'):
            path = os.path.join(run_dir, 'ping_%s.txt' % host)
            if not os.path.exists(path):
                continue
            rtts, loss = parse_ping(path)
            row = {'mode': mode, 'bulk': bulk, 'rep': rep, 'host': host,
                   'loss_pct': loss, 'throughput_mbps': tput}
            if rtts:
                values = list(rtts.values())
                row['rtt_avg'] = round(sum(values) / len(values), 3)
                row['rtt_min'] = min(values)
                row['rtt_max'] = max(values)
            # First-packet delay = RTT of ping #1 minus the average of the others.
            # If ping #1 got no reply we leave both fields empty.
            if 1 in rtts and len(rtts) > 1:
                rest = [v for seq, v in rtts.items() if seq != 1]
                row['first_ping_ms'] = rtts[1]
                row['first_packet_delay_ms'] = round(rtts[1] - sum(rest) / len(rest), 3)
            rows.append(row)

    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, restval='')
        w.writeheader()
        w.writerows(rows)
    print('Wrote %d rows to %s' % (len(rows), OUT))


if __name__ == '__main__':
    main()
