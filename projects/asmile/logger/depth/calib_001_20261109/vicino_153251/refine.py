import sys,cv2,numpy as np,pickle
sys.argv=['x','/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json','/dev/null']
exec(open('meas3.py').read().split("res=[]")[0])
M=pickle.load(open('meas3_cur.pkl','rb'));out=[]
for m in M:
    i=m['frame'];L=rl(i);best=None
    for s in np.geomspace(m['scale']*0.9,m['scale']*1.1,41):
        tp=cv2.resize(TPL,None,fx=s,fy=s,interpolation=cv2.INTER_AREA);h,w=tp.shape
        x0=int(m['x0b']+m['w']/2-w/2);y0=int(m['y0b']+m['h']/2-h/2)
        sx0=max(0,x0-6);sy0=max(0,y0-6);rs=cv2.matchTemplate(L[sy0:min(CH,y0+h+6),sx0:min(CW,x0+w+6)],tp,cv2.TM_CCOEFF_NORMED)
        mx=rs.max()
        if best is None or mx>best[0]:best=(mx,s)
    m['scale_ref']=best[1];m['sq_ref']=SQ*best[1];m['mx_ref']=best[0];print(m['run'],'%.1f->%.2f mx=%.2f'%(m['sqpx'],m['sq_ref'],best[0]))
pickle.dump(M,open('meas3_ref.pkl','wb'))
