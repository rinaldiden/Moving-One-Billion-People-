#!/usr/bin/env python3
"""Aggrega gli eventi estratti (soglie_dalle_guide.py) -> tabelle md + proposta JSON soglie. Solo lettura sui dati."""
import json, sys, numpy as np, pandas as pd
D = 'training/eventi/out_guide_20261112_c%s'
NMIN = 5

def pc(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return (np.nan,) * 3 if len(x) == 0 else tuple(np.percentile(x, [25, 50, 75]))

def f(t, d=2):
    return '/'.join('-' if not np.isfinite(v) else f'{v:.{d}f}' for v in t)

out = {}
for c in ('0.3477', '0.3374'):
    b = pd.read_csv(D % c + '/frenate.csv'); s = pd.read_csv(D % c + '/sterzate.csv'); v = pd.read_csv(D % c + '/velocita_1hz.csv')
    st = b[b.classe == 'stop_umano']
    rows = []
    for fa in (5, 8, 10, 12, 15):
        x = st[st.fascia == fa]
        rows.append(dict(fascia=fa, n=len(x), a_mean=pc(x.a_mean), a_peak=pc(x.a_peak), dur=pc(x.dur_s), sp=pc(x.sp_m),
                         v0=pc(x.v0_kmh)))
    out[c] = dict(b=b, s=s, v=v, st=st, rows=rows)
json.dump({c: [{k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()} for r in o['rows']] for c, o in out.items()},
          open('training/eventi/out_guide_20261112_c0.3477/tabella_frenate_fasce.json', 'w'), indent=1, default=float)
for c in out:
    print('== circ', c)
    for r in out[c]['rows']:
        print(r['fascia'], 'n', r['n'], 'a_mean', f(r['a_mean']), 'a_peak', f(r['a_peak']), 'dur', f(r['dur'], 1), 'sp_m', f(r['sp'], 1))
    st = out[c]['st']; print('pool stop n', len(st), 'a_mean', f(pc(st.a_mean)), 'a_peak', f(pc(st.a_peak)), 'sp', f(pc(st.sp_m), 1), 'dur', f(pc(st.dur_s), 1))
    s = out[c]['s']; print('sterzate n', len(s), 'rate_peak', f(pc(s.rate_peak), 0), 'amp', f(pc(s.amp_deg), 0), 'k', f(pc(s.k_med)), 'antic', f(pc(s.anticipo_s)), 'gz', f(pc(s.gz_peak), 0))
    v = out[c]['v']
    for fa, g in v[v.v_kmh > 0].groupby(pd.cut(v.v_kmh, [0, 6.5, 9, 11, 13.5, 99], labels=[5, 8, 10, 12, 15])):
        g = g[g.ctx != 'x']
        print('fascia', fa, 'n1hz', len(g), 'steer_rate p50/p90', f(pc(g.steer_rate)[1:2], 1), np.nanpercentile(g.steer_rate, 90).round(1),
              'steer_deg p50/p90', np.nanpercentile(g.steer_deg, 50).round(1), np.nanpercentile(g.steer_deg, 90).round(1))

# ------------------------------------------------------------------ report md + proposta json
seg = json.load(open(D % '0.3477' + '/segmenti.json'))
base = json.load(open('config/soglie_attuazione_001.json'))
P = base['parametri']
o = out['0.3477']; o2 = out['0.3374']
st, st2 = o['st'], o2['st']
# fit lineare sp = beta*v + gamma sui 15 stop, offset p75 dei residui
vv = st.v0_kmh.values / 3.6; sp = st.sp_m.values
A = np.c_[vv, np.ones_like(vv)]; beta, gamma = np.linalg.lstsq(A, sp, rcond=None)[0]
res = sp - A @ np.array([beta, gamma]); off = float(np.percentile(res, 75))
vv2 = st2.v0_kmh.values / 3.6; A2 = np.c_[vv2, np.ones_like(vv2)]; b2, g2 = np.linalg.lstsq(A2, st2.sp_m.values, rcond=None)[0]
off2 = float(np.percentile(st2.sp_m.values - A2 @ np.array([b2, g2]), 75))
def sp75(v, b=beta, g=gamma, of=off): return max(0.0, b * v + g + of)
def sp75_2(v): return max(0.0, b2 * v + g2 + off2)
rows = []; table = []
for r, kmh in zip(o['rows'] + [None] * 0, (5, 8, 10, 12, 15)):
    pass
tab_new = []
for r in base['tabella_per_velocita']:
    kmh, v = r['kmh'], r['v_ms']
    band_row = next((x for x in o['rows'] if x['fascia'] == kmh), None)
    n = band_row['n'] if band_row else 0
    in_range = 5 <= kmh <= 12
    if in_range:
        fr = sp75(v) + v * P['t_latenza_s'] + P['cuscinetto_m']
        stato = 'dalle guide (n banda=%d, fit pooled n=%d)' % (n, len(st)) + ('' if n >= NMIN else ' DEBOLE')
        rl = max(1.5 * fr, v * P['ttc_avviso_s'])
    else:
        fe = sp75(v) + v * P['t_latenza_s'] + P['cuscinetto_m']
        fr = max(r['frena_entro_m'], fe); rl = max(r['rallenta_entro_m'], 1.5 * fr, v * P['ttc_avviso_s'])
        stato = 'pochi dati: fuori 5-12 km/h, max(segnaposto, estrapolazione fit) per restare monotona'
    tab_new.append(dict(kmh=kmh, v_ms=v, frena_entro_m=round(fr, 2), rallenta_entro_m=round(rl, 2),
                        bordo_margine_m=r['bordo_margine_m'], origine=stato, n_banda=n,
                        frenata_guida_p25_p50_p75_m=[round(x, 2) for x in band_row['sp']] if band_row and n else None,
                        origine_bordo='segnaposto: in arrivo da v10'))
# parametri propri: decel pooled
dec_p25 = float(np.percentile(st.a_mean, 25)); dec_p50 = float(np.percentile(st.a_mean, 50))
prop = dict(base)
prop = json.loads(json.dumps(base))
prop['stato'] = ('PROPOSTA dalle guide di #001 (event-miner 2026-11-12), NON validata: la valida Daniele. Valida solo 5-12 km/h; '
                 'resto segnaposto. Frenate di routine (non emergenza). Latenza, cuscinetto, bordi, rallenta = segnaposto.')
prop['versione'] = 2
prop['parametri']['decel_guide_p25_ms2'] = round(dec_p25, 2)
prop['parametri']['_note']['decel_guide_p25_ms2'] = ('p25 delle decel medie di %d stop completi di Daniele (pooled, p50 %.2f, p75 %.2f). '
    'Cresce con la velocita (0.4 a 5 km/h, 1.1 a 12): solo riferimento; decel_frenata_ms2 (1.5, segnaposto) resta per le formule fuori tabella; la tabella usa la distanza di frenata osservata.' %
    (len(st), dec_p50, float(np.percentile(st.a_mean, 75))))
prop['parametri']['_note']['frena_entro_guide'] = ('distanza di frenata = fit lineare sp=%.2f*v%+.2f (+ offset p75 residui %.2f m) su %d stop; '
    '+ v*t_latenza + cuscinetto (segnaposto). Ruota 0.3477 m/giro enc.' % (beta, gamma, off, len(st)))
prop['formule']['frena_entro_m'] = ('5-12 km/h: (beta*v+gamma+off_p75) + v*t_latenza + cuscinetto; fuori: v*t_latenza + v^2/(2*decel_segnaposto 1.5) + cuscinetto')
prop['tabella_per_velocita'] = tab_new
prop['fonte_valori'] = dict(oggi='proposta guide', segnaposto_in_uso='config/soglie_attuazione_001.json', validato_da=None,
    circ_ruota_usata_m_per_giro_enc=0.3477, nota='con 0.3374 i numeri scendono del 3%: vedi rapporto')
prop['sterzo_dalle_guide'] = dict(
    n_curve=int(len(o['s'])), velocita_angolare_manubrio_picco_degs_p25_p50_p75=[round(x, 1) for x in pc(o['s'].rate_peak)],
    ampiezza_deg_p25_p50_p75=[round(x, 1) for x in pc(o['s'].amp_deg)],
    curvatura_1_su_m_p25_p50_p75=[round(x, 2) for x in pc(o['s'].k_med)],
    anticipo_s_p25_p50_p75=[round(x, 2) for x in pc(o['s'].anticipo_s)],
    stato='pochi dati (n=11, 8 con v>8 km/h): indicativo, NON adottare come soglia')
json.dump(prop, open('config/soglie_attuazione_001.PROPOSTA_guide.json', 'w'), indent=1, ensure_ascii=False)

# ---- numeri per il rapporto
b = o['b']; s = o['s']; v = o['v']
L = []
def w(x=''): L.append(x)
w('# Soglie dalle guide di #001 - 2026-11-12 (event-miner)')
w()
w('Script: training/eventi/soglie_dalle_guide.py (estrazione) + soglie_report.py (tabelle, proposta). Eventi: training/eventi/out_guide_20261112_c0.3477/ e _c0.3374/ (frenate.csv, sterzate.csv, velocita_1hz.csv, segmenti.json). Percezione solo letta da training/depth/out_20261112_v9 (tracks_20261109_094146.pkl).')
w('Ruota: numeri con 0.3477 m/giro enc (proposta, L0.encoder_ruota_20261112) e tra parentesi con 0.3374 (in uso). Differenza: velocita e decel -3% con 0.3374.')
w()
w('## 0. Cosa sono davvero le "guide": LIMITE GROSSO sui dati')
w('- Dei 17 CSV sensori 08-11/11 solo 2 hanno la bici in moto con encoder valido: 20261108_160150 e 20261109_085334. Tutti gli altri: ruota ferma (cavalletto/banco) o GPS/encoder incoerenti (11/11: sterzo -1 o 0..16380). Scartati.')
w('- Tratti in moto (|v|>0.5 m/s, >5 s): %d; usati %d (encoder/GPS entro 0.7-1.3). Scartati: 6356 s (spinta calibrazione 10 giri, gps assente), 5617 s (rapporto GPS 1.5), 3 tratti 08/11 senza GPS (fermi / limiter a bici quasi ferma).' % (len(seg), sum(x['usato'] for x in seg)))
dist = sum(x['dist_m'] for x in seg if x['usato']); dl = sum(x['dist_m'] for x in seg if x['usato'] and x['limiter']);
w('- Distanza usata: %.0f m, di cui %.0f m col speed_limiter attivo (servo freno, target 10 km/h, cap 12): in quei tratti velocita e parte delle frenate sono del LIMITER, non di Daniele. Solo %.0f m sono senza limiter (08/11 pomeriggio e 09/11 09:23-09:25), in cui non e dimostrato chi guidava (nessun video di quei tratti).' % (dist, dl, dist - dl))
w('- Percezione: solo il giro 094146 (t 6639-6730 s, 233 m, 90 s a 15 fps). Verifica di Daniele su v9: primo ostacolo con 28 falsi vs 11 veri (regress_v9.json): le distanze Z sotto sono "depth:coarse" e possono essere falsi primo.')
w('- Controlli: v e acc da Savitzky-Golay ord. 2 su cumulativo (v 0.5 s, acc 1.5 s come L0). IMU non usata per la decel: a riposo ay=+0.074 g (offset 0.7 m/s2) e non compensata per il pitch (IMU da -1.6 a -1.8 contro -0.9..-1.2 encoder).')
w()
w('## 1. FRENATE (%d eventi decel >=0.3 m/s2 per >=1 s, dv>=0.5 m/s)' % len(b))
cl = b.classe.value_counts().to_dict()
w('Classi: stop_umano=%d (v finale <2 km/h: il limiter rilascia sotto 8 km/h e non puo fermare), umano=%d (servo <5 gradi: rallentamenti dolci), limiter=%d (servo >=5 gradi e non stop: freno automatico, escluso).' % (cl.get('stop_umano', 0), cl.get('umano', 0), cl.get('limiter', 0)))
w()
w('### 1a. Stop completi di Daniele per fascia di velocita iniziale (0.3477; [0.3374])')
w('| fascia km/h | n (0.3477/0.3374) | v0 p50 | decel media p25/p50/p75 m/s2 | decel picco p25/p50/p75 | durata s p50 | spazio di frenata p25/p50/p75 m | note |')
w('|---|---|---|---|---|---|---|---|')
for r, r2 in zip(o['rows'], o2['rows']):
    note = 'pochi dati: resta segnaposto' if r['n'] < NMIN else ''
    if r['n'] == 0: note = 'nessun evento: resta segnaposto'
    w('| %d | %d/%d | %s | %s [%s] | %s | %s | %s [%s] | %s |' % (r['fascia'], r['n'], r2['n'], f(r['v0'][1:2], 1), f(r['a_mean']), f(r2['a_mean'][1:2]), f(r['a_peak']),
      f(r['dur'][1:2], 1), f(r['sp']), f(r2['sp'][1:2], 1), note))
w('| pooled | %d/%d | - | %s [%s] | %s | %s | %s [%s] | - |' % (len(st), len(st2), f(pc(st.a_mean)), f(pc(st2.a_mean)[1:2]), f(pc(st.a_peak)), f(pc(st.dur_s)[1:2], 1), f(pc(st.sp_m), 1), f(pc(st2.sp_m)[1:2], 1)))
w()
w('Lettura: sono frenate di ROUTINE (picco massimo smussato 2.8 m/s2 a ~12 km/h), non di emergenza. La decel cresce con la velocita (0.4 a 5 km/h, ~1.1 a 12), quindi un solo valore costante e sbagliato. Il massimo del freno idraulico NON e misurato. La decel di 1.5 del segnaposto e sopra la mediana di Daniele (0.68) e il segnaposto frena_entro e PIU CORTO dello spazio che Daniele usa da solo per fermarsi (a 5 km/h: segnaposto 1.84 m totale contro 2.7 m p50 di sola frenata; a 10 km/h 4.46 contro 5.5).')
w('Fit pooled spazio di frenata: sp = %.2f*v %+.2f m (v in m/s, n=%d; residui p75 +%.2f m) [0.3374: %.2f*v %+.2f, +%.2f].' % (beta, gamma, len(st), off, b2, g2, off2))
w()
w('### 1b. Frenate con percezione (finestra v9, 094146, depth:coarse)')
wz = b[b.Z_arc.notna()]
w('| t (s) | classe | v0 km/h | decel media | Z primo ostacolo nell arco (m) | Z dritto | TTC s | note |')
w('|---|---|---|---|---|---|---|---|')
for _, e in wz.iterrows():
    w('| %.0f | %s | %.1f | %.2f | %.1f | %s | %.1f | %s |' % (e.t0, e.classe, e.v0_kmh, e.a_mean, e.Z_arc, ('%.1f' % e.Z_str) if np.isfinite(e.Z_str) else '-', e.ttc, 'possibile falso primo' if e.Z_arc < 2.5 else ''))
sz = wz[wz.classe == 'stop_umano']
w()
w('Stop con percezione: n=%d, Z a inizio frenata %s m (range molto largo), TTC %s s: **pochi dati (n<5): la distanza di inizio frenata resta segnaposto**. Non e dimostrato che Daniele frenasse PER quell ostacolo (nessun caso dubbio aperto): l etichetta intento resta "intent:unknown" salvo conferma.' % (len(sz), f(pc(sz.Z_arc), 1), f(pc(sz.ttc), 1)))
w()
w('## 2. STERZATE (curve con |gz|>22 dps per >=0.5 s a v>1 m/s: n=%d, di cui n=%d a v>8 km/h)' % (len(s), (s.v_kmh > 8).sum()))
w('| indicatore | p25 / p50 / p75 | note |')
w('|---|---|---|')
w('| velocita angolare manubrio picco (deg/s) | %s | |' % f(pc(s.rate_peak), 0))
w('| ampiezza manubrio nella curva (deg dal punto di partenza) | %s | |' % f(pc(s.amp_deg), 0))
w('| curvatura gz/v (1/m) | %s | raggio ~%.1f m al p50 |' % (f(pc(s.k_med)), 1 / pc(s.k_med)[1]))
w('| gz picco (deg/s) | %s | |' % f(pc(s.gz_peak), 0))
w('| anticipo: manubrio parte prima di gz>22 (s) | %s | |' % f(pc(s.anticipo_s)))
w()
w('Curvatura contro velocita (n piccolo): ' + '; '.join('v=%.0f km/h k=%.2f rate=%.0f deg/s' % (e.v_kmh, e.k_med, e.rate_peak) for _, e in s.sort_values('v_kmh').iterrows()) + '.')
w('Lettura: curvatura scende con la velocita (0.38 a 4 km/h, 0.14 a 12): a 12-13 km/h Daniele non supera ~0.15 1/m (raggio ~7 m) e ~24-31 deg/s. La velocita angolare del manubrio piu alta (110 deg/s) e a 8 km/h in un evento a bassa velocita.')
w('Velocita del manubrio su tutto il moto (campioni 1 Hz, |steer_rate|, deg/s) p50/p90 e |angolo| p50/p90 per fascia:')
w('| fascia km/h | n | rate p50/p90 | angolo p50/p90 |')
w('|---|---|---|---|')
for lo, hi, c in [(0, 6.5, 5), (6.5, 9, 8), (9, 11, 10), (11, 13.5, 12), (13.5, 99, 15)]:
    g = v[(v.v_kmh >= lo) & (v.v_kmh < hi)]
    w('| %d | %d | %.1f/%.1f | %.1f/%.1f |' % (c, len(g), np.nanpercentile(g.steer_rate, 50), np.nanpercentile(g.steer_rate, 90), np.nanpercentile(g.steer_deg, 50), np.nanpercentile(g.steer_deg, 90)))
w()
w('Anticipo rispetto a curva/ostacolo: il manubrio parte ~%.1f s (p50) prima che gz superi 22 dps. Con percezione solo 3 curve (Z a inizio sterzata %s m): **pochi dati**, l anticipo "quanto prima dell ostacolo" non e stimabile.' % (pc(s.anticipo_s)[1], f(pc(s.Z_arc_inizio), 1)))
w('Nota: centro sterzo 6606 e finecorsa del 09/11 16:05 (dopo la guida di 09:46): ripetibilita centro +-1.27 gradi; valgono fino al rimontaggio del 12/11.')
w()
w('## 3. VELOCITA tenute (campioni a 1 Hz in moto, km/h; p25/p50/p75)')
w('| contesto | n | senza limiter (FREE/off) | n | limiter attivo (HYST/RELEASE/OVER) |')
w('|---|---|---|---|---|')
vl = v.lim.isin(['HYST', 'RELEASE', 'OVER'])
for ctx in ('rettilineo', 'curva', 'altro'):
    a_ = v[(v.ctx == ctx) & ~vl].v_kmh; b_ = v[(v.ctx == ctx) & vl].v_kmh
    w('| %s | %d | %s | %d | %s |' % (ctx, len(a_), f(pc(a_), 1), len(b_), f(pc(b_), 1)))
nz = v[v.Z_arc.notna()]
w('| vicino a ostacolo (Z arco <10 m, v9) | %d | - | %d | %s |' % (0, int((nz.Z_arc < 10).sum()), f(pc(nz[nz.Z_arc < 10].v_kmh), 1)))
w('| lontano (Z arco >=10 m, v9) | 0 | - | %d | %s |' % (int((nz.Z_arc >= 10).sum()), f(pc(nz[nz.Z_arc >= 10].v_kmh), 1)))
w()
w('Lettura: le velocita "con limiter" (mediana ~13.5 km/h in rettilineo) sono il cap del limiter, non scelta di Daniele; le velocita libere (mediana ~5-6 km/h) sono il comportamento di Daniele sotto 8 km/h, dove il limiter non interviene. Nel giro 094146 (limiter attivo) i campioni vicino/lontano non mostrano differenza leggibile perche il cap domina: contesto "vicino a persone" non separabile (n troppo basso e limiter confondente).')
w()
w('## 4. MARGINI LATERALI')
w('Nel v9 (tracks pkl) non ci sono distanze dai bordi (solo X laterale degli oggetti e flag in_arc/in_str): **in arrivo da v10**. bordo_margine resta segnaposto.')
w()
w('## 5. Tabella: segnaposto vs proposta dalle guide')
w('Fuori 5-12 km/h il valore e max(segnaposto, estrapolazione del fit) per non rompere la monotonia. Colonne come config. frena_entro = spazio frenata Daniele p75 (fit) + v*0.5 s + 0.5 m (latenza e cuscinetto segnaposto: non vengono dalle guide). rallenta = max(1.5*frena, v*3 s) (formula, non guide).')
w('| km/h | frena_entro segnaposto | frena_entro PROPOSTA | rallenta segnaposto | rallenta PROPOSTA | bordo_margine | origine |')
w('|---|---|---|---|---|---|---|')
for r, n_ in zip(base['tabella_per_velocita'], tab_new):
    w('| %d | %.2f | %.2f | %.2f | %.2f | %.2f (segnaposto, v10) | %s |' % (r['kmh'], r['frena_entro_m'], n_['frena_entro_m'], r['rallenta_entro_m'], n_['rallenta_entro_m'], r['bordo_margine_m'], n_['origine']))
w()
w('Decel / sterzo proposti (non in tabella per velocita): decel_frenata_ms2 segnaposto 1.5 (resta nel JSON); decel dalle guide p25 %.2f m/s2 (campo decel_guide_p25_ms2, solo riferimento); velocita manubrio picco in curva p50 %.0f deg/s (p25-p75 %.0f-%.0f), curvatura max osservata a 12 km/h ~0.15 1/m: **pochi dati (n=11), non adottati come soglia**.' % (dec_p25, pc(s.rate_peak)[1], pc(s.rate_peak)[0], pc(s.rate_peak)[2]))
w()
w('## 6. Casi dove i dati non bastano')
w('- fascia 15 km/h e oltre: nessuno stop (solo frenate parziali del limiter): segnaposto. 3 km/h, 20, 25: segnaposto.')
w('- fasce 8, 10, 12: n=2/4/4 (<5): proposta da fit pooled, DEBOLE.')
w('- Frenate di emergenza e decel massima: non presenti (picco smussato 2.8 m/s2); il segnaposto non puo essere confermato ne smentito per l emergenza.')
w('- Distanza ostacolo a inizio frenata / TTC / anticipo sterzata: n<5 con percezione, falsi primo noti.')
w('- Guide "pure" di Daniele senza limiter: ~%.0f m soli. Servono altre uscite con il limiter spento (o velocita sopra 10 km/h) per le fasce 12-15 e per gli stop da 15.' % (dist - dl))
w('- Logica: nessun evento ha intento verificato; Z accoppiata solo per coincidenza temporale (intent:unknown).')
open('agents/rapporti/soglie_dalle_guide_001_20261112.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
