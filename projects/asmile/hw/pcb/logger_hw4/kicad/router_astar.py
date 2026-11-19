"""Router A* a griglia per il logger HW4 (Python di KiCad). Usato da premipi.py (coppie MIPI prima di Freerouting) e da
completa.py (collegamenti che Freerouting lascia aperti).
Griglia 0,05 mm, F.Cu/B.Cu, vie 0,6/0,3 mm (costo alto), mosse a 8 direzioni con penalità di curva, ostacoli = rame di
altre net (+ isolamento), zone vietate (anche dentro i footprint), bordo. Le piste messe diventano subito ostacoli.
"""
import heapq, math
import pcbnew

MM, TO = pcbnew.FromMM, pcbnew.ToMM
G = 0.05
VIA_D, VIA_H = 0.6, 0.3
COSTO_VIA = 40


def carica_ostacoli(b):
    rame = []                                       # (net, strati {0=F,1=B}, tipo, geometria)
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            r = (TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom()))
            th = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            lay = {0, 1} if th else ({0} if pad.IsOnLayer(pcbnew.F_Cu) else {1})
            rame.append((pad.GetNetname(), lay, "r", r))
    tr = b.Tracks()
    for i in range(tr.size()):
        t = tr[i]
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            rame.append((t.GetNetname(), {0, 1}, "c", (TO(p.x), TO(p.y), VIA_D / 2)))
        elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            s, e = t.GetStart(), t.GetEnd()
            rame.append((t.GetNetname(), {0} if t.GetLayer() == pcbnew.F_Cu else {1}, "s",
                         (TO(s.x), TO(s.y), TO(e.x), TO(e.y), TO(t.GetWidth()) / 2)))
    vietate = []
    zz = list(b.Zones())
    for fp in b.GetFootprints():
        zz += list(fp.Zones())
    for z in zz:
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            vietate.append((TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom())))
    return rame, vietate


def _dist(o, x, y):
    if o[2] == "r":
        r = o[3]
        return math.hypot(max(r[0] - x, 0, x - r[2]), max(r[1] - y, 0, y - r[3]))
    if o[2] == "c":
        return math.hypot(x - o[3][0], y - o[3][1]) - o[3][2]
    ax, ay, cx, cy, hw = o[3]
    vx, vy = cx - ax, cy - ay
    l2 = vx * vx + vy * vy
    t = 0 if l2 == 0 else max(0, min(1, ((x - ax) * vx + (y - ay) * vy) / l2))
    return math.hypot(x - ax - t * vx, y - ay - t * vy) - hw


