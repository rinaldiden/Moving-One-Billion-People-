"""ESPLORATIVO (post-hoc, dichiarato): dopo aver visto che S2 t<75 s e' un transitorio (dy -8 -> -22 -> -7 px a mano), fit su S2 stabile t>=120 s,
blocchi 60 s pari->fit, dispari->test + scambio; verifica su M (mattina) e su S2 90-120 s mai usati; remap+SIFT indipendente. uso: python3 v4.py <lavoro> <out.json>"""
import os,sys,json,numpy as np,cv2,pickle as pk
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
sys.argv_=sys.argv;src=open('analyze.py').read().split('def main')[0]
exec(src)
from extract import decode
from sync import pairs
def main():
    Wk=os.path.abspath(sys.argv_[1]);outp=os.path.abspath(sys.argv_[2]);M=Model(json.load(open(Wk+'/v3_800.json')));S=pk.load(open(Wk+'/lr_matches.pkl','rb'))
    rng=np.random.default_rng(1);rd=lambda p,K:np.hypot((p[:,0]-K[0,2])/K[0,0],(p[:,1]-K[1,2])/K[1,1]);L=[]
    for s in S:
        n=len(s['a']);i=rng.permutation(n)[:300];a=s['a'][i];b=s['b'][i];v=(rd(a,M.K1)<0.64)&(rd(b,M.K2)<0.64);L.append((s['sess'],s['t'],a[v],b[v]))
    X=imu('143247');cat=lambda sel:(np.concatenate([x[2] for x in sel]),np.concatenate([x[3] for x in sel]))
    st=[x for x in L if x[0].startswith('S2') and x[1]>=120];ev=[x for x in st if int(x[1]//60)%2==0];od=[x for x in st if int(x[1]//60)%2==1]
    (Ae,Be),(Ao,Bo)=cat(ev),cat(od);z0=np.zeros(3)
    pe=fitR(M,Ae,Be);po=fitR(M,Ao,Bo);pa=fitR(M,*cat(st));o=dict(n_fit_pari=len(Ae),n_test_dispari=len(Ao))
    o['dR_xyz_deg_vs_v3']=dict(pari=deg(pe).round(4).tolist(),dispari=deg(po).round(4).tolist(),tutti=deg(pa).round(4).tolist());print(o)
    pr=lambda tag,p,A,B:(lambda s:(print(tag,'n',s['n'],'med %.2f p95 %.2f segno %.2f'%(s['med'],s['p95'],s['segno'])),s)[1])(m2.stats(M,p,'R',A,B))
    o['test_dispari_Rpari']=pr('test dispari R(pari)',pe,Ao,Bo);o['test_pari_Rdispari']=pr('swap pari R(dispari)',po,Ae,Be);o['test_dispari_v3']=pr('test dispari v3',z0,Ao,Bo)
    mov=lambda x:moving(X,int(x[1]//30)*30)
    for tag,f in(('moto',lambda x:mov(x) is True),('fermo',lambda x:mov(x) is False)):
        sel=[x for x in od if f(x)]
        if sel: A,B=cat(sel);o['dispari_'+tag]=pr('dispari '+tag+' R(pari)',pe,A,B)
    # finestre 30 s con R(pari) su tutto S2 t>=90 + salti
    W={}
    for x in L:
        if x[0].startswith('S2') and x[1]>=90: W.setdefault(int(x[1]//30)*30,[]).append(x)
    rows=[]
    for w in sorted(W):
        A,B=cat(W[w]);s=m2.stats(M,pe,'R',A,B);t=int(w//60)%2==1;rows.append(dict(t0=w,n=s['n'],moto=mov(W[w][0]),tenuta_fuori=t,med=round(s['med'],2),p95=round(s['p95'],2),segno=round(s['segno'],2)))
    o['finestre']=rows;j=[round(b['segno']-a['segno'],2) for a,b in zip(rows,rows[1:]) if b['t0']-a['t0']==30];o['salto_max_abs']=max(abs(v) for v in j);print('salto max',o['salto_max_abs'],'finestre',len(rows))
    # mattina e S1 con R v4
    for tag,pref in(('M','M'),('S1','S1')):
        sel=[x for x in L if x[0].startswith(pref)]
        if sel and sum(len(x[2]) for x in sel)>200: A,B=cat(sel);o['ctrl_'+tag]=dict(v3=m2.stats(M,z0,'R',A,B),v4=m2.stats(M,pa,'R',A,B));print(tag,'v3 med %.2f segno %.2f | v4 med %.2f p95 %.2f segno %.2f n %d'%(o['ctrl_'+tag]['v3']['med'],o['ctrl_'+tag]['v3']['segno'],o['ctrl_'+tag]['v4']['med'],o['ctrl_'+tag]['v4']['p95'],o['ctrl_'+tag]['v4']['segno'],len(A)))
    # profondita': disparita' dei punti del test (spread)
    qa,qb=m2.rect_pts(M,pe,'R',Ao,Bo);d=qa[:,0]-qb[:,0];o['disparita_test_pct_5_50_95']=np.percentile(d,[5,50,95]).round(1).tolist()
    # remap+SIFT indipendente su 60 coppie dei blocchi dispari
    c=json.load(open(Wk+'/v3_800.json'));R_new=(Rm(pa)@M.R0);c4=dict(c);c4['R']=R_new.tolist();json.dump(c4,open(Wk+'/_v4_tmp.json','w'))
    P=[q for q in pairs('143247','143252') if abs(q['dt'])<=1.0 and q['t']>=120 and int(q['t']//60)%2==1][::170][:60]
    def maps(cal):
        cc=json.load(open(cal));K1=np.array(cc['K_left']);K2=np.array(cc['K_right']);d1=np.array(cc['dist_left']);d2=np.array(cc['dist_right'])
        r=cv2.stereoRectify(K1,d1,K2,d2,tuple(cc['size']),np.array(cc['R']),np.array(cc['T']).reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
        return cv2.initUndistortRectifyMap(K1,d1,r[0],r[2],(1280,800),cv2.CV_32FC1),cv2.initUndistortRectifyMap(K2,d2,r[1],r[2],(1280,800),cv2.CV_32FC1)
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher();imgs=[(decode(q['a'][0],[q['a'][1]])[q['a'][1]],decode(q['b'][0],[q['b'][1]])[q['b'][1]]) for q in P];rows2={}
    for name,cal in(('v3_800',Wk+'/v3_800.json'),('v4',Wk+'/_v4_tmp.json')):
        m1_,m2_=maps(cal);rr=[]
        for ia,ib in imgs:
            ra=cv2.remap(ia,*m1_,cv2.INTER_LINEAR);rb=cv2.remap(ib,*m2_,cv2.INTER_LINEAR);mk=np.zeros_like(ra);mk[8:-8,8:-8]=255
            ka,da=sift.detectAndCompute(ra,mk);kb,db=sift.detectAndCompute(rb,mk)
            if da is None or db is None or len(ka)<20 or len(kb)<20: continue
            ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
            for q in ab:
                if len(q)==2 and q[0].distance<0.75*q[1].distance and ba[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                    a=ka[q[0].queryIdx].pt;b=kb[q[0].trainIdx].pt
                    if abs(a[1]-b[1])<25 and a[0]-b[0]>1: rr.append((a[0],a[1],b[1]-a[1]))
        rr=np.array(rr);ad=abs(rr[:,2]);zz=np.clip((rr[:,1]/800*3).astype(int),0,2)*3+np.clip((rr[:,0]/1280*3).astype(int),0,2)
        rows2[name]=dict(n=len(rr),coppie=len(imgs),med=float(np.median(ad)),p95=float(np.percentile(ad,95)),segno=float(np.median(rr[:,2])),zone=[[int((zz==i).sum()),round(float(np.median(ad[zz==i])),2) if (zz==i).sum()>=15 else None,round(float(np.percentile(ad[zz==i],95)),2) if (zz==i).sum()>=15 else None] for i in range(9)])
        print('REMAP',name,rows2[name]['n'],'med %.2f p95 %.2f segno %.2f'%(rows2[name]['med'],rows2[name]['p95'],rows2[name]['segno']),rows2[name]['zone'])
    o['remap_dispari']=rows2;os.remove(Wk+'/_v4_tmp.json')
    # zone 3x3 su test dispari (R pari)
    o['zone_test_dispari_Rpari']=o['test_dispari_Rpari']['zone']
    c4['stato']='PROVVISORIO da officina 24/11: R rifittata (Rx,Rz) su S2 t>=120 s; NON promuovibile: scala non verificata, giro corto (~4-5 min strada), Ry/d0 da v3'
    c4['size']=[1280,800];c4['version']='v4_20261124_provvisorio';c4['v4_montaggio']=dict(dR_xyz_deg_vs_v3=deg(pa).round(4).tolist(),base='v3 con cy+40 su entrambe (modo 800 parte dalla riga 0)',fit='S2 143247/143252 t>=120 s tutti i blocchi; test pari/dispari+scambio in analisi',note='1280x800')
    json.dump(c4,open(outp,'w'),indent=1);json.dump(o,open(Wk+'/v4_analisi.json','w'),indent=1,default=float)
main()
