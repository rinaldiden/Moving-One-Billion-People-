import sys,os,json,subprocess,numpy as np,cv2
ROOT='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile'
S=ROOT+'/agents/prove/occhio_depth_video_v4_6b153403'
sys.path.insert(0,ROOT+'/logger/depth')
from stereo_common import Calib
r=Calib.load(ROOT+'/logger/depth/calib_asmile-001.json').rectify()
def frames(path,want):
    p=subprocess.Popen(['ffmpeg','-v','error','-framerate','15','-i',path,'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
    i=0
    while True:
        b=p.stdout.read(1280*800)
        if len(b)<1280*800:break
        if i in want: yield i,np.frombuffer(b,np.uint8).reshape(800,1280)
        i+=1
        if i>max(want):p.kill();break
sess=sys.argv[1];mode=sys.argv[2];want=set(int(x) for x in sys.argv[3:])
base=ROOT+f'/asmile-loggers/asmile-001/session_20261109_{sess}'
os.makedirs(S+'/'+mode,exist_ok=True)
for (i,a),(j,b) in zip(frames(base+'_right.h264',want),frames(base+'_left.h264',want)):
    A=cv2.remap(a,r['m1x'],r['m1y'],cv2.INTER_LINEAR);B=cv2.remap(b,r['m2x'],r['m2y'],cv2.INTER_LINEAR)
    if mode=='thumb':
        t=cv2.resize(A,(320,200));cv2.putText(t,str(i),(4,24),cv2.FONT_HERSHEY_SIMPLEX,0.8,255,2);cv2.imwrite(f'{S}/thumb/{sess}_{i:05d}.png',t)
    else:
        cv2.imwrite(f'{S}/{mode}/{sess}_{i}_L.png',A);cv2.imwrite(f'{S}/{mode}/{sess}_{i}_R.png',B)
