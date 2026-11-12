#!/bin/bash
# Test sintetico giro 10: toppe a 1.5, 1.7, 1.9 m (devono essere OSTACOLO) e 2.2 m (ESCLUSA) da terra. VFA_SYNTH="Z,h_da_terra,spessore,larghezza,X" nello stadio A reale (fotogrammi 2284-2300, corridoio libero).
cd "$(dirname "$0")"; PY=~/.asmile_depth_venv/bin/python
run(){ VFA_OUT=out_20261112_v10_synth_$2 VFA_SYNTH=$1 $PY depth_fluido_a_001.py 20261109_094146 2284 2300 > out_20261112_v10_synth_$2.log 2>&1; VF_NOSTUFF=1 VF_OUT_A=out_20261112_v10_synth_$2 VF_OUT=out_20261112_v10_synth_$2/B python3 video_fluido_001.py 20261109_094146 --stats-only; }
run 6.0,1.5,0.4,0.8,0.0 h15_z6 & run 6.0,1.7,0.4,0.8,0.0 h17_z6 & run 6.0,1.9,0.4,0.8,0.0 h19_z6 & wait
run 8.0,2.2,0.5,0.8,0.0 h22_z8 & run 8.0,1.9,0.5,0.8,0.0 h19_z8 & wait
