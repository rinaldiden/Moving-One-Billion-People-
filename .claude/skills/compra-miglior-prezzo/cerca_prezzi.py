#!/usr/bin/env python3
"""
cerca_prezzi.py — trova dove comprare lo STESSO pezzo al prezzo più basso, spedizione compresa,
e accorpa gli ordini. Il doppio lo usa da qualsiasi progetto (skill `compra-miglior-prezzo`).

Fonti: Amazon.it · AliExpress (it) · web (DuckDuckGo → pagine prodotto con prezzo in JSON-LD).
Browser: Google Chrome vero via Playwright, HEADLESS (non ruba lo schermo), profilo dedicato
~/.claude_pw_shop (separato da ~/.claude_pw_profile, così non c'è conflitto di lock).

Uso (python con playwright: ~/.asmile_depth_venv/bin/python):
  cerca_prezzi.py cap 23037                        # una volta: CAP di consegna su Amazon (Tirano)
  cerca_prezzi.py cerca "ADS1115" --deve ADS1115 --escludi IDGSR,chip --qty 1
  cerca_prezzi.py bom lista.csv --out risultati/   # tutta una lista → offerte.json + carrello.md
  cerca_prezzi.py carrello risultati/offerte.json  # ricalcola solo l'accorpamento

lista.csv: id,gruppo,qty,query,deve,escludi,note   (deve/escludi: token separati da | )

NON compra nulla. Prepara la lista; l'acquisto parte solo con l'ok di Daniele.
"""
import argparse, csv, itertools, json, os, re, sys, time, urllib.parse
from datetime import date

PROFILE = os.path.expanduser("~/.claude_pw_shop")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# Regole di spedizione (verificate a mano 2026-11-14, da ricontrollare se cambiano)
AMAZON_SOGLIA_GRATIS = 39.0      # ordini spediti da Amazon, cliente non Prime
AMAZON_SPED_STD = 4.99           # sotto soglia, non Prime (stima; il carrello reale fa fede)
ALI_CHOICE_SOGLIA = 10.0         # "Spedizione gratuita da 10€" = articoli Choice accorpati
ALI_CHOICE_SPED = 1.99           # sotto soglia Choice (stima)
ALI_IGNOTA = 2.50                # card senza info spedizione: stima prudente, marcata
WEB_SPED_STD = 6.90              # negozio web senza soglia letta: stima corriere IT, marcata
# Distributori professionali: prezzi in pagina spesso SENZA IVA, spedizione cara sotto soglia
DISTRIBUTORI = {"digikey": (50.0, 18.0), "mouser": (50.0, 20.0), "farnell": (40.0, 9.0),
                "rs-online": (50.0, 9.95), "lcsc": (None, 15.0)}
IVA = 1.22

# ---------------------------------------------------------------- parsing comune

def euro(s):
    """'1.234,56 €' / '2,98€' / '€ 3.05' → float."""
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})|\d+(?:[.,]\d{1,2})?)\s*€|€\s*(\d+(?:[.,]\d{1,2})?)", s or "")
    if not m:
        return None
    v = m.group(1) or m.group(2)
    if "," in v:
        v = v.replace(".", "").replace(" ", "").replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def pezzi_conf(titolo):
    """Quanti pezzi nella confezione: '3 Moduli', '5PCS', '10 pezzi', 'confezione da 2'."""
    t = titolo.lower()
    t = re.sub(r"\b\d+(?:\s*[-~/]\s*\d+)+\s*(?:pz|pcs|pc|pezzi)\b", " ", t)   # "1-10 pezzi", "2/5/10pcs" = varianti
    pats = [r"(\d+)\s*(?:pz|pcs|pc|pezzi|pieces|moduli|unità|units|x)\b",
            r"confezione da\s*(\d+)", r"set di\s*(\d+)", r"pack of\s*(\d+)", r"lotto(?: di)?\s*(\d+)"]
    for p in pats:
        m = re.search(p, t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 500:
                return n
    return 1


def coerente(titolo, deve, escludi):
    """Stesso prodotto? Tutti i token 'deve' presenti, nessun 'escludi'. Confronto sul meccanismo, non sul nome."""
    t = titolo.lower()
    for d in deve:
        alts = [a.strip().lower() for a in d.split("/") if a.strip()]
        if alts and not any(a in t for a in alts):
            return False, f"manca '{d}'"
    for e in escludi:
        if e and e.lower() in t:
            return False, f"contiene '{e}'"
    return True, ""


def voto(s):
    m = re.search(r"\b([1-5][.,]\d)\b", s or "")
    return float(m.group(1).replace(",", ".")) if m else None

# ---------------------------------------------------------------- browser

class Browser:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            PROFILE, channel="chrome", headless=True, locale="it-IT", user_agent=UA,
            args=["--disable-blink-features=AutomationControlled"])

    def apri(self, url, attesa=5, scroll=True):
        pg = self.ctx.new_page()
        try:
            pg.goto(url, timeout=45000, wait_until="domcontentloaded")
            time.sleep(attesa)
            if scroll:
                pg.mouse.wheel(0, 3000)
                time.sleep(1.5)
        except Exception as e:
            print(f"   ! {url[:80]}: {e}", file=sys.stderr)
        return pg

    def chiudi(self):
        self.ctx.close()
        self._pw.stop()

