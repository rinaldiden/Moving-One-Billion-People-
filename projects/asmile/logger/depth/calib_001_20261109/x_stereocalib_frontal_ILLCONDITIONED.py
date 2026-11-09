import pickle,numpy as np,cv2,sys
SP=sys.argv[1]; SQ=float(sys.argv[2])
r=pickle.load(open(f'{SP}/corners.pkl','rb'))
pat=(6,9)
obj=np.zeros((54,3),np.float32); obj[:,:2]=np.mgrid[0:6,0:9].T.reshape(-1,2)*SQ/1000
# frames: subsample, skip moving blur (sq size changing fast) 
fr=[];last=None
for i,a,b in r:
    if a is None or b is None: continue
    if last is not None and np.abs(a.mean(0)-last).max()<6 and i>0 and fr and abs(i-fr[-1][0])<45: continue
    fr.append((i,a.astype(np.float32),b.astype(np.float32))); last=a.mean(0)
print('viste',len(fr))
W,H=1280,800
O=[obj]*len(fr); PL=[f[1].reshape(-1,1,2) for f in fr]; PR=[f[2].reshape(-1,1,2) for f in fr]
for flags,name in [(cv2.CALIB_FIX_PRINCIPAL_POINT|cv2.CALIB_ZERO_TANGENT_DIST|cv2.CALIB_FIX_K2|cv2.CALIB_FIX_K3,'k1'),
                   (cv2.CALIB_FIX_PRINCIPAL_POINT|cv2.CALIB_ZERO_TANGENT_DIST|cv2.CALIB_FIX_K3,'k1k2')]:
    K0=np.array([[1000,0,W/2],[0,1000,H/2],[0,0,1.]])
    out=[]
    for P in (PL,PR):
        e,K,D,_,_=cv2.calibrateCamera(O,P,(W,H),K0.copy(),np.zeros(5),flags=flags|cv2.CALIB_USE_INTRINSIC_GUESS)
        out.append((e,K,D))
    print(name,'rms',[round(o[0],3) for o in out],'f',[round(o[1][0,0],1) for o in out],'k',[o[2].ravel()[:2].round(3).tolist() for o in out])
    e,K1,D1,K2,D2,R,T,E,F=cv2.stereoCalibrate(O,PL,PR,out[0][1],out[0][2],out[1][1],out[1][2],(W,H),flags=cv2.CALIB_FIX_INTRINSIC)[:9]
    print('  stereo rms',round(e,3),'|T| mm',round(float(np.linalg.norm(T))*1000,1),'T',(T.ravel()*1000).round(1),'rot deg',np.degrees(cv2.Rodrigues(R)[0].ravel()).round(2))
    pickle.dump(dict(K1=K1,D1=D1,K2=K2,D2=D2,R=R,T=T),open(f'{SP}/stereo_{name}.pkl','wb'))
