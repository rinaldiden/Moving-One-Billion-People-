#!/usr/bin/env python3
"""BOM del logger HW4 da netlist_hw4.py + prezzi/stock dall'API parti JLCPCB (cache in prezzi_jlc.json, con data).

Uscite (nella cartella logger_hw4/):
  BOM.csv            — BOM ragionato: parte, LCSC, Basic/Extended, stock, prezzo 10/100/1000, alternativa, note
  BOM_JLC.csv        — formato caricamento JLCPCB/PCBWay (Comment, Designator, Footprint, LCSC), senza DNP
  COSTI.md           — costo per scheda a 10/100/1000 per scenario (pezzi + moduli + camere; PCB/montaggio a parte)
Uso: python3 genera_bom.py [--aggiorna]  (--aggiorna rilegge i prezzi dall'API)
"""
import csv, datetime, json, os, sys, time, urllib.request
import netlist_hw4 as NL

QUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(QUI)
CACHE = os.path.join(QUI, "prezzi_jlc.json")

# alternativa pin-compatibile per i pezzi critici (verificata sul pinout del datasheet, non sul nome)
ALT = {
    "C725790": "C16581 TP4056-42-ESOP8 (stesso pinout, altro produttore) · IP2312 NO (pinout diverso)",
    "C351410": "C2927799 / C18164398 DW01A di altri produttori (SOT-23-6, stesso pinout)",
    "C2830320": "C908265 FS8205A (SOT-23-6) · 8205A di altri produttori",
    "C141836": "C47117578 TLV62569DBVR-TP (MCC) · C54839595 (stesso SOT-23-5 EN/GND/SW/VIN/FB)",
    "C408335": "qualsiasi 2,2 µH ≥2,5 A 4×4 mm (es. FNR4030S2R2M) — controllare l'ingombro",
    "C967633": "nessuna pin-compatibile esatta in LGA-14 2,5×3 con stessi pin: piano B ICM-42670-P C3288646 (richiede footprint dedicato) → footprint opzionale",
    "C2827654": "C7519 USBLC6-2SC6 ST (originale) · C2687116",
    "C165948": "C2765186 TYPE-C 16P 2MD(073) (stesso footprint? DA VERIFICARE)",
    "C113206": "C381082 XKTF-015-N (stesso ingombro TF-015)",
    "C7529394": "C23397372 FC-10A15P11H20 (15p 1 mm, contatti in basso: DA VERIFICARE lato contatti)",
    "C160402": "C5306062 SM02B-SRSS-TB",
    "C54582899": "S2B-PH-SM4-TB JST originale",
    "C96127": "C409830 YS-SBZ9650DYB05 (9,6×9,6 mm)",
    "C15127": "C347476 AO3401A", "C2146": "C105433 S8050", "C318884": "C42420254 TS-1187A",
    "C81598": "1N4148W altri produttori", "C88374": "u.FL compatibili IPEX MHF1",
}
FUORI_LCSC = [  # pezzi che non arrivano da LCSC: prezzi del 18/11/2026 con fonte
    dict(ref="U10,U20", qty=2, value="Waveshare ESP32-P4-Module 16MB (IPEX)", lcsc="", tipo="fornito a parte",
         p10=10.99, p100=9.99, p1000=9.99,
         nota="waveshare.com 9,99-10,99 $ (prezzo a 100 DA VERIFICARE: preventivo Waveshare); non in libreria JLC: kit consegnato o saldato a mano"),
    dict(ref="ANT", qty=2, value="antenna FPC 2,4 GHz IPEX adesiva", lcsc="", tipo="fornito a parte",
         p10=1.0, p100=0.6, p1000=0.4, nota="stima, DA VERIFICARE"),
]
CAMERE = {  # prezzo per camera (USD) a 10/100/1000 — vedi DESIGN.md §3
    "C1 OV9281 modulo Pi (dettaglio, makersheet 41 €)": (45.0, 45.0, 45.0),
    "C1 OV9281 modulo Pi (DFRobot SEN0634 24 $ a 10+)": (24.0, 22.0, 20.0),
    "C1 OV9281 modulo in volume (stima, preventivo da chiedere)": (24.0, 18.0, 14.0),
    "C2 SC132GS Camemake (DigiKey)": (77.84, 77.84, 8.80),
    "C5 OV9281 nudo + portalente M12 (non comprabile oggi)": (12.25, 9.0, 7.0),
}


