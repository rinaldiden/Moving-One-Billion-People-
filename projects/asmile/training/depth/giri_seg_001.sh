#!/bin/bash
# un tratto a 15 fps: stadio A fluido -> maestro stuff (bordi) -> postprocess famiglie -> video fluido VFMODE=v10.   uso: giri_seg_001.sh NOME SESSIONE FRAME_A FRAME_B
cd "$(dirname "$0")"
N=$1; S=$2; A=$3; B=$4; PY=~/.asmile_depth_venv/bin/python; O=out_20261113_giri
export OMP_NUM_THREADS=1 VFA_OUT=$O/A_$N VF_OUT_A=$O/A_$N VF_OUT=$O/video_$N VF_STUFF=$O/stuff_$N.npz STUFF_OUT=$O VFMODE=v10
mkdir -p $O/A_$N $O/video_$N
nice -n 10 $PY depth_fluido_a_001.py ${S#session_} $A $B > $O/A_$N.log 2>&1 || exit 1
nice -n 10 $PY bordi_stuff_001.py $S 3 > $O/stuff_$N.log 2>&1
echo "stuff ok" >> $O/A_$N.log
cd ../..
for k in 1 2 3; do python3 training/segmentation/seg_postprocess_v2.py $S _fluido > training/depth/$O/pp_$N.log 2>&1 && break; sleep 5; done
cd training/depth
nice -n 10 $PY video_fluido_001.py $S >> $O/video_$N.log 2>&1
echo "DONE" > $O/video_$N/DONE
