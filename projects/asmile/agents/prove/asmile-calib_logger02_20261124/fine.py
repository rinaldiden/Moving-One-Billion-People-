import sys,os,json,pickle,numpy as np
sys.argv=['x',sys.argv[1]]
exec(open('analyze.py').read().split('def main')[0])
Wk=sys.argv[1];M=Model(json.load(open(Wk+'/v3_800.json')));S=pickle.load(open(Wk+'/lr_matches.pkl','rb'));X=imu('143247')
for s in S:
    if s['sess'].startswith('S2') and s['t']<140 and int(s['t'])%6<1:
        qa,qb=m2.rect_pts(M,np.zeros(3),'R',s['a'],s['b']);dy=qa[:,1]-qb[:,1];ok=(qa[:,0]-qb[:,0]>1)&(abs(dy)<25)
        m=(X[:,0]>=s['t']-.5)&(X[:,0]<s['t']+.5);g=X[m,4:7]
        print('%.1f n %d dy med %.2f iqr %.2f | gyro max %.0f'%(s['t'],ok.sum(),np.median(dy[ok]),np.subtract(*np.percentile(dy[ok],[75,25])),np.abs(g-np.median(X[:,4:7],0)).max() if len(g) else -1))
