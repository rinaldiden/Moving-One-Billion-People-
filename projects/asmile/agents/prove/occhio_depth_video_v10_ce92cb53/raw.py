import sys, json, cv2, numpy as np, pickle, os
sys.path.insert(0,'/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth')
import depth_seg_001 as D
B='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth/out_20261112_v10/'
T=pickle.load(open(B+'tracks_20261109_094146.pkl','rb'))
need=sorted(set(json.load(open(sys.argv[1]))))
sess='session_20261109_094146'; rc=D.Rect(); os.makedirs('raw',exist_ok=True)
for i,Lr in enumerate(D.gray_frames(D.os.path.join(D.LOGS,sess+'_right.h264'))):
    if i>max(need): break
    if i not in need: continue
    L=cv2.remap(Lr,rc.r['m1x'],rc.r['m1y'],cv2.INTER_LINEAR); img=cv2.convertScaleAbs(cv2.cvtColor(L,cv2.COLOR_GRAY2BGR),alpha=1.15,beta=8)
    if i in T['frames']:
        n=T['frames'].index(i); c=T['cs'][n]; fid=c['first']['arc']
        r=next((q for q in T['per'][n] if q['id']==fid),None)
        t=f"f{i} v{c['v']:.1f}"
        if r and r['fam']!='bordo':
            b=r['box']; cv2.rectangle(img,(b[0],b[1]),(b[2],b[3]),(0,255,255),3); t+=f" 1o:{r['fam']} {r['Z']:.1f}m X{r['X']:.1f}"
        if r and r['fam']=='bordo': t+=f" 1o:BORDO"
        if c['act']: t+=f" {c['act']['act']}"
        a=c['bord']['alarm']
        if a: t+=f" ALLARME {a['side']} Z{a['Z']:.1f} clear{a['clear']:.2f}"
        fm=lambda x:'-' if x is None else f'{x:.2f}'; t2=f"mL {fm(c['bord']['clearL'])} mR {fm(c['bord']['clearR'])} marg {fm(c['bord']['margin'])}"
        cv2.putText(img,t,(10,35),cv2.FONT_HERSHEY_DUPLEX,0.9,(0,255,255),2); cv2.putText(img,t2,(10,75),cv2.FONT_HERSHEY_DUPLEX,0.9,(0,255,0),2)
    cv2.imwrite(f'raw/f{i}.jpg',img,[cv2.IMWRITE_JPEG_QUALITY,85])
