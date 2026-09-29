#!/bin/bash
# Next Gen Stats and PFR advanced stats for the Redzone Desk football stats (rerun weekly; nflverse updates them in-season).
cd "$(dirname "$0")/../../data"; B=https://github.com/nflverse/nflverse-data/releases/download
for k in receiving rushing passing; do curl -sfL -o ngs_$k.parquet $B/nextgen_stats/ngs_$k.parquet || echo "WARN ngs_$k"; done
for y in 2022 2023 2024 2025 2026; do for k in pass rush rec def; do curl -sfL -o advstats_week_${k}_$y.csv $B/pfr_advstats/advstats_week_${k}_$y.csv || echo "WARN $k $y"; done; done
curl -sfL -o ftn_charting_2026.parquet $B/ftn_charting/ftn_charting_2026.parquet || echo "WARN ftn"
echo stats ready