# ---------------------------------------------------------------- Amazon

def amazon_cerca(b, query, n=16):
    pg = b.apri("https://www.amazon.it/s?k=" + urllib.parse.quote_plus(query))
    cards = pg.evaluate("""() => [...document.querySelectorAll('div[data-component-type=s-search-result]')].map(c => ({
        asin: c.dataset.asin, testo: c.innerText,
        titolo: (c.querySelector('h2') || {}).innerText || '',
        prezzo: (c.querySelector('.a-price:not(.a-text-price) .a-offscreen') || {}).textContent || '',
        recensioni: (c.querySelector('[aria-label*="valutazion"], span.s-underline-text') || {}).innerText || ''}))""")
    pg.close()
    out = []
    for c in cards[:n]:
        if not c["asin"]:
            continue
        txt = c["testo"]
        sped = None
        if re.search(r"consegna gratuita", txt, re.I):
            sped = "gratis_amazon"          # gratis con Prime o sopra soglia
        m = re.search(r"consegna a\s*([\d.,]+\s*€)", txt, re.I)
        if m:
            sped = euro(m.group(1))
        rec = re.sub(r"[^\d]", "", c["recensioni"]) or None
        out.append({
            "fonte": "amazon", "id": c["asin"], "titolo": c["titolo"].strip(),
            "url": f"https://www.amazon.it/dp/{c['asin']}", "prezzo": euro(c["prezzo"]),
            "spedizione": sped, "voto": voto(txt), "n_recensioni": int(rec) if rec else None,
            "sponsorizzato": "Sponsorizzato" in txt, "primo_ordine": "primo ordine" in txt,
        })
    return out


def amazon_verifica(b, off):
    """Apre la scheda: chi spedisce, chi vende, % feedback del venditore."""
    pg = b.apri(off["url"], attesa=4, scroll=False)
    d = pg.evaluate("""() => ({
        bb: (document.querySelector('#tabular-buybox, #offerDisplayFeatures_desktop, #merchantInfoFeature_feature_div') || {}).innerText || '',
        cons: (document.querySelector('#deliveryBlockMessage, #mir-layout-DELIVERY_BLOCK') || {}).innerText || '',
        prezzo: (document.querySelector('#corePrice_feature_div .a-offscreen, #apex_desktop .a-offscreen') || {}).textContent || '',
        venditore: (document.querySelector('#sellerProfileTriggerId') || {}).href || ''})""")
    pg.close()
    bb = d["bb"]
    m_sp = re.search(r"Spedizione\s*\n\s*(.+)", bb)
    m_ve = re.search(r"Venditore\s*\n\s*(.+)", bb)
    off["spedito_da"] = m_sp.group(1).strip() if m_sp else None
    off["venduto_da"] = m_ve.group(1).strip() if m_ve else None
    off["consegna"] = d["cons"].split("Maggiori")[0].strip()[:160]
    if euro(d["prezzo"]):
        off["prezzo"] = euro(d["prezzo"])
    m = re.search(r"consegna a\s*([\d.,]+\s*€)", d["cons"], re.I)
    if m:
        off["spedizione"] = euro(m.group(1))
    elif re.search(r"gratuita", d["cons"], re.I):
        off["spedizione"] = "gratis_amazon"
    if d["venditore"]:
        pv = b.apri(d["venditore"], attesa=3, scroll=False)
        t = pv.inner_text("body")
        pv.close()
        m = re.search(r"(\d{1,3})\s*%\s*positiv\w*[^\n(]*\(?\s*([\d.]+)\s*valutazion", t, re.I)
        if m:
            off["venditore_positivo_pct"] = int(m.group(1))
            off["venditore_valutazioni"] = int(m.group(2).replace(".", ""))
    off["verificato"] = f"scheda {date.today()}"
    return off

