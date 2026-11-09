# Lezioni di asmile-capo

Cosa ho previsto male. Le legge il capo-critico.

- 2026-11-09 VETO del capo-critico sul piano: (1) avevo trattato i tape_points di calib come verifica, sono punti del fit; (2) avevo promesso una prova encoder "6-20 km/h" senza guardare i CSV: c'era una sola sessione utile fino a 16 km/h e il GPS è a 1 Hz, non 10; (3) non avevo previsto il rischio duplicati/fake-hwclock. → REGOLA: prima di scrivere un criterio di uscita, guarda i dati che lo devono dimostrare.
- 2026-11-09 Avevo dato per buone le "11 sessioni" della lavagna: l'elenco di stato.py ne saltava 3 su disco (145051, 161628, 164438), trovate dal critico. → erano già segmentate (stato.py le conta "lavorate" se esiste _seg*), ma MAI controllate dall ingest: "segmentato" non vuol dire "controllato".
- 2026-11-09 Falso allarme "camere nere" su #001: `rpicam-still` JPEG dà immagini a 0 sulle OV9281 mono, ma il video (`rpicam-vid`, come il recorder) è buono (luma ~70-90 su entrambe). → REGOLA: per controllare le camere usa sempre `rpicam-vid --codec yuv420` e misura la Y, mai rpicam-still JPEG. Ho disturbato Daniele per niente.
- 2026-11-09 #001 è tornato online con le prove già fatte e io ho scritto "aspetto che rientri": SBAGLIATO. → REGOLA: quando un Pi torna online, guarda SUBITO se ci sono sessioni nuove e lavorale (pull + agenti), senza aspettare che Daniele lo dica.
- 2026-11-09 Depth in moto #001: la v1 dichiarava 3.9%/2.6% con un filtro CIRCOLARE (scartava ciò che non tornava). L'occhio l'ha scoperto. → REGOLA: ogni verifica "in moto" senza filtri basati sulla grandezza che si sta verificando; prima si dimostra il METODO (pendenza ≈1 con odometria), poi l'errore. Al 2° veto su un gate che dipende da dati fisici mancanti, FERMA il giro e chiedi il dato a Daniele invece di bruciare il 3° veto.

## 2026-11-09 pomeriggio
- Con Daniele in garage: meno passaggi di conferma, più azione. Quando dà il "vai" per una prova, le iterazioni di taratura
  della stessa prova (stessa direzione, stessi tetti) sono coperte; chiedere solo per cose nuove (scrittura VESC, freno).
- `pgrep -f X` dentro un `ssh '...X...'` trova se stesso: loop infinito. Usare pid file o pgrep -x.
- ssh -tt con input in pipe: tenere stdin aperto dopo il "vai" (sleep), altrimenti hangup uccide lo script prima della scrittura.
- Calib: il metro a mano ai bordi sbaglia di 25-80 cm (Daniele finisce più indietro): giudice dei bordi = PnP scacchiera, non il metro.