def jlc(code):
    req = urllib.request.Request(
        "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList",
        data=json.dumps({"keyword": code, "currentPage": 1, "pageSize": 5}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for c in (d.get("data") or {}).get("componentPageInfo", {}).get("list") or []:
        if c.get("componentCode") == code:
            pr = sorted((p["startNumber"], p["productPrice"]) for p in c.get("componentPrices") or [])

            def at(n):
                v = pr[0][1] if pr else None
                for s, p in pr:
                    if s <= n:
                        v = p
                return v
            return dict(mpn=c.get("componentModelEn"), lib="Basic" if c.get("componentLibraryType") == "base" else "Extended",
                        stock=c.get("stockCount"), p10=at(10), p100=at(100), p1000=at(1000))
    return None


def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {"data": "", "parti": {}}
    righe = {}
    for p in NL.PARTS:
        if not p["lcsc"]:
            continue
        k = (p["lcsc"], p["value"], p["fp"])
        r = righe.setdefault(k, dict(refs=[], dnp_refs=[], value=p["value"], fp=p["fp"], lcsc=p["lcsc"]))
        (r["dnp_refs"] if p["dnp"] else r["refs"]).append(p["ref"])
    codici = sorted({k[0] for k in righe})
    if "--aggiorna" in sys.argv or not cache["parti"]:
        for c in codici:
            cache["parti"][c] = jlc(c)
            time.sleep(0.3)
        cache["data"] = datetime.date.today().isoformat()
        json.dump(cache, open(CACHE, "w"), indent=1)
    tot = {10: 0.0, 100: 0.0, 1000: 0.0}
    estesi = set()
    with open(os.path.join(OUT, "BOM.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["designatori", "qta", "valore", "footprint", "LCSC", "MPN", "Basic/Extended", "stock_" + cache["data"],
                    "prezzo_10", "prezzo_100", "prezzo_1000", "alternativa pin-compatibile", "non montati (DNP)"])
        for k, r in sorted(righe.items(), key=lambda kv: kv[1]["refs"][:1] or kv[1]["dnp_refs"][:1]):
            info = cache["parti"].get(r["lcsc"]) or {}
            q = len(r["refs"])
            for n in tot:
                v = info.get("p%d" % n)
                if v and q:
                    tot[n] += v * q
            if q and info.get("lib") == "Extended":
                estesi.add(r["lcsc"])
            w.writerow([" ".join(r["refs"]), q, r["value"], r["fp"], r["lcsc"], info.get("mpn", "?"), info.get("lib", "?"),
                        info.get("stock", "?"), info.get("p10"), info.get("p100"), info.get("p1000"),
                        ALT.get(r["lcsc"], ""), " ".join(r["dnp_refs"])])
        for x in FUORI_LCSC:
            w.writerow([x["ref"], x["qty"], x["value"], "", "", "", x["tipo"], "", x["p10"], x["p100"], x["p1000"], "", x["nota"]])
    with open(os.path.join(OUT, "BOM_JLC.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for k, r in righe.items():
            if r["refs"]:
                w.writerow([r["value"], ",".join(r["refs"]), r["fp"], r["lcsc"]])
    fuori = {n: sum(x["qty"] * x["p%d" % n] for x in FUORI_LCSC) for n in tot}
    json.dump(dict(data=cache["data"], pezzi_lcsc=tot, fuori_lcsc=fuori, estesi=sorted(estesi),
                   n_estesi=len(estesi), camere=CAMERE), open(os.path.join(QUI, "costi_bom.json"), "w"), indent=1)
    print("data prezzi:", cache["data"], "| pezzi LCSC per scheda:", {n: round(v, 2) for n, v in tot.items()},
          "| moduli+antenne:", fuori, "| Extended distinti:", len(estesi))
    mancanti = [c for c in codici if not cache["parti"].get(c)]
    if mancanti:
        print("SENZA PREZZO:", mancanti)


if __name__ == "__main__":
    main()