# ---------------------------------------------------------------- AliExpress

def ali_cerca(b, query, n=20, da_ue=False):
    url = "https://it.aliexpress.com/w/wholesale-" + urllib.parse.quote(query.replace(" ", "-")) + ".html"
    if da_ue:
        url += "?shipFromCountry=IT"
    pg = b.apri(url, attesa=6)
    cards = pg.evaluate("""() => { const seen = new Set(); const out = [];
        for (const a of document.querySelectorAll('a[href*="/item/"]')) {
          const h = a.href.split('?')[0]; if (seen.has(h)) continue; seen.add(h);
          out.push({url: h, testo: a.innerText}); }
        return out; }""")
    pg.close()
    out = []
    for c in cards[:n]:
        righe = [r.strip() for r in c["testo"].split("\n") if r.strip()]
        if not righe:
            continue
        txt = c["testo"]
        prezzi = [euro(r) for r in righe if "€" in r and not re.search(r"risparmi|30 giorni|ognuno|da 10", r, re.I)]
        prezzi = [p for p in prezzi if p]
        sped = None
        m = re.search(r"spedizione:?\s*([\d.,]+\s*€)", txt, re.I)
        if m:
            sped = euro(m.group(1))
        elif re.search(r"spedizione gratuita da\s*10", txt, re.I):
            sped = "choice_10"
        elif re.search(r"spedizione gratuita", txt, re.I):
            sped = 0.0
        m_v = re.search(r"([\d.]+\+?|\+?[\d,]+\s*mila)\s*venduto", txt)
        venduti = None
        if m_v:
            s = m_v.group(1).replace("+", "").replace(".", "")
            venduti = int(float(s.replace("mila", "").replace(",", ".").strip()) * (1000 if "mila" in s else 1))
        m_id = re.search(r"/item/(\d+)", c["url"])
        out.append({
            "fonte": "aliexpress", "id": m_id.group(1) if m_id else c["url"], "titolo": righe[0],
            "url": c["url"], "prezzo": prezzi[0] if prezzi else None, "spedizione": sped,
            "voto": voto(txt), "venduti": venduti, "choice": sped == "choice_10",
            "da_italia": da_ue,
        })
    return out

# ---------------------------------------------------------------- web (altri negozi)

ESCLUDI_DOMINI = ("amazon.", "aliexpress.", "duckduckgo.", "youtube.", "wikipedia.", "reddit.", "facebook.",
                  "pinterest.", "temu.", "alibaba.", "instructables.", "github.")


