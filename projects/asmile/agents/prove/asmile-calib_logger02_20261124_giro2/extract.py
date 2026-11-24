"""Match SIFT L-R grezzi (nessun dy statistico). uso: python3 extract.py <W> [step]. gate largo +-40 px rispetto alla rettifica di v4 (solo per scartare falsi match)."""
import os,sys,pickle,json,collections,subprocess,numpy as np,cv2
from multiprocessing import Pool
V4=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_v4_20261124.json')
def region(t):
    if 130<=t<330 or 390<=t<715: return 'M'
    if 330<=t<360 or 720<=t<830: return 'F'
    return None
def rectfun():
    c=json.load(open(V4));K1=np.array(c['K_left']);K2=np.array(c['K_right']);d=np.array(c['dist_left']);r=cv2.stereoRectify(K1,d,K2,d,tuple(c['size']),np.array(c['R']),np.array(c['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    f=lambda p,K,R_:cv2.undistortPoints(p.reshape(-1,1,2).astype(np.float64),K,d,R=R_,P=r[2]).reshape(-1,2);return lambda a,b:(f(a,K1,r[0]),f(b,K2,r[1]))
def decode(clip,idx):
    idx=sorted(set(idx));expr='+'.join(f'eq(n\\,{i})' for i in idx)
    p=subprocess.run(['ffmpeg','-v','error','-i',clip,'-vf',f"select='{expr}'",'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    v=np.frombuffer(p.stdout,np.uint8);n=len(v)//(1280*800);assert n==len(idx),(clip,n,len(idx));return dict(zip(idx,v.reshape(n,800,1280)))
def work(args):
    ca,cb,items=args;rect=rectfun();A=decode(ca,[i['a'] for i in items]);B=decode(cb,[i['b'] for i in items])
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher();res=[]
    for it in items:
        ia=A[it['a']];ib=B[it['b']];m=np.zeros_like(ia);m[8:-8,8:-8]=255
        ka,da=sift.detectAndCompute(ia,m);kb,db=sift.detectAndCompute(ib,m)
        if da is None or db is None or len(ka)<30 or len(kb)<30: continue
        ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1);a=[];b=[]
        for q in ab:
            if len(q)==2 and q[0].distance<0.75*q[1].distance and ba[q[0].trainIdx][0].trainIdx==q[0].queryIdx: a.append(ka[q[0].queryIdx].pt);b.append(kb[q[0].trainIdx].pt)
        a=np.array(a);b=np.array(b)
        if len(a)<25: continue
        qa,qb=rect(a,b);ok=(abs(qa[:,1]-qb[:,1])<40)&(qa[:,0]-qb[:,0]>1)&(qa[:,0]-qb[:,0]<500)
        if ok.sum()>=25: res.append(dict(reg=it['reg'],t=it['t'],n_raw=len(a),a=a[ok],b=b[ok]))
    return res
if __name__=='__main__':
    W=os.path.abspath(sys.argv[1]);step=int(sys.argv[2]) if len(sys.argv)>2 else 12;P=pickle.load(open(W+'/pairs.pkl','rb'));g=collections.OrderedDict();n=0
    for k,(a,b,dt) in enumerate(P):
        t=a[0]/1e6;r=region(t)
        if r is None or k%step: continue
        g.setdefault((a[1],b[1]),[]).append(dict(a=a[2],b=b[2],t=t,reg=r));n+=1
    print('coppie scelte',n,'job',len(g),flush=True);jobs=[(ca,cb,v) for (ca,cb),v in g.items()]
    with Pool(2) as pool: out=[x for o in pool.imap_unordered(work,jobs) for x in o]
    out.sort(key=lambda r:r['t']);print('con match',len(out),'punti',sum(len(o['a']) for o in out),'raw>gate scartati',sum(o['n_raw']-len(o['a']) for o in out))
    pickle.dump(out,open(W+'/lr_matches.pkl','wb'))
