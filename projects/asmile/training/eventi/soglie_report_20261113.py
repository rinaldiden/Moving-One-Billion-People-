#!/usr/bin/env python3
"""soglie_report_20261113.py — aggiorna la PROPOSTA soglie (config/soglie_attuazione_001.PROPOSTA_guide.json, v4) con gli stop puliti del 13/11.
Regole qualita' INVARIATE rispetto a soglie_report.py (riga = max(fit pulito p75, fit coi soli stop verificati GPS, p75 osservato in banda n>=2)
+ v*latenza + cuscinetto; mai sotto il segnaposto; crescente; >=10 km/h segnaposto; qualita per n: solida>=10, media 5-9, debole 2-4, segnaposto 0-1).
Tutto con circ 0.3374 (in uso): gli stop vecchi dello scettico (0.3477) sono riscalati x0.3374/0.3477. Stop 13/11: stop_umano pulita (servo<1, lim_zone<0.2),
tratti con rapporto GPS 0.99-1.03 (encoder coerente -> 'verificati GPS')."""
import json, numpy as np, pandas as pd
O12 = 'training/eventi/out_guide_20261112_c0.3374'; O13 = 'training/eventi/out_guide_20261113'
SCET = 'agents/prove/eventi_scettico_20261112/ev.csv'; NMIN = 5
base = json.load(open('config/soglie_attuazione_001.json')); P = base['parametri']
old = json.load(open('config/soglie_attuazione_001.PROPOSTA_guide.json'))

def band(k):
    for lo, hi, c in [(0, 4, 3), (4, 6.5, 5), (6.5, 9, 8), (9, 11, 10), (11, 13.5, 12), (13.5, 99, 15)]:
        if lo <= k < hi: return c
