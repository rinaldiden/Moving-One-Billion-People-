"""Rifit montaggio giro2 - passo 1: accoppiamento PER SESSIONE (le 2 sessioni ripartono entrambe da t~9 s: make_pairs() le mescola) e match SIFT L-R
su fotogrammi GREZZI (nessuna rettifica: il risultato non dipende dalla calibrazione da giudicare). Salva lr_matches.pkl (piccolo).
uso: python3 -m logger02_v2.m1_extract_lr <cartella_giro> <lavoro> [passo_pair=25]   (max 2 processi, decodifica solo i fotogrammi scelti via ffmpeg select)"""
import os,sys,glob,csv,pickle,subprocess,collections,numpy as np,cv2
from multiprocessing import Pool
def rows(side,D):
    out=[]
    for f in sorted(glob.glob(f'{D}/{side}/clip_*_{side}_*_frames.csv')):
        clip=f.replace('_frames.csv','.h264');sess=os.path.basename(f).split('_')[2]+'_'+os.path.basename(f).split('_')[3]
        for i,r in enumerate(csv.DictReader(open(f))): out.append((int(r['t_us' if side=='A' else 't_a_us']),clip,i,sess))
    return out
def pairs_per_session(D):
    A=rows('A',D);B=rows('B',D);sa=sorted({r[3] for r in A});sb=sorted({r[3] for r in B});out=[]
    # NB giro2: la sessione 2 ha A 9-70 s e B 199-321 s (nessuna sovrapposizione): scartata dal gate 10 ms
    sb=sb[:len(sa)] if len(sb)>=len(sa) else sb
    for k,(a_s,b_s) in enumerate(zip(sa,sb)):
        a=[r for r in A if r[3]==a_s];b=sorted([r for r in B if r[3]==b_s],key=lambda r:r[0]);tb=np.array([r[0] for r in b]);ta=np.array([r[0] for r in a])
        j=np.clip(np.searchsorted(tb,ta),1,len(tb)-1);jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1)
        for i in range(len(a)):
            if abs(tb[jj[i]]-ta[i])<10000: out.append(dict(sess=k,t=ta[i]/1e6,a=a[i][1:3],b=b[jj[i]][1:3]))
    return out
def decode(clip,idx):
    idx=sorted(set(idx));expr='+'.join(f'eq(n\\,{i})' for i in idx)
    p=subprocess.run(['ffmpeg','-v','error','-i',clip,'-vf',f"select='{expr}'",'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    W,H=1280,720;v=np.frombuffer(p.stdout,np.uint8);n=len(v)//(W*H);assert n==len(idx),(clip,n,len(idx))
    return dict(zip(idx,v.reshape(n,H,W)))
import json
CAL=os.environ.get('L02_CALIB')
def _rect():
    c=json.load(open(CAL));K1=np.array(c['K_left']);K2=np.array(c['K_right']);d1=np.array(c['dist_left']);d2=np.array(c['dist_right'])
    r=cv2.stereoRectify(K1,d1,K2,d2,tuple(c['size']),np.array(c['R']),np.array(c['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    f=lambda p,K,d,R_:cv2.undistortPoints(p.reshape(-1,1,2).astype(np.float64),K,d,R=R_,P=r[2]).reshape(-1,2)
    return lambda a,b:(f(a,K1,d1,r[0]),f(b,K2,d2,r[1]))
def work(args):
    rect=_rect();ca,cb,items=args;A=decode(ca,[i['a'][1] for i in items]);B=decode(cb,[i['b'][1] for i in items])
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
        qa,qb=rect(a,b);ok=(abs(qa[:,1]-qb[:,1])<25)&(qa[:,0]-qb[:,0]>1)&(qa[:,0]-qb[:,0]<500)   # gate larghissimo (+-25 px, centrato su 0 ma l'errore misurato ~10): non tronca
        if ok.sum()>=25: res.append(dict(sess=it['sess'],t=it['t'],a=a[ok],b=b[ok]))
    return res
if __name__=='__main__':
    D=os.path.abspath(sys.argv[1]);Wk=os.path.abspath(sys.argv[2]);step=int(sys.argv[3]) if len(sys.argv)>3 else 25;os.makedirs(Wk,exist_ok=True)
    P=pairs_per_session(D);print('coppie',len(P),collections.Counter(p['sess'] for p in P),flush=True)
    sel=P[::step];g=collections.OrderedDict()
    for p in sel: g.setdefault((p['a'][0],p['b'][0]),[]).append(dict(a=p['a'],b=p['b'],sess=p['sess'],t=p['t']))
    jobs=[(ca,cb,v) for (ca,cb),v in g.items()];print('fotogrammi',len(sel),'job',len(jobs),flush=True)
    with Pool(2) as pool: out=[x for o in pool.map(work,jobs) for x in o]
    out.sort(key=lambda r:(r['sess'],r['t']));print('coppie con match',len(out),'punti',sum(len(o['a']) for o in out))
    pickle.dump(out,open(os.path.join(Wk,'lr_matches.pkl'),'wb'))