def instrada(b, rame, vietate, net, p0, p1, pista=0.15, iso=0.15, margine=6.0, blocca=False, solo_strato=None):
    """p0, p1 = (x, y, strato). Ritorna (ok, lunghezza_mm, n_vie)."""
    (x0, y0, l0), (x1, y1, l1) = p0, p1
    bx0, by0 = min(x0, x1) - margine, min(y0, y1) - margine
    nx, ny = int((abs(x1 - x0) + 2 * margine) / G) + 1, int((abs(y1 - y0) + 2 * margine) / G) + 1
    wx0, wy0, wx1, wy1 = bx0 - 2, by0 - 2, bx0 + nx * G + 2, by0 + ny * G + 2

    def dentro(o):                                   # solo gli ostacoli nella finestra (velocità)
        if o[2] == "r":
            r = o[3]
            return r[2] > wx0 and r[0] < wx1 and r[3] > wy0 and r[1] < wy1
        if o[2] == "c":
            return wx0 < o[3][0] < wx1 and wy0 < o[3][1] < wy1
        ax, ay, cx, cy, hw = o[3]
        return max(ax, cx) > wx0 and min(ax, cx) < wx1 and max(ay, cy) > wy0 and min(ay, cy) < wy1
    loc = [o for o in rame if o[0] != net and dentro(o)]
    tutte_vie = [o for o in rame if o[2] == "c" and dentro(o)]     # foro-foro vale anche per la stessa net
    iso_g = iso + 0.02                               # margine per l'arrotondamento della griglia
    cache = {}

    def libero(i, j, lay, raggio):
        k = (i, j, lay, raggio)
        if k in cache:
            return cache[k]
        x, y = bx0 + i * G, by0 + j * G
        ok = 0.8 < x < 249.2 and 0.8 < y < 49.2
        if ok and (lay == 2 or lay == 0):
            ok = not any(v[0] - raggio < x < v[2] + raggio and v[1] - raggio < y < v[3] + raggio for v in vietate)
        if ok and lay == 2:                           # via: centro ≥ 0,6 mm da ogni altra via (foro-foro ≥ 0,3 mm)
            ok = all(math.hypot(x - o[3][0], y - o[3][1]) >= 0.6 for o in tutte_vie)
        if ok:
            for o in loc:
                if (lay == 2 or lay in o[1]) and _dist(o, x, y) < raggio + iso_g:
                    ok = False
                    break
        cache[k] = ok
        return ok

    def cella(x, y):
        return int(round((x - bx0) / G)), int(round((y - by0) / G))

    s0, s1 = cella(x0, y0), cella(x1, y1)
    start, goal = (s0[0], s0[1], l0), (s1[0], s1[1], l1)
    vicino = lambda i, j, a: abs(i - a[0]) + abs(j - a[1]) <= 6
    h = lambda n: G * math.hypot(n[0] - goal[0], n[1] - goal[1])
    curva = 0.6 * G * 4
    aperti = [(h(start), 0.0, start, None)]
    da, costo, direz = {}, {start: 0.0}, {start: None}
    trovato = None
    mosse = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    while aperti:
        f, c, n, padre = heapq.heappop(aperti)
        if n in da:
            continue
        da[n] = padre
        if n == goal:
            trovato = n
            break
        i, j, lay = n
        for di, dj in mosse:
            m = (i + di, j + dj, lay)
            if not (0 <= m[0] < nx and 0 <= m[1] < ny) or m in da:
                continue
            if not (vicino(m[0], m[1], start) or vicino(m[0], m[1], goal)) and not libero(m[0], m[1], lay, pista / 2):
                continue
            nc = c + G * math.hypot(di, dj) + (curva if direz.get(n) not in (None, (di, dj)) else 0)
            if nc < costo.get(m, 1e9):
                costo[m] = nc
                direz[m] = (di, dj)
                heapq.heappush(aperti, (nc + h(m), nc, m, n))
        if solo_strato is None:
            m = (i, j, 1 - lay)
            if m not in da and libero(i, j, 2, VIA_D / 2):
                nc = c + G * COSTO_VIA
                if nc < costo.get(m, 1e9):
                    costo[m] = nc
                    direz[m] = None
                    heapq.heappush(aperti, (nc + h(m), nc, m, n))
    if not trovato:
        return False, 0.0, 0
    cammino = []
    n = trovato
    while n:
        cammino.append(n)
        n = da[n]
    cammino.reverse()
    nodi = [cammino[0]]
    for k in range(1, len(cammino) - 1):
        a, m_, c_ = cammino[k - 1], cammino[k], cammino[k + 1]
        if a[2] != m_[2] or m_[2] != c_[2] or (m_[0] - a[0], m_[1] - a[1]) != (c_[0] - m_[0], c_[1] - m_[1]):
            nodi.append(m_)
    nodi.append(cammino[-1])
    netinfo = b.FindNet(net)
    # le estremità vanno esattamente sul punto chiesto (centro del pad), non sulla cella
    coord = [(bx0 + q[0] * G, by0 + q[1] * G) for q in nodi]
    coord[0], coord[-1] = (x0, y0), (x1, y1)
    n_v = 0
    for k in range(1, len(nodi)):
        a, c_ = nodi[k - 1], nodi[k]
        pa = pcbnew.VECTOR2I(MM(coord[k - 1][0]), MM(coord[k - 1][1]))
        pc = pcbnew.VECTOR2I(MM(coord[k][0]), MM(coord[k][1]))
        if a[2] != c_[2]:
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pa)
            v.SetWidth(MM(VIA_D))
            v.SetDrill(MM(VIA_H))
            v.SetNet(netinfo)
            v.SetLocked(blocca)
            b.Add(v)
            rame.append((net, {0, 1}, "c", (TO(pa.x), TO(pa.y), VIA_D / 2)))
            tutte_vie.append(rame[-1])
            n_v += 1
            continue
        if pa == pc:
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pa)
        t.SetEnd(pc)
        t.SetWidth(MM(pista))
        t.SetLayer(pcbnew.F_Cu if a[2] == 0 else pcbnew.B_Cu)
        t.SetNet(netinfo)
        t.SetLocked(blocca)
        b.Add(t)
        rame.append((net, {a[2]}, "s", (TO(pa.x), TO(pa.y), TO(pc.x), TO(pc.y), pista / 2)))
    lung = sum(math.hypot(coord[k][0] - coord[k - 1][0], coord[k][1] - coord[k - 1][1])
               for k in range(1, len(nodi)) if nodi[k][2] == nodi[k - 1][2])
    return True, lung, n_v
