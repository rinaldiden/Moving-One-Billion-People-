#!/bin/bash
# Test sintetico giro 9: toppa di disparita' (larghezza 0.8 m, X=0) inserita nella mappa SGBM del fotogramma 2292-2300 (094146, corridoio libero, rettilineo) dentro lo stadio A reale.
# VFA_SYNTH="Z,h_da_terra,spessore,larghezza,X". Uso: esegue con il venv depth, poi stadio B (VF_OUT_A/VF_OUT) e stampa il primo ostacolo.
cd "$(dirname "$0")"; PY=~/.asmile_depth_venv/bin/python
run(){ VFA_OUT=out_20261112_v9_synth_$2 VFA_SYNTH=$1 $PY depth_fluido_a_001.py 20261109_094146 2292 2300 > out_20261112_v9_synth_$2.log 2>&1; VF_OUT_A=out_20261112_v9_synth_$2 VF_OUT=out_20261112_v9_synth_$2/B python3 video_fluido_001.py 20261109_094146 --stats-only; }
run 3.0,1.0,0.4,0.8,0.0 h10_z3 & run 4.0,1.2,0.5,0.8,0.0 h12_z4 & run 4.0,1.5,0.5,0.8,0.0 h15_z4 & wait
run 6.0,2.0,0.6,0.8,0.0 h20_z6b
