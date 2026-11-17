import cv2,json,numpy as np,sys
s=json.load(open('sets.json'))
def mont(fs,name):
    ims=[cv2.resize(cv2.imread(f'raw/f{f}.jpg'),(800,500)) for f in fs]
    while len(ims)%2: ims.append(np.zeros_like(ims[0]))
    rows=[np.hstack(ims[i:i+2]) for i in range(0,len(ims),2)]
    cv2.imwrite(name,np.vstack(rows),[cv2.IMWRITE_JPEG_QUALITY,80])
for k in ('al','act'):
    for j in range(0,20,4): mont(s[k][j:j+4],f'm_{k}{j//4}.jpg')
mont(s['lost'][:6],'m_lost0.jpg'); mont(s['lost'][6:],'m_lost1.jpg')
