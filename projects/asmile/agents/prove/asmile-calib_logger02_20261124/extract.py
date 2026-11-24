"""Estrazione match L-R grezzi 24/11 (1280x800). uso: python3 extract.py <lavoro> [step]. Base: v3 con size 800 e cy+40."""
import os,sys,json,pickle,subprocess,collections,numpy as np,cv2
from multiprocessing import Pool
from sync import pairs,SESS
V3=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_v3_giro2_20261123.json')
def base800(out):
    c=json.load(open(V3));c['size']=[1280,800]
    for k in('K_left','K_right'): c[k][1][2]+=40
    c['nota_24_11']='v3 a 1280x800: cy+40 su entrambe (modo 800 parte dalla riga 0, 720 dalla 40). File di lavoro, non e un candidato.';json.dump(c,open(out,'w'),indent=1);return out
def rectfun(cal):
    c=json.load(open(cal));K1=np.array(c['K_left']);K2=np.array(c['K_right']);d1=np.array(c['dist_left']);d2=np.array(c['dist_right'])
    r=cv2.stereoRectify(K1,d1,K2,d2,tuple(c['size']),np.array(c['R']),np.array(c['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    f=lambda p,K,d,R_:cv2.undistortPoints(p.reshape(-1,1,2).astype(np.float64),K,d,R=R_,P=r[2]).reshape(-1,2)
    return lambda a,b:(f(a,K1,d1,r[0]),f(b,K2,d2,r[1]))
def decode(clip,idx):
    idx=sorted(set(idx));expr='+'.join(f'eq(n\\,{i})' for i in idx)
    p=subprocess.run(['ffmpeg','-v','error','-i',clip,'-vf',f"select='{expr}'",'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    W,H=1280,800;v=np.frombuffer(p.stdout,np.uint8);n=len(v)//(W*H);assert n==len(idx),(clip,n,len(idx));return dict(zip(idx,v.reshape(n,H,W)))
def work(args):
    cal,ca,cb,items=args;rect=rectfun(cal);A=decode(ca,[i['a'][1] for i in items]);B=decode(cb,[i['b'][1] for i in items])
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher();res=[]
    for it in items:
        ia=A[it['a'][1]];ib=B[it['b'][1]];m=np.zeros_like(ia);m[8:-8,8:-8]=255
        ka,da=sift.detectAndCompute(ia,m);kb,db=sift.detectAndCompute(ib,m)
        if da is None or db is None or len(ka)<30 or len(kb)<30: continue
        ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1);a=[];b=[]
        for q in ab:
            if len(q)==2 and q[0].distance<0.75*q[1].distance and ba[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                a.append(ka[q[0].queryIdx].pt);b.append(kb[q[0].trainIdx].pt)
        a=np.array(a);b=np.array(b)
        if len(a)<25: continue
        qa,qb=rect(a,b);ok=(abs(qa[:,1]-qb[:,1])<25)&(qa[:,0]-qb[:,0]>1)&(qa[:,0]-qb[:,0]<500)
        if ok.sum()>=25: res.append(dict(sess=it['sess'],t=it['t'],dt=it['dt'],a=a[ok],b=b[ok]))
    return res
if __name__=='__main__':
    Wk=os.path.abspath(sys.argv[1]);step=int(sys.argv[2]) if len(sys.argv)>2 else 15;os.makedirs(Wk,exist_ok=True);cal=base800(os.path.join(Wk,'v3_800.json'))
    jobs=[]
    for k,(a,b) in SESS.items():
        if k.startswith('N'): continue
        from sync import sfasati
        P=pairs(a,b);off,sf=sfasati(P);P=[p for p,s in zip(P,sf) if not s and abs(p['dt'])<=1.0]
        st=step if not k.startswith('M') else max(3,step//3);P=P[::st];print(k,'coppie sync ok scelte',len(P),flush=True)
        g=collections.OrderedDict()
        for p in P: g.setdefault((p['a'][0],p['b'][0]),[]).append(dict(a=p['a'],b=p['b'],sess=k,t=p['t'],dt=p['dt']))
        jobs+=[(cal,ca,cb,v) for (ca,cb),v in g.items()]
    print('job',len(jobs),flush=True)
    with Pool(2) as pool: out=[x for o in pool.imap_unordered(work,jobs) for x in o]
    out.sort(key=lambda r:(r['sess'],r['t']));print('coppie con match',len(out),'punti',sum(len(o['a']) for o in out))
    pickle.dump(out,open(os.path.join(Wk,'lr_matches.pkl'),'wb'))
