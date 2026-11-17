import sys,cv2,numpy as np,pickle
sys.path.insert(0,'/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth')
from stereo_common import Calib
c=Calib.load('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json');r=c.rectify()
rp=lambda p,K,D,R,P: cv2.undistortPoints(p.reshape(-1,1,2).astype(np.float64),K,D,R=R,P=P).reshape(-1,2)
def zones(u1,u2,name):
    dy=u1[:,1]-u2[:,1];d=u1[:,0]-u2[:,0];far=d<25
    print(name,'n far',far.sum())
    for xl,xh in [(0,300),(300,600),(600,900),(900,1200),(1200,1500)]:
        row=[]
        for yl,yh in [(0,250),(250,500),(500,800)]:
            m=far&(u1[:,0]>=xl)&(u1[:,0]<xh)&(u1[:,1]>=yl)&(u1[:,1]<yh)
            row.append('%+.2f(%d)'%(np.median(dy[m]),m.sum()) if m.sum()>=8 else '  --  ')
        print('x%4d-%4d'%(xl,xh),' '.join(row))
M=pickle.load(open('../meas3.pkl','rb'))
S1=np.vstack([m['s1'] for m in M]);S2=np.vstack([m['s2'] for m in M])
zones(rp(S1,c.K1,c.d1,r['R1'],r['P1']),rp(S2,c.K2,c.d2,r['R2'],r['P2']),'MATTINA (stop 093216), colonne=x rett, righe y 0-250/250-500/500-800')
# pomeriggio
FL=np.load('full_left.npy',mmap_mode='r');FR=np.load('full_right.npy',mmap_mode='r')
sift=cv2.SIFT_create(4000);bf=cv2.BFMatcher()
P1=[];P2=[]
for i in range(0,2596,90):
    a=np.array(FR[i]);b=np.array(FL[i])   # a=cam sinistra calib
    ka,da=sift.detectAndCompute(a,None);kb,db=sift.detectAndCompute(b,None)
    for m,n in bf.knnMatch(da,db,k=2):
        if m.distance<0.75*n.distance:P1.append(ka[m.queryIdx].pt);P2.append(kb[m.trainIdx].pt)
P1=np.array(P1);P2=np.array(P2)
u1=rp(P1,c.K1,c.d1,r['R1'],r['P1']);u2=rp(P2,c.K2,c.d2,r['R2'],r['P2'])
ok=abs(u1[:,1]-u2[:,1])<12;u1,u2=u1[ok],u2[ok]
zones(u1,u2,'POMERIGGIO (153251, stessi criteri)')
pickle.dump((P1[ok],P2[ok]),open('../pm_sift.pkl','wb'))
