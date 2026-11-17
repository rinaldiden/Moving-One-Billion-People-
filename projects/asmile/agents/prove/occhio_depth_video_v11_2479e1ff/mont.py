import cv2,sys,numpy as np
fr=[int(x) for x in sys.argv[2:]]; ims=[cv2.resize(cv2.imread(f'raw/f{f}.jpg'),(640,400)) for f in fr]
while len(ims)%3: ims.append(np.zeros_like(ims[0]))
cv2.imwrite(sys.argv[1],np.vstack([np.hstack(ims[i:i+3]) for i in range(0,len(ims),3)]),[cv2.IMWRITE_JPEG_QUALITY,80])
