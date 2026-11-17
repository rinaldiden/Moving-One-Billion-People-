import cv2, numpy as np, glob, sys
unit=sys.argv[1]; fs=sorted(glob.glob(f"asmile-loggers/_seg_sam3_L1classi_v2/frames/{unit}_*.jpg"))
for k in range(0,len(fs),30):
    t=[]
    for p in fs[k:k+30]:
        im=cv2.resize(cv2.imread(p),(320,200)); cv2.putText(im,p[-7:-4],(3,16),0,0.55,(0,255,255),2); t.append(im)
    while len(t)%6: t.append(np.zeros((200,320,3),np.uint8))
    cv2.imwrite(f"asmile-loggers/_seg_sam3_L1classi_v2/sheet_{unit}_{k//30}.jpg",np.vstack([np.hstack(t[i:i+6]) for i in range(0,len(t),6)]),[cv2.IMWRITE_JPEG_QUALITY,85])
