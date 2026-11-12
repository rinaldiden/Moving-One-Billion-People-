#!/bin/bash
cd "$(dirname "$0")"
go(){ VFA_OUT=out_20261112_v12_A/$4 OMP_NUM_THREADS=1 ~/.asmile_depth_venv/bin/python depth_fluido_a_001.py $1 $2 $3 > out_20261112_v12_A_$4.log 2>&1; }
mkdir -p out_20261112_v12_A
go 20261109_094146 1875 2325 a & go 20261109_094146 2325 2775 b & go 20261109_094146 2775 3225 c & wait
go 20261109_093909 0 140 d & go 20261109_093909 140 280 e & go 20261109_093909 280 406 f & wait
echo DONE > out_20261112_v12_A/DONE
