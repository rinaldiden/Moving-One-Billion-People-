#!/bin/bash
# SAM 3 sui giri 13/11 di #001: un solo processo (MPS), nice 10. Prima le frenate a 15 fps, poi 1 Hz su tutto il giro, poi i tratti controsole.
cd "$(dirname "$0")/../.."
PY=~/.asmile_depth_venv/bin/python; L=training/depth/out_20261113_giri; SG=asmile-loggers/_seg_sam3
S1=session_20261113_150337; S2=session_20261113_151400
run(){ OMP_NUM_THREADS=2 nice -n 10 $PY training/segmentation/seg_sam3_001.py "$@"; }
run $S1 --list $L/lista_15fps_frenata1.csv --out $SG/${S1}_001_fluido
run $S1 --list $L/lista_15fps_frenata2_monovolume.csv --out $SG/${S1}_001_fluido
run $S1 --list $L/lista_1hz_${S1:8}.csv --out $SG/${S1}_001
run $S2 --list $L/lista_1hz_${S2:8}.csv --out $SG/${S2}_001
run $S1 --list $L/lista_15fps_controsole_a.csv --out $SG/${S1}_001_fluido
run $S1 --list $L/lista_15fps_controsole_b.csv --out $SG/${S1}_001_fluido
run $S2 --list $L/lista_15fps_controsole_c.csv --out $SG/${S2}_001_fluido
echo DONE > $L/SAM_DONE
