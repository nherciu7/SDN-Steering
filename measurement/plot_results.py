#!/usr/bin/env python3
"""Bar charts from results/summary.csv. Runs WITHOUT sudo:
    python3 measurement/plot_results.py

For every (mode, bulk) group:
  - per repetition we first average h1 and h2 (one value per run),
  - the bar is the average over the repetitions,
  - the error bar goes from the min to the max repetition.
Output: results/plots/rtt.png, first_packet_delay.png, throughput.png
"""
import csv
import os

import matplotlib
matplotlib.use('Agg')  # no display in the VM, just write PNG files
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(REPO, 'results', 'summary.csv')
PLOTS = os.path.join(REPO, 'results', 'plots')
MODES = ['static', 'reactive']
BULK_LABEL = {0: 'no bulk load', 1: 'bulk 5 Mbit/s'}
BULK_COLOR = {0: '#4C78A8', 1: '#F58518'}  # blue / orange


def per_run_values(rows, column, mode, bulk):
    """One value per repetition (average of h1 and h2) for one group."""
    by_rep = {}
    for r in rows:
        if r['mode'] == mode and int(r['bulk']) == bulk and r[column] != '':
            by_rep.setdefault(r['rep'], []).append(float(r[column]))
    return [sum(v) / len(v) for v in by_rep.values()]


def bar_chart(rows, column, ylabel, title, filename, bulks=(0, 1)):
    fig, ax = plt.subplots(figsize=(6, 4))
    width = 0.35
    labeled = set()  # put each bulk level in the legend only once
    for i, bulk in enumerate(bulks):
        for j, mode in enumerate(MODES):
            vals = per_run_values(rows, column, mode, bulk)
            if not vals:
                continue  # this group has not been measured yet
            avg = sum(vals) / len(vals)
            x = j + (i - (len(bulks) - 1) / 2) * width  # bars side by side per mode
            ax.bar(x, avg, width * 0.9, color=BULK_COLOR[bulk],
                   label=None if bulk in labeled else BULK_LABEL[bulk],
                   # max(0, ...) avoids a tiny negative value from float rounding
                   yerr=[[max(0, avg - min(vals))], [max(0, max(vals) - avg)]], capsize=4)
            labeled.add(bulk)
            # write the average just above the top of the error bar
            ax.text(x, max(vals), '%.2f\n' % avg, ha='center', va='bottom', fontsize=8)
    ax.set_xlim(-0.6, len(MODES) - 0.4)  # keep room for every mode, even if not measured yet
    ax.set_xticks(range(len(MODES)))
    ax.set_xticklabels(MODES)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(top=ax.get_ylim()[1] * 1.25)  # headroom for labels and legend
    ax.legend(loc='upper right')
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS, filename), dpi=120)
    plt.close(fig)
    print('Saved', os.path.join(PLOTS, filename))


def main():
    rows = list(csv.DictReader(open(CSV)))
    os.makedirs(PLOTS, exist_ok=True)
    bar_chart(rows, 'rtt_avg', 'RTT (ms)', 'Average RTT h1/h2 -> srv', 'rtt.png')
    # First-packet delay only without load: under bulk traffic the queue
    # fills after ping #1, so "first minus the rest" is not meaningful.
    bar_chart(rows, 'first_packet_delay_ms', 'First-packet delay (ms)',
              'First ping RTT minus median RTT (bulk=0 only)',
              'first_packet_delay.png', bulks=(0,))
    # Throughput only exists when there is bulk traffic.
    bar_chart(rows, 'throughput_mbps', 'Throughput (Mbit/s)',
              'iperf3 UDP throughput h3 -> srv', 'throughput.png', bulks=(1,))


if __name__ == '__main__':
    main()
