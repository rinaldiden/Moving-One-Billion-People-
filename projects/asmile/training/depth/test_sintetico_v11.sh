#!/bin/bash
# Test sintetico giro 11: SBARRA SOSPESA (spessore SP m (0.15 NON viene rilevata: lo stadio A scarta blob alti < 0.30 m; si prova 0.35), larga 1.4 m, X=0) a 1.0 e 1.7 m da terra, a Z = 3.0, 4.0, 4.5 m (entro frena_entro ~6.3 m a 3.5 m/s).
# VFA_SYNTH="Z,h_da_terra,spessore,larghezza,X" nello stadio A reale (fotogrammi 2284-2300, corridoio libero). Poi stadio B v11 --stats-only e lettura di azione/ritardo.
cd "$(dirname "$0")"; PY=~/.asmile_depth_venv/bin/python
run(){ VFA_OUT=out_20261112_v11_synth35_$2 VFA_SYNTH=$1 $PY depth_fluido_a_001.py 20261109_094146 2284 2300 > out_20261112_v11_synth35_$2.log 2>&1; VF_NOSTUFF=1 VF_OUT_A=out_20261112_v11_synth35_$2 VF_OUT=out_20261112_v11_synth35_$2/B python3 video_fluido_001.py 20261109_094146 --stats-only; }
run 4.0,1.0,0.35,1.4,0.0 s10_z4 & run 4.0,1.7,0.35,1.4,0.0 s17_z4 & run 3.0,1.0,0.35,1.4,0.0 s10_z3 & wait
run 3.0,1.7,0.35,1.4,0.0 s17_z3 & run 4.5,1.0,0.35,1.4,0.0 s10_z45 & run 4.5,1.7,0.35,1.4,0.0 s17_z45 & wait