def web_cerca(b, query, n_pagine=6):
    pg = b.apri("https://html.duckduckgo.com/html/?kl=it-it&q=" + urllib.parse.quote_plus(query + " prezzo acquista"),
                attesa=2, scroll=False)
    links = pg.evaluate("""() => [...document.querySelectorAll('.result a.result__a')].map(a => a.href)""")
    pg.close()
    urls = []
    for l in links:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(l).query).get("uddg")
        u = q[0] if q else l
        if not any(d in u for d in ESCLUDI_DOMINI) and u not in urls:
            urls.append(u)
    out = []
    for u in urls[:n_pagine]:
        pg = b.apri(u, attesa=3, scroll=False)
        try:
            d = pg.evaluate("""() => ({titolo: document.title,
                ld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent),
                meta: (document.querySelector('meta[property="product:price:amount"], meta[itemprop=price]') || {}).content || '',
                testo: document.body ? document.body.innerText.slice(0, 20000) : ''})""")
        except Exception:
            pg.close()
            continue
        pg.close()
        prezzo, nome, disp = None, d["titolo"], None
        for raw in d["ld"]:
            try:
                j = json.loads(raw)
            except Exception:
                continue
            for node in _nodi(j):
                if str(node.get("@type", "")).lower() in ("product", "['product']"):
                    nome = node.get("name", nome)
                    offs = node.get("offers") or {}
                    offs = offs if isinstance(offs, list) else [offs]
                    for o in offs:
                        p = o.get("price") or o.get("lowPrice")
                        if p and str(o.get("priceCurrency", "EUR")).upper() == "EUR":
                            prezzo = float(str(p).replace(",", "."))
                            disp = str(o.get("availability", "")).split("/")[-1] or None
                            break
        if prezzo is None and d["meta"]:
            try:
                prezzo = float(d["meta"].replace(",", "."))
            except ValueError:
                pass
        if prezzo is None:
            continue
        soglia = None
        m = re.search(r"spedizione gratuita[^\n.]{0,40}?(?:sopra|oltre|da|per ordini superiori a)\s*(?:i\s*)?€?\s*([\d.,]+)", d["testo"], re.I)
        if m:
            soglia = euro(m.group(1) + "€")
        dom = urllib.parse.urlparse(u).netloc.replace("www.", "")
        dist = next((k for k in DISTRIBUTORI if k in dom), None)
        if dist:                                   # prezzo da listino B2B: aggiungo IVA, soglia nota
            prezzo = round(prezzo * IVA, 2)
            soglia = DISTRIBUTORI[dist][0]
        out.append({"fonte": "web", "negozio": dom, "distributore": dist, "id": u, "titolo": (nome or "").strip()[:200], "url": u,
                    "prezzo": prezzo, "spedizione": None, "soglia_gratis": soglia, "disponibilita": disp})
    return out


def _nodi(j):
    if isinstance(j, list):
        for x in j:
            yield from _nodi(x)
    elif isinstance(j, dict):
        yield j
        for k in ("@graph", "mainEntity", "itemListElement"):
            if k in j:
                yield from _nodi(j[k])

# ---------------------------------------------------------------- valutazione

def costo_unitario(o):
    n = o.get("pezzi_conf") or 1
    return round(o["prezzo"] / n, 3) if o.get("prezzo") else None


def affidabile(o):
    """Filtro fornitore: non il primo della lista, ma chi ha numeri veri dietro."""
    if o["fonte"] == "amazon":
        if o.get("venditore_positivo_pct") is not None and o["venditore_positivo_pct"] < 85:
            return False, "venditore <85% positivo"
        if (o.get("voto") or 0) < 4.0 or (o.get("n_recensioni") or 0) < 10:
            return False, "voto<4 o <10 recensioni"
    if o["fonte"] == "aliexpress":
        if (o.get("voto") or 0) < 4.5 or (o.get("venduti") or 0) < 50:
            return False, "voto<4.5 o <50 venduti"
    return True, ""


