"""Passo 4: fogli contatto per cercare a occhio griglie a terra/catene/dossi. Campionamento deterministico."""
import glob, subprocess, os, numpy as np, cv2
A = "asmile-loggers"; O = "agents/rapporti/img"
def grab(v, n, crop):
    p = subprocess.run(["ffmpeg","-v","error","-framerate","15","-i",v,"-vf",f"select=eq(n\\,{n})"+(",crop=1280:800:0:0" if crop else ""),"-frames:v","1","-f","image2pipe","-vcodec","png","-"],capture_output=True)
    return cv2.imdecode(np.frombuffer(p.stdout,np.uint8),1) if p.stdout else None
def sheet(items, name, crop):
    tiles=[]
    for v,n in items:
        im=grab(v,n,crop)
        if im is None: im=np.zeros((800,1280,3),np.uint8)
        im=cv2.resize(im,(256,160)); cv2.putText(im,f"{os.path.basename(v)[5:24]}:{n}",(2,12),0,0.35,(0,255,255),1); tiles.append(im)
    while len(tiles)%5: tiles.append(np.zeros((160,256,3),np.uint8))
    cv2.imwrite(f"{O}/{name}.jpg",np.vstack([np.hstack(tiles[i:i+5]) for i in range(0,len(tiles),5)]),[cv2.IMWRITE_JPEG_QUALITY,85])
lg=sorted(glob.glob(f"{A}/asmile-logger/clip_*.h264"))[::4]
for k in range(0,len(lg),20): sheet([(v,200) for v in lg[k:k+20]],f"L1classi_ricerca_logger_{k//20}",True)
s1=sorted(glob.glob(f"{A}/asmile-001/session_*_left.h264"))
it=[(v,n) for v in s1 for n in (1500,4000,7000)]
for k in range(0,len(it),20): sheet(it[k:k+20],f"L1classi_ricerca_001_{k//20}",False)
print(len(lg),len(it))
