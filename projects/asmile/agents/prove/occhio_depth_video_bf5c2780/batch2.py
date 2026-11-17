from ncc import *
import pandas as pd
R='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/training/depth/out_20261112/session_20261109_094146/'
f=pd.read_csv(R+'frames.csv').set_index('frame')
items=[
(6051,'auto argento corpo',(668,380,714,480),'rep picco 7.1 med 15.1'),
(6051,'specchio furgone',(640,320,690,370),''),
(9938,'bici manubrio/ruota',(1050,590,1130,790),'nessuna det'),
(9938,'bici sella',(1150,300,1280,420),''),
(9938,'muro centro',(560,200,1000,700),'rep 1.7 med 2.9'),
(9190,'colonnina c',(520,530,565,750),'rep 3.3'),
(9190,'colonnina dx',(1100,400,1150,720),'rep 3.4(med 6.8)'),
(9250,'lastra',(735,400,775,520),'rep 7.8'),
(9265,'lastra',(640,410,710,600),'rep 5.0'),
(6156,'Iveco',(1060,340,1190,470),'rep 8.7'),
(9518,'colonna sx',(330,420,390,780),'rep 2.7'),
(9533,'ceppo sx',(200,430,265,540),'rep 5.4'),
]
for fr,l,roi,note in items:
    s=summarize(ncc_roi('094146',fr,roi))
    print(fr,'s=%.2f'%f.loc[fr,'s_enc_m'],l,'NCC',None if s is None else {k:round(v,2) for k,v in s.items()},'|',note,flush=True)
