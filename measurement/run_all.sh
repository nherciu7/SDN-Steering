#!/bin/bash
# Full midterm matrix: 2 modes x 2 load levels x 3 repetitions = 12 runs,
# then parse the logs and draw the plots.
# Usage (from the repo root):  bash measurement/run_all.sh [duration]
DURATION=${1:-30}
cd "$(dirname "$0")/.." || exit 1

for mode in static reactive; do
  for bulk in 0 1; do
    for rep in 1 2 3; do
      sudo python3 measurement/run_test.py --mode $mode --bulk $bulk --rep $rep --duration $DURATION
    done
  done
done

# These two do not need root.
python3 measurement/parse_results.py
python3 measurement/plot_results.py
