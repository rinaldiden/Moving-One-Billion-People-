#!/bin/zsh
# giro 3 giri 13/11: rigira i 5 tratti con video_fluido_001.py (v14). Uso: run_giri_v3.sh [--stats-only] [extra args]  (env VFMODE per il prima/dopo, VF_ROOT_OUT cartella uscita)
cd "$(dirname "$0")"
R=${VF_ROOT_OUT:-out_20261113_giri_v3}; A=out_20261113_giri
for t in frenata1:150337 controsole_a:150337 controsole_b:150337 frenata2_monovolume:150337 controsole_c:151400; do
  n=${t%%:*}; s=${t##*:}; mkdir -p $R/video_$n
  VF_OUT_A=$A/A_$n VF_STUFF=$A/stuff_$n.npz VF_OUT=$R/video_$n VF_NMDUMP=$R/nm_$n.csv OMP_NUM_THREADS=3 nice -n 10 python3 video_fluido_001.py session_20261113_$s "$@" > $R/pp_$n.log 2>&1
done
echo FINE > $R/FINE