def analizza_voce(voce, offerte):
    deve = [t for t in voce.get("deve", "").split("|") if t.strip()]
    escl = [t for t in voce.get("escludi", "").split("|") if t.strip()]
    tenute = []
    for o in offerte:
        if not o.get("prezzo"):
            continue
        ok, why = coerente(o["titolo"], deve, escl)
        o["pezzi_conf"] = pezzi_conf(o["titolo"])
        o["unitario"] = costo_unitario(o)
        aff, why2 = affidabile(o)
        o["scarto"] = why or why2 or ""
        if ok and aff:
            tenute.append(o)
    qty = int(voce.get("qty") or 1)
    for o in tenute:
        conf = max(1, -(-qty // o["pezzi_conf"]))       # confezioni da comprare
        o["confezioni"] = conf
        o["totale_merce"] = round(conf * o["prezzo"], 2)
    tenute.sort(key=lambda o: o["totale_merce"])
    return tenute

# ---------------------------------------------------------------- carrello (accorpamento)

def sped_negozio(fonte_key, righe, prime=False):
    sub = sum(r["totale_merce"] for r in righe)
    if fonte_key == "amazon:amazon":
        return 0.0 if (prime or sub >= AMAZON_SOGLIA_GRATIS) else AMAZON_SPED_STD
    if fonte_key == "aliexpress:choice":
        return 0.0 if sub >= ALI_CHOICE_SOGLIA else ALI_CHOICE_SPED
    tot = 0.0
    for r in righe:                     # spedizioni per riga (marketplace terzi, Ali non-Choice)
        s = r.get("spedizione")
        if isinstance(s, (int, float)):
            tot += s
        elif r["fonte"] == "aliexpress":
            tot += ALI_IGNOTA
    if fonte_key.startswith("web:"):
        soglia = next((r.get("soglia_gratis") for r in righe if r.get("soglia_gratis")), None)
        dist = next((r.get("distributore") for r in righe if r.get("distributore")), None)
        if dist:
            return 0.0 if soglia and sub >= soglia else DISTRIBUTORI[dist][1]
        return 0.0 if soglia and sub >= soglia else WEB_SPED_STD
    return tot


def chiave_negozio(o):
    if o["fonte"] == "amazon":
        s = o.get("spedizione")
        return "amazon:amazon" if s == "gratis_amazon" or (o.get("spedito_da") or "").lower() == "amazon" \
            else f"amazon:{o.get('venduto_da') or o['id']}"
    if o["fonte"] == "aliexpress":
        return "aliexpress:choice" if o.get("choice") else f"aliexpress:{o['id']}"
    return f"web:{o['negozio']}"


def ottimizza(voci, prime=False, k=3):
    """Prova le combinazioni delle k offerte migliori per voce e sceglie il totale (merce+spedizioni) minimo."""
    scelte = [(v, v["offerte"][:k]) for v in voci if v["offerte"]]
    mancanti = [v["id"] for v in voci if not v["offerte"]]
    best, best_tot = None, float("inf")
    spazio = itertools.product(*[opts for _, opts in scelte]) if scelte else [()]
    for combo in itertools.islice(spazio, 200000):
        per_neg = {}
        for o in combo:
            per_neg.setdefault(chiave_negozio(o), []).append(o)
        tot = sum(o["totale_merce"] for o in combo) + sum(sped_negozio(kk, rr, prime) for kk, rr in per_neg.items())
        if tot < best_tot:
            best, best_tot = combo, tot
    ordini = {}
    for (v, _), o in zip(scelte, best or ()):
        ordini.setdefault(chiave_negozio(o), []).append((v, o))
    return ordini, round(best_tot, 2) if best else 0.0, mancanti


def scrivi_carrello(voci, path_md, titolo, prime=False):
    gruppi = sorted({v.get("gruppo", "base") for v in voci})
    L = [f"# Carrello proposto — {titolo}", "",
         f"Generato da `cerca_prezzi.py` il {date.today()}. Prezzi letti dal web oggi: **il carrello reale fa fede**.",
         f"Amazon: {'Prime' if prime else 'NON Prime'} (soglia gratis {AMAZON_SOGLIA_GRATIS:.0f} €). "
         f"AliExpress Choice: gratis da {ALI_CHOICE_SOGLIA:.0f} € accorpati.", ""]
    scen = {}
    for g in gruppi:
        inclusi = [v for v in voci if v.get("gruppo", "base") in ("base", g)] if g != "base" else \
                  [v for v in voci if v.get("gruppo", "base") == "base"]
        scen[g] = ottimizza(inclusi, prime)
    for g, (ordini, tot, manc) in scen.items():
        L += [f"## Scenario `{g}` — totale stimato **{tot:.2f} €** (merce + spedizioni)", ""]
        for neg, righe in sorted(ordini.items()):
            sped = sped_negozio(neg, [o for _, o in righe], prime)
            L.append(f"### Ordine {neg} — spedizione {sped:.2f} €")
            L.append("| voce | qty | offerta | conf. | € merce | link |")
            L.append("|---|---|---|---|---|---|")
            for v, o in righe:
                L.append(f"| {v['id']} | {v['qty']} | {o['titolo'][:70]} | {o['confezioni']}×{o['pezzi_conf']}pz "
                         f"| {o['totale_merce']:.2f} | [apri]({o['url']}) |")
            L.append("")
        if manc:
            L += [f"⚠️ Nessuna offerta coerente trovata per: {', '.join(manc)} — cercare a mano/altre query.", ""]
    L += ["## Alternative per voce (le 3 migliori dopo i filtri)", ""]
    for v in voci:
        L.append(f"**{v['id']}** ({v.get('gruppo','base')}, qty {v['qty']}) — `{v['query']}`")
        for o in v["offerte"][:3]:
            extra = []
            if o.get("voto"): extra.append(f"★{o['voto']}")
            if o.get("n_recensioni"): extra.append(f"{o['n_recensioni']} rec.")
            if o.get("venduti"): extra.append(f"{o['venduti']} venduti")
            if o.get("venduto_da"): extra.append(f"vende {o['venduto_da']}")
            if o.get("venditore_positivo_pct"): extra.append(f"{o['venditore_positivo_pct']}% pos.")
            L.append(f"- {o['fonte']} {o['totale_merce']:.2f} € ({o['unitario']} €/pz) sped:{o.get('spedizione')} "
                     f"{' · '.join(extra)} — [{o['titolo'][:60]}]({o['url']})")
        if not v["offerte"]:
            L.append("- (nessuna)")
        L.append("")
    open(path_md, "w").write("\n".join(L))
    return scen

# ---------------------------------------------------------------- comandi

def cerca_voce(b, voce, fonti, verifica_amazon=2):
    q = voce["query"]
    print(f"→ {voce['id']}: {q}", file=sys.stderr)
    off = []
    if "amazon" in fonti:
        off += amazon_cerca(b, q)
    if "aliexpress" in fonti:
        off += ali_cerca(b, q)
    if "web" in fonti:
        off += web_cerca(b, q)
    tenute = analizza_voce(voce, off)
    # verifica a fondo le migliori Amazon (venditore, spedizione reale)
    for o in [o for o in tenute if o["fonte"] == "amazon"][:verifica_amazon]:
        amazon_verifica(b, o)
    tenute = analizza_voce(voce, tenute)
    voce["offerte"] = tenute
    voce["scartate"] = len(off) - len(tenute)
    voce["lette"] = len(off)
    return voce


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("cap"); a.add_argument("cap")
    a = sub.add_parser("cerca"); a.add_argument("query"); a.add_argument("--deve", default="")
    a.add_argument("--escludi", default=""); a.add_argument("--qty", default="1")
    a.add_argument("--fonti", default="amazon,aliexpress,web")
    a = sub.add_parser("bom"); a.add_argument("csv"); a.add_argument("--out", required=True)
    a.add_argument("--fonti", default="amazon,aliexpress,web"); a.add_argument("--prime", action="store_true")
    a.add_argument("--titolo", default="lista acquisti")
    a = sub.add_parser("carrello"); a.add_argument("json"); a.add_argument("--prime", action="store_true")
    a.add_argument("--titolo", default="lista acquisti")
    args = ap.parse_args()

    if args.cmd == "carrello":
        voci = json.load(open(args.json))
        md = os.path.join(os.path.dirname(args.json), "carrello.md")
        scrivi_carrello(voci, md, args.titolo, args.prime); print(md); return

    b = Browser()
    try:
        if args.cmd == "cap":
            pg = b.apri("https://www.amazon.it/", attesa=3, scroll=False)
            pg.click("#nav-global-location-popover-link"); time.sleep(2)
            pg.fill("#GLUXZipUpdateInput", args.cap); pg.click("#GLUXZipUpdate"); time.sleep(3)
            pg.reload(); time.sleep(3)
            print(pg.inner_text("#glow-ingress-line2")); pg.close()
        elif args.cmd == "cerca":
            v = cerca_voce(b, {"id": "q", "query": args.query, "deve": args.deve.replace(",", "|"),
                               "escludi": args.escludi.replace(",", "|"), "qty": args.qty},
                           args.fonti.split(","))
            print(json.dumps(v, ensure_ascii=False, indent=1))
        elif args.cmd == "bom":
            os.makedirs(args.out, exist_ok=True)
            voci = list(csv.DictReader(open(args.csv)))
            for v in voci:
                cerca_voce(b, v, args.fonti.split(","))
                json.dump(voci, open(os.path.join(args.out, "offerte.json"), "w"), ensure_ascii=False, indent=1)
            md = os.path.join(args.out, "carrello.md")
            scrivi_carrello(voci, md, args.titolo, args.prime)
            print(md)
    finally:
        b.chiudi()


if __name__ == "__main__":
    main()
