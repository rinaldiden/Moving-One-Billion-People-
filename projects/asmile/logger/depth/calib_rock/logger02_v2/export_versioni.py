"""Produce le DUE versioni del candidato: 720 (come registrato) e 800 (derivata: cy +40, f e cx invariati) - la 800 va VERIFICATA sul primo giro a 800.
uso: python3 export_versioni.py calib_auto.json prefisso   -> prefisso_720.json, prefisso_800.json"""
import sys,json
c=json.load(open(sys.argv[1]));pre=sys.argv[2]
if c['size'][1]==720: c720=c
else: c720=json.loads(json.dumps(c));[c720[k][1].__setitem__(2,c720[k][1][2]-40) for k in('K_left','K_right')];c720['size']=[1280,720]
c800=json.loads(json.dumps(c720))
for k in('K_left','K_right'): c800[k][1][2]+=40
c800['size']=[1280,800];c800['stato']=(c720.get('stato','')+' | versione 800 DERIVATA (cy+40) da quella a 720: DA VERIFICARE sul primo giro a 1280x800')
c720['risoluzione']='1280x720';c800['risoluzione']='1280x800 (derivata)'
json.dump(c720,open(pre+'_720.json','w'),indent=1);json.dump(c800,open(pre+'_800.json','w'),indent=1);print('scritti',pre+'_720.json',pre+'_800.json')
