import sys,cv2,numpy as np,pickle
SP=sys.argv[1]
cl=cv2.VideoCapture(f'{SP}/mp4/s093216_right.mp4')   # file "left" = cam0 = fisicamente DESTRA
cr=cv2.VideoCapture(f'{SP}/mp4/s093216_left.mp4')
# NB: nomi: s*_left.mp4 = cam0 (destra fisica); s*_right.mp4 = cam1 (sinistra fisica)
cL=cv2.VideoCapture(f'{SP}/mp4/s093216_right.mp4'); cR=cv2.VideoCapture(f'{SP}/mp4/s093216_left.mp4')
pat=(6,9); res=[]; i=0
while True:
    a,fa=cL.read(); b,fb=cR.read()
    if not(a and b): break
    if i%3==0:
        gL=cv2.cvtColor(fa,cv2.COLOR_BGR2GRAY); gR=cv2.cvtColor(fb,cv2.COLOR_BGR2GRAY)
        okL,cLc=cv2.findChessboardCornersSB(gL,pat,cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY)
        okR,cRc=cv2.findChessboardCornersSB(gR,pat,cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY)
        res.append((i,cLc.reshape(-1,2) if okL else None,cRc.reshape(-1,2) if okR else None))
    i+=1
pickle.dump(res,open(f'{SP}/corners.pkl','wb'))
print(i,sum(1 for r in res if r[1] is not None),sum(1 for r in res if r[2] is not None),sum(1 for r in res if r[1] is not None and r[2] is not None))
