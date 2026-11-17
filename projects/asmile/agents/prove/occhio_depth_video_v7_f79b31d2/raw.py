import sys, json, cv2, numpy as np, pickle
sys.path.insert(0,'/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth')
import depth_seg_001 as D
B='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth/'
T7=pickle.load(open(B+'out_20261112_v7/tracks_20261109_094146.pkl','rb'))
samp=json.load(open('samp30.json')); need={c[1]:c for c in samp}
for f in (3171,3173,3175): need.setdefault(f,None)
sess='session_20261109_094146'; rc=D.Rect()
import os; os.makedirs('raw',exist_ok=True)
for i,Lr in enumerate(D.gray_frames(D.os.path.join(D.LOGS,sess+'_right.h264'))):
    if i>max(need): break
    if i not in need: continue
    L=cv2.remap(Lr,rc.r['m1x'],rc.r['m1y'],cv2.INTER_LINEAR); img=cv2.convertScaleAbs(cv2.cvtColor(L,cv2.COLOR_GRAY2BGR),alpha=1.15,beta=8)
    n=T7['frames'].index(i); fid=T7['cs'][n]['first']['arc']
    r=next((q for q in T7['per'][n] if q['id']==fid),None)
    if r:
        b=r['box']; cv2.rectangle(img,(b[0],b[1]),(b[2],b[3]),(0,255,255),3); cv2.putText(img,f"f{i} {r['fam']} {r['Z']:.1f}m",(20,40),cv2.FONT_HERSHEY_DUPLEX,1.1,(0,255,255),2)
    cv2.imwrite(f'raw/f{i}.jpg',img,[cv2.IMWRITE_JPEG_QUALITY,85])
