#!/usr/bin/env python3
"""One measurement run (part C).

Usage (needs root, Mininet requires it):
    sudo python3 measurement/run_test.py --mode static --bulk 1 --rep 1 --duration 30

What it does:
  1. cleans Mininet leftovers (mn -c)
  2. reactive mode: starts the Ryu controller (log -> controller.log)
  3. builds the network with create_net(mode) from topology/topo.py
  4. starts an iperf3 server on srv
  5. h1 and h2 ping srv every 0.2 s for <duration> seconds
     (bulk=1: at the same time h3 sends 5 Mbit/s UDP to srv with iperf3)
  6. stops everything and cleans up again
All output goes to results/raw/<mode>_bulk<b>_rep<r>/.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

# Paths: this file lives in measurement/, the repo root is one level up.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'topology'))
from topo import create_net  # provided by part A (topology/topo.py)

SRV_IP = '10.0.0.100'
PING_INTERVAL = 0.2


def start_ryu(run_dir):
    """Start ryu-manager in the background, logging to controller.log.
    Ryu is installed for the normal user (not root), so we run it as the
    user who called sudo."""
    user = os.environ.get('SUDO_USER', 'mininet')
    ryu = shutil.which('ryu-manager') or os.path.expanduser('~%s/.local/bin/ryu-manager' % user)
    log = open(os.path.join(run_dir, 'controller.log'), 'w')
    cmd = ['sudo', '-u', user, ryu, os.path.join(REPO, 'controller', 'reactive_app.py')]
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(3)  # give Ryu time to open port 6653
    return proc


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['static', 'reactive'], required=True)
    p.add_argument('--bulk', type=int, choices=[0, 1], required=True)
    p.add_argument('--rep', type=int, required=True)
    p.add_argument('--duration', type=int, default=30)
    a = p.parse_args()

    if os.geteuid() != 0:
        sys.exit('Run with sudo: sudo python3 measurement/run_test.py ...')

    run_dir = os.path.join(REPO, 'results', 'raw', '%s_bulk%d_rep%d' % (a.mode, a.bulk, a.rep))
    os.makedirs(run_dir, exist_ok=True)
    print('*** Run %s_bulk%d_rep%d, %d s -> %s' % (a.mode, a.bulk, a.rep, a.duration, run_dir))

    # Clean leftovers from older runs (do this BEFORE Ryu: mn -c kills ryu-manager).
    subprocess.call(['mn', '-c'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ryu = start_ryu(run_dir) if a.mode == 'reactive' else None
    net = create_net(a.mode)
    if a.mode == 'reactive':
        net.waitConnected()  # wait until all switches talk to the controller

    h1, h2, h3, srv = net.get('h1', 'h2', 'h3', 'srv')

    # iperf3 server on srv (no network traffic yet, just listening).
    # Its output must go to DEVNULL: Mininet's popen otherwise uses a pipe
    # nobody reads, and the iperf3 client then hangs at the end of the test.
    iperf_srv = srv.popen(['iperf3', '-s'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    time.sleep(1)

    # NO warm-up traffic: the very first ping is our first-packet delay sample.
    count = int(a.duration / PING_INTERVAL)
    procs = []
    for h in (h1, h2):
        out = open(os.path.join(run_dir, 'ping_%s.txt' % h.name), 'w')
        procs.append(h.popen(['ping', '-i', str(PING_INTERVAL), '-c', str(count), SRV_IP],
                             stdout=out, stderr=subprocess.STDOUT))
    if a.bulk == 1:
        out = open(os.path.join(run_dir, 'iperf.json'), 'w')
        procs.append(h3.popen(['iperf3', '-c', SRV_IP, '-u', '-b', '5M',
                               '-t', str(a.duration), '-J'],
                              stdout=out, stderr=subprocess.STDOUT))

    # Wait for pings (and iperf3) to finish; kill anything stuck after a margin.
    for proc in procs:
        try:
            proc.wait(timeout=a.duration + 15)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Stop everything.
    iperf_srv.terminate()
    net.stop()
    if ryu:
        ryu.terminate()
        ryu.wait()
    subprocess.call(['mn', '-c'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Files were written by root; give them back to the normal user.
    user = os.environ.get('SUDO_USER')
    if user:
        subprocess.call(['chown', '-R', '%s:%s' % (user, user), run_dir])
    print('*** Done:', ', '.join(sorted(os.listdir(run_dir))))


if __name__ == '__main__':
    main()
