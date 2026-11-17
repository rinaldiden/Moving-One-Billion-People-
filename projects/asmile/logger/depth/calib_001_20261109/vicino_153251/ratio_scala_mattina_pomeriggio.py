import sys,json,pickle,numpy as np
D='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_001_20261109/vicino_153251'
sys.argv=['x','.','pm','/dev/null'];sys.path.insert(0,D)
import fit_joint_pm as F
j=json.load(open('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json'))['fit_params']
q=[*j['rx_ry_rz_deg'],j['fL'],j['fR'],j['k1_L'],j['k2'],j['k1_R'],j['k2'],j['dcx_right_px'],j['dcy_right_px'],0,0,0,0]
p=np.array(q);cache=F.rect(p);B=0.2
AM=pickle.load(open('boards_am.pkl','rb'))
print('chi = Zs/Zp (indipendente da f e dal metro); Zs/metro')
for k,fr in AM.items():
    if not fr:continue
    d,tz,dy,tx=F.board_stats(p,dict(frames=fr),cache);Zs=p[3]*B/d
    print('MATTINA %4.0f m  Zs=%.3f  Zp(unit)=%.2f sq  Zs/(tz)=%.5f  Zs/metro=%+.2f%%  dy=%+.2f'%(F.M[k]['Z'],Zs,tz,Zs/tz,100*(Zs/F.M[k]['Z']-1),dy))
for r in F.BR:
    if r['pos']!='C':continue
    d,tz,dy,tx=F.board_stats(p,r,cache);Zs=p[3]*B/d
    print('POMER.  %4.0f m  Zs=%.3f  Zp(unit)=%.2f sq  Zs/(tz)=%.5f  Zs/metro=%+.2f%%  dy=%+.2f'%(r['nom'],Zs,tz,Zs/tz,100*(Zs/r['nom']-1),dy))
