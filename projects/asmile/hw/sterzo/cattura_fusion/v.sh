S=$(cd "$(dirname "$0")" && pwd)
cd ~/progetti/doppio/fusion
sed "s/EYE/($1)/; s/TGT/($2)/; s/EXT/$3/" $S/view.py > $S/view_.py
python3 bridge/zbridge.py script $S/view_.py >/dev/null
python3 bridge/zbridge.py script $S/proj.py | sed 's/=> return: //' > $S/../img/fusion_$4.json
python3 bridge/zbridge.py shot $S/../img/fusion_$4.png 1084 680
