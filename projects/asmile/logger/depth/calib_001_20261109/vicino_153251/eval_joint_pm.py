#!/usr/bin/env python3
"""eval_joint_pm.py SCRATCH FIT.json|before  -> tabella errori su soste tenute fuori + dy per zona (mattina/pomeriggio)"""
import sys, json, numpy as np
SPd, FJ = sys.argv[1:3]; sys.argv = ['x', SPd, 'pm', '/dev/null']
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import fit_joint_pm as F
if FJ == 'before':
    j = json.load(open('/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json'))['fit_params']
    q = [*j['rx_ry_rz_deg'], j['fL'], j['fR'], j['k1_L'], j['k2'], j['k1_R'], j['k2'], j['dcx_right_px'], j['dcy_right_px'], 0, 0, 0, 0, 0, 0, 0.03]
else: q = json.load(open(FJ))['x']
Z0 = (q[19] if len(q) > 19 else 0.0); Z0M = (q[18] if len(q) > 18 else 0.0); DYO = (q[20] if len(q) > 20 else 0.0)
p = np.array(q[:17]); cache = F.rect(p); B = F.B
st = [(r, *F.board_stats(p, r, cache)) for r in F.BR]
SQ = np.median([r['nom']/tz for r, d, tz, dy, tx in st if r['pos'] == 'C' and r['fit']])
print('SQ da soste centrali fit = %.5f m' % SQ)
print('POMERIGGIO  nom pos  ruolo  Zstereo  Zpnp/metro  err%  dy_px')
for r, d, tz, dy, tx in st:
    Zs = p[3]*B/d; Zr = r['nom'] if r['pos'] == 'C' else SQ*tz
    print('%4.0f m %3s %5s  Zs=%.3f ref=%.3f  %+6.2f%%  dy=%+.2f  X=%+.2f' % (r['nom'], r['pos'], 'FIT' if r['fit'] else 'HOLD', Zs, Zr, 100*(Zs/Zr-1), dy, tx*SQ))
print('MATTINA (metro)')
for i, m in enumerate(F.M):
    d = F.tape_d(p, m, cache); Zs = p[3]*B/d
    print('%4.0f m %s  Zs=%.3f  %+6.2f%%' % (m['Z'], 'HOLD' if i in F.MHOLD else 'fit ', Zs, 100*(Zs/m['Z']-1)))
def zones(S1, S2, name, far=False):
    u1, u2 = F.proj(p, S1, S2, cache); dy = u1[:, 1]-u2[:, 1]; d = u1[:, 0]-u2[:, 0]; ok = abs(dy) < 12
    if far: ok &= d < 25
    print(name, 'n=%d  mediana|dy|=%.2f p95|dy|=%.2f  med(dy)=%+.2f' % (ok.sum(), np.median(abs(dy[ok])), np.percentile(abs(dy[ok]), 95), np.median(dy[ok])))
    x = S1[:, 0]; y = S1[:, 1]
    for rr in range(3):
        row = []
        for cc in range(3):
            m = ok & (x >= cc*W/3) & (x < (cc+1)*W/3) & (y >= rr*H/3) & (y < (rr+1)*H/3)
            row.append('%+5.2f/%4.1f[%5d]' % (np.median(dy[m]), np.percentile(abs(dy[m]), 95), m.sum()) if m.sum() > 30 else '      --      ')
        print('   ', '  '.join(row))
W, H = 1280, 800
for k in F.MOV: zones(F.MOV[k][0], F.MOV[k][1], 'MATTINA moto '+k)
zones(F.PM[0], F.PM[1], 'POMERIGGIO sfondo (raw, tutte le zone) ')
