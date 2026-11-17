import sys,os,json,subprocess,numpy as np,cv2,pandas as pd
ROOT='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile'
S=os.path.dirname(os.path.abspath(__file__))
c=json.load(open(ROOT+'/logger/depth/calib_asmile-001.json'))
K1=np.array(c['K_left']);d1=np.array(c['dist_left']);K2=np.array(c['K_right']);d2=np.array(c['dist_right'])
R=np.array(c['R']);T=np.array(c['T']);sz=tuple(c['size'])
# order RL: file *_right = fisica sinistra; calib K_left corrisponde a? uso stereo_common come riferimento di mappatura
sys.path.insert(0,ROOT+'/logger/depth')
from stereo_common import Calib
cc=Calib.load(ROOT+'/logger/depth/calib_asmile-001.json');r=cc.rectify()
print('f',r['focal_px'],'P1',r['P1'][0,:3],'keys',list(r.keys()))
def frames(path,want):
    p=subprocess.Popen(['ffmpeg','-v','error','-framerate','15','-i',path,'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
    i=0;W,H=1280,800
    while True:
        b=p.stdout.read(W*H)
        if len(b)<W*H:break
        if i in want: yield i,np.frombuffer(b,np.uint8).reshape(H,W)
        i+=1
        if i>max(want):p.kill();break
sess=sys.argv[1];want=set(int(x) for x in sys.argv[2:])
L=ROOT+f'/asmile-loggers/asmile-001/session_20261109_{sess}_right.h264';Rr=ROOT+f'/asmile-loggers/asmile-001/session_20261109_{sess}_left.h264'
for (i,a),(j,b) in zip(frames(L,want),frames(Rr,want)):
    A=cv2.remap(a,r['m1x'],r['m1y'],cv2.INTER_LINEAR);B=cv2.remap(b,r['m2x'],r['m2y'],cv2.INTER_LINEAR)
    cv2.imwrite(f'{S}/{sess}_{i}_L.png',A);cv2.imwrite(f'{S}/{sess}_{i}_R.png',B)