def pc(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return (np.nan,) * 3 if len(x) == 0 else tuple(np.percentile(x, [25, 50, 75]))
def fit(x):
    v = x.v0_kmh.values / 3.6; A = np.c_[v, np.ones_like(v)]; b, g = np.linalg.lstsq(A, x.sp_m.values, rcond=None)[0]
    return b, g, float(np.percentile(x.sp_m.values - A @ np.array([b, g]), 75))

e = pd.read_csv(SCET); e = e[(e.v1 > -1.0) & (e.v1 < 2) & (e.bomax < 1) & (e.lim < 0.2)].copy()
k = 0.3374 / 0.3477
vec = pd.DataFrame(dict(v0_kmh=e.v0 * k, sp_m=e.sp * k, a_mean=e.am * k, dur_s=e.dur, src='12/11'))
b12 = pd.read_csv(O12 + '/frenate.csv'); v12 = b12[b12.classe == 'stop_umano']
ver12 = pd.DataFrame(dict(v0_kmh=v12.v0_kmh, sp_m=v12.sp_m, a_mean=v12.a_mean, dur_s=v12.dur_s, src='12/11'))
b13 = pd.read_csv(O13 + '/frenate.csv'); n13 = b13[(b13.classe == 'stop_umano') & b13.pulita]
new = pd.DataFrame(dict(v0_kmh=n13.v0_kmh, sp_m=n13.sp_m, a_mean=n13.a_mean, dur_s=n13.dur_s, src='13/11'))
st = pd.concat([vec, new], ignore_index=True); st8 = pd.concat([ver12, new], ignore_index=True)
st['fascia'] = [band(x) for x in st.v0_kmh]
print('stop puliti vecchi', len(vec), 'verificati GPS vecchi', len(ver12), 'nuovi 13/11', len(new)); print(new.round(2).to_string())
beta, gamma, off = fit(st); bv, gv, ov = fit(st8)
rows = {fa: st[st.fascia == fa] for fa in (3, 5, 8, 10, 12, 15)}
V2 = {3: (3.45, 5.17), 5: (4.62, 6.92), 8: (6.34, 9.52), 10: (7.51, 11.27), 12: (8.66, 12.98), 15: (10.40, 15.61), 20: (13.57, 20.36), 25: (20.05, 30.08)}
VMAX = float(st.v0_kmh.max()); prev_f = prev_r = 0.0; tab = []
for r in base['tabella_per_velocita']:
    kmh, v = r['kmh'], r['v_ms']; xb = rows.get(kmh, st.iloc[0:0]); n = len(xb)
    lc = v * P['t_latenza_s'] + P['cuscinetto_m']
    f_fit = max(0.0, beta * v + gamma + off) + lc; f_ver = max(0.0, bv * v + gv + ov) + lc
    f_p75 = (float(np.percentile(xb.sp_m, 75)) + lc) if n >= 2 else 0.0
    fe = max(f_fit, f_ver, f_p75)
    ok = kmh < 10
    if ok:
        fr = max(fe, r['frena_entro_m']); rl = max(1.5 * fr, v * P['ttc_avviso_s'], r['rallenta_entro_m'])
    else:
        fr = max(r['frena_entro_m'], V2[kmh][0], fe); rl = max(r['rallenta_entro_m'], V2[kmh][1], 1.5 * fr, v * P['ttc_avviso_s'])
    cls = 'solida' if n >= 10 else 'media' if n >= 5 else 'debole' if n >= 2 else 'segnaposto'
    if not ok: cls = 'segnaposto'
    stato = ('dalle guide: %s (n stop puliti in banda=%d; max di fit %.2f, verificati-GPS %.2f, p75-banda %.2f)' % (cls, n, f_fit, f_ver, f_p75)) if ok else \
        'segnaposto: servono stop >10 km/h senza limiter (max di segnaposto, proposta v2, fit pulito)'
    fr = max(fr, prev_f); rl = max(rl, prev_r, fr); prev_f, prev_r = fr, rl
    tab.append(dict(kmh=kmh, v_ms=v, frena_entro_m=round(fr, 2), rallenta_entro_m=round(rl, 2), bordo_margine_m=r['bordo_margine_m'], origine=stato,
                    solidita=cls, n_banda=n, frenata_guida_p25_p50_p75_m=[round(x, 2) for x in pc(xb.sp_m)] if n else None,
                    origine_bordo='segnaposto: in arrivo da v10'))
assert all(t['frena_entro_m'] >= r['frena_entro_m'] and t['rallenta_entro_m'] >= r['rallenta_entro_m'] for t, r in zip(tab, base['tabella_per_velocita']))
assert all(a['frena_entro_m'] <= b['frena_entro_m'] for a, b in zip(tab, tab[1:]))
prop = json.loads(json.dumps(old))
prop['versione'] = 4; prop['data'] = '2026-11-13'
prop['stato'] = ('PROPOSTA dalle guide di #001 (event-miner 2026-11-13, v4: +%d stop puliti del 13/11), NON validata: la valida Daniele. Dati puliti solo fino a ~9.5 km/h; '
                 'righe >=10 km/h = segnaposto. Frenate di routine (non emergenza). Latenza, cuscinetto, bordi, rallenta = segnaposto.' % len(new))
dp25 = float(np.percentile(st.a_mean, 25))
prop['parametri']['decel_guide_p25_ms2'] = round(dp25, 2)
prop['parametri']['_note']['decel_guide_p25_ms2'] = ('p25 delle decel medie di %d stop completi di Daniele (puliti, pooled, p50 %.2f, p75 %.2f). Cresce con la velocita: solo riferimento.' %
                                                     (len(st), np.percentile(st.a_mean, 50), np.percentile(st.a_mean, 75)))
prop['parametri']['_note']['frena_entro_guide'] = ('distanza di frenata = fit lineare sp=%.2f*v%+.2f (+ offset p75 residui %.2f m) su %d stop; + v*t_latenza + cuscinetto (segnaposto). '
                                                   'Ruota 0.3374 m/giro enc (stop 12/11 riscalati da 0.3477).' % (beta, gamma, off, len(st)))
prop['tabella_per_velocita'] = tab
prop['fonte_valori'] = dict(oggi='proposta guide v4', segnaposto_in_uso='config/soglie_attuazione_001.json', validato_da=None, circ_ruota_usata_m_per_giro_enc=0.3374,
                            nota='v3 usava 0.3477 (3% piu lungo, piu prudente); v4 tutto a 0.3374 (calibrata col metro)')
s12 = pd.read_csv(O12 + '/sterzate.csv'); s13 = pd.read_csv(O13 + '/sterzate.csv'); s = pd.concat([s12, s13], ignore_index=True)
prop['sterzo_dalle_guide'] = dict(n_curve=int(len(s)), velocita_angolare_manubrio_picco_degs_p25_p50_p75=[round(x, 1) for x in pc(s.rate_peak)],
    ampiezza_deg_p25_p50_p75=[round(x, 1) for x in pc(s.amp_deg)], curvatura_1_su_m_p25_p50_p75=[round(x, 2) for x in pc(s.k_med)],
    anticipo_s_p25_p50_p75=[round(x, 2) for x in pc(s.anticipo_s)], n_di_cui_13_11=int(len(s13)),
    stato='pochi dati (n=%d curve con ampiezza manubrio >=5 gr, %d del 13/11 con centro 4112): indicative, NON soglie' % (len(s), len(s13)))
json.dump(prop, open('config/soglie_attuazione_001.PROPOSTA_guide.json', 'w'), indent=1, ensure_ascii=False)
print('fit sp=%.2f*v%+.2f off %.2f n=%d | verificati sp=%.2f*v%+.2f off %.2f n=%d | vmax pulito %.1f' % (beta, gamma, off, len(st), bv, gv, ov, len(st8), VMAX))
for t in tab: print(t['kmh'], t['frena_entro_m'], t['rallenta_entro_m'], t['n_banda'], t['solidita'])
print('vecchia v3:', [(t['kmh'], t['frena_entro_m'], t['n_banda']) for t in old['tabella_per_velocita']][:5])
print('decel pooled p25/50/75', pc(st.a_mean)); print('sterzo', prop['sterzo_dalle_guide'])
