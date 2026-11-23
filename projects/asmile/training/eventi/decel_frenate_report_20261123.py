#!/usr/bin/env python3
"""Unisce eventi #001 (13/11) + etichette di contesto (guardate a mano sui fotogrammi, 4 per evento) + logger001 BLE;
scrive CSV finale e stampa le tabelle. Etichette: 'non_chiaro' dove il fotogramma non permette di dire."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, 'training/eventi')
import decel_frenate_20261123 as D
OUT = sys.argv[1]   # argv[2] = CSV logger (decel_frenate_logger_20261123.py)
# (contesto, nota) per ora-evento, dai fotogrammi (SAM3 da solo non discrimina: pole/bollard ovunque)
L = {
'15:03:50': ('non_chiaro', 'vicolo stretto con arco, stop a 0 (IMPUNTATA); causa non visibile'),
'15:04:22': ('curva', 'strada in curva stretta fra muri, 15->7'),
'15:05:00': ('non_chiaro', 'controluce, dissuasore a dx; servo 55 gradi, v quasi costante'),
'15:05:02': ('ostacolo_fisso_curva', 'dissuasore/pietra a dx in piazzetta + curva sx'),
'15:05:19': ('non_chiaro', 'rallenta a 0 in piazza, auto parcheggiate a sx, nessuno in traiettoria'),
'15:05:55': ('ostacolo_fisso_curva', 'fioriere/muro a dx, curva'),
'15:06:48': ('incrocio_stop', 'incrocio con strisce, cartello probabile STOP e auto sulla trasversale'),
'15:06:56': ('pedone', 'pedone davanti nel centro (cammina nella stessa direzione), dissuasori'),
'15:07:08': ('incrocio', 'incrocio, auto che passano, cartello P'),
'15:07:36': ('non_chiaro', 'piazza aperta, pedoni lontani/strisce'),
'15:07:38': ('auto_attraversa', 'SUV attraversa davanti, stop a 0'),
'15:07:48': ('incrocio', 'strisce+fioriere, auto sulla trasversale'),
'15:07:57': ('pedone', 'persona vicino a tavolo coperto sul lato'),
'15:08:19': ('auto_attraversa', 'auto nera davanti alle strisce, pedoni'),
'15:08:49': ('auto_attraversa', 'monovolume nera attraversa a strisce'),
'15:08:51': ('auto_attraversa', 'monovolume nera attraversa a strisce, stop a 0 (IMPUNTATA)'),
'15:09:31': ('incrocio', 'auto parcheggiate/in arrivo da sx, ciclista fermo'),
'15:15:05': ('curva', 'curva a dx con ciclista lontano a sx'),
'15:15:57': ('pedone_strisce', 'strisce con pedoni in attesa e auto che passa, stop a 0'),
'15:16:34': ('non_chiaro', 'fioriere in fila a dx, edificio'),
'15:17:18': ('incrocio', 'incrocio, furgone/auto sulla trasversale, curva dx'),
'15:17:43': ('non_chiaro', 'controluce forte, cartelli tondi'),
'15:17:55': ('auto_pedone', 'controluce, auto davanti e persona a lato'),
'15:18:07': ('pedone_strisce', 'strisce, pedoni lontani, controluce'),
'15:18:13': ('incrocio', 'incrocio, auto bianca da dx'),
'15:18:28': ('incrocio_strisce', 'strisce, auto in arrivo'),
'15:18:58': ('pedone', 'vicolo stretto, pedone davanti'),
'15:19:11': ('passaggio_stretto', 'vicolo stretto in curva, cassetta metallica a dx'),
'15:19:49': ('passaggio_stretto', 'vicolo con furgone parcheggiato'),
'15:20:40': ('passaggio_stretto', 'vicolo con biciclette parcheggiate a lato'),
}
d = D.load001('20261113_145727', 0.3477)
e = pd.DataFrame(D.ev001(d, 0.3477))
e['contesto'] = e.ora.map(lambda o: L.get(o, ('non_chiaro', ''))[0])
e['nota'] = e.ora.map(lambda o: L.get(o, ('', 'non classificato'))[1])
e['classe_freno'] = np.where(e.servo_max_deg >= 5, 'servo', np.where(e.lim_frac > 0.2, 'limiter_attivo', 'umano'))
e['in_curva_gz'] = e.gz_max_dps > 22
e['impuntata'] = e.ora.isin(['15:03:50', '15:08:51'])
e['depth_dist_m'] = np.nan; e['depth'] = 'non_disponibile'
e['intent'] = np.where(e.contesto == 'non_chiaro', 'intent:unknown', e.contesto)
e['fine_a_zero'] = e.v1_kmh < 1.0
lg = pd.read_csv(sys.argv[2])
lg['contesto'] = 'non_chiaro'; lg['intent'] = 'intent:unknown'; lg['nota'] = 'non esaminato: BLE 1 Hz, stima grossolana, hw logger != #001'
lg['depth'] = 'non_disponibile'; lg['impuntata'] = False
pd.concat([e, lg], ignore_index=True).to_csv(OUT, index=False)
pd.set_option('display.width', 200)
print(len(e), e.contesto.value_counts().to_dict(), 'curva gz', int(e.in_curva_gz.sum()))
print(e.groupby('contesto').agg(n=('a_media', 'size'), am_mean=('a_media', 'mean'), am_p50=('a_media', 'median'), am_p90=('a_media', lambda x: x.quantile(.9)), am_max=('a_media', 'max'),
      pk_p50=('a_picco', 'median'), pk_max=('a_picco', 'max'), v0=('v0_kmh', 'median'), dist=('dist_m', 'median'), jerk_max=('jerk_max_ms3', 'max')).round(2))
ni = e[~e.impuntata]
print('NON impuntate n', len(ni), 'a_media p50/p90/max', ni.a_media.quantile([.5, .9, 1]).round(2).tolist(), 'a_picco p50/p90/max', ni.a_picco.quantile([.5, .9, 1]).round(2).tolist(),
      'jerk p50/p90/max', ni.jerk_max_ms3.quantile([.5, .9, 1]).round(2).tolist(), 'imu picco p90/max', ni.a_imu_picco.quantile([.9, 1]).round(2).tolist(), 'imu>=2.0:', int((ni.a_imu_picco >= 2.0).sum()))
print('impuntate'); print(e[e.impuntata][['ora', 'v0_kmh', 'a_media', 'a_picco', 'a_imu_picco', 'jerk_max_ms3', 'servo_max_deg']].round(2).to_string())
print('tutti a_media p50/p90/max', e.a_media.quantile([.5, .9, 1]).round(2).tolist(), 'a_picco', e.a_picco.quantile([.5, .9, 1]).round(2).tolist(), 'v0 p50', e.v0_kmh.median().round(1))
print('per classe freno'); print(e.groupby('classe_freno').agg(n=('a_media', 'size'), am=('a_media', 'median'), pk=('a_picco', 'median'), pkmax=('a_picco', 'max')).round(2))
print('fine a zero'); print(e[e.fine_a_zero][['ora', 'contesto', 'v0_kmh', 'a_media', 'a_picco', 'dist_m', 'classe_freno']].round(2).to_string())
# circ 0.3374: scala 0.970
print('scala circ 0.3374/0.3477 =', round(0.3374 / 0.3477, 3))
# GPS sanity
g = d[d.gps_v > 1.5]; print('gps ratio v/gps_v med', round(float((g.v / g.gps_v).median()), 3), len(g))
