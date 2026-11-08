#!/bin/bash
# Aspetta che Meta approvi l'accesso a facebook/sam3, scarica sam3.pt in ~/.asmile_seg_models e
# rigira la segmentazione della sessione indicata con SAM 3 come maestro (2026-11-08).
SESS="${1:-asmile-loggers/asmile-001/session_20261107_161628}"
PY=~/.asmile_depth_venv/bin/python
cd "$(dirname "$0")/../.."
for i in $(seq 1 288); do            # fino a 48 h, un controllo ogni 10 min
  if $PY -c "from huggingface_hub import hf_hub_download as d; import shutil,os; p=d('facebook/sam3','sam3.pt'); shutil.copy(p, os.path.expanduser('~/.asmile_seg_models/sam3.pt'))" 2>/dev/null; then
    echo "SAM3_OK $(date)"
    $PY training/segmentation/seg_teacher_student.py "$SESS" --out asmile-loggers/_seg_sam3 2>&1 | tail -20
    exit 0
  fi
  sleep 600
done
echo "SAM3_TIMEOUT"
