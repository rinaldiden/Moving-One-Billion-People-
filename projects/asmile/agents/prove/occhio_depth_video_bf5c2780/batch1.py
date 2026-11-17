from ncc import *
items=[
(5282,'car208 grille',(770,390,990,500),9.0,'size 8.7(w, piano largo)'),
(5492,'runner',(688,365,725,440),14.1,'size 19.8 se adulto 1.75'),
(5492,'persona dx bordo',(1235,300,1278,500),10.1,'size 9.7'),
(6021,'van posteriore',(60,200,420,520),3.2,'-'),
(6081,'plate',(270,415,380,445),6.1,'size 6.0'),
(6081,'auto argento',(595,335,700,440),16.5,'size 19.4(w)'),
(6156,'auto argento',(630,335,725,425),21.3,'size 23.4(w)'),
(6756,'persona+cane',(190,240,290,540),6.0,'size 6.5 (h1.65)'),
(6756,'cane',(345,490,440,550),6.9,''),
(6831,'persona',(830,300,885,470),11.3,'size 11.4'),
(6921,'cartello tondo',(945,235,1020,305),10.5,'size 10.1 (d0.6)'),
(6921,'pallet',(905,345,1030,520),9.1,'size 11.8(1.2m)/7.9(0.8m)'),
(7225,'persona',(780,300,880,520),7.7,'size 8.0'),
(7615,'colonnina 1',(512,290,552,590),4.4,'size 4.2 (h1.0)'),
(7615,'colonnina 2',(855,300,895,590),4.3,'size 4.3 (h1.0)'),
(7900,'persona vicina',(1085,260,1185,560),7.0,'size 6.4'),
(9518,'colonna dx',(970,500,1025,740),3.0,'contatto ~3.3'),
(9518,'colonna sx',(330,420,390,780),2.7,''),
(2097,'auto grille',(600,330,980,520),5.1,'size 5.9(w)'),
(1990,'auto',(575,320,690,420),18.9,'size 18.8'),
(6051,'targa',(120,470,280,510),4.1,'size 4.2'),
]
for fr,l,roi,rep,note in items:
    s=summarize(ncc_roi('094146',fr,roi))
    print(fr,l,'rep',rep,'| NCC',None if s is None else {k:round(v,2) for k,v in s.items()},'|',note,flush=True)
