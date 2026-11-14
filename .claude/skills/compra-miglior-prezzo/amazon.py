#!/usr/bin/env python3
"""
amazon.py — Amazon.it dall'account di Daniele, col profilo Chrome del doppio (~/.claude_pw_shop).

Sullo stesso account ci sono PIÙ CARTE e PIÙ INDIRIZZI. Prima di ogni acquisto lo script impone:
  indirizzo = Rinaldi Daniele, via San Carlo 25        (acquisti.json → amazon.indirizzo_cerca)
  carta     = quella che termina con le ultime 4 cifre (acquisti.json → amazon.carta_ultime4)
Se non riesce a selezionarli e a rileggerli nella pagina di riepilogo, si FERMA. Non indovina.

Uso (~/.asmile_depth_venv/bin/python):
  amazon.py login                         # UNA volta: Chrome visibile, Daniele entra (password + codice), poi chiude
  amazon.py stato [--dettagli]            # loggato? + indirizzi e carte che vede (solo ultime 4 cifre)
  amazon.py aggiungi B0XXXXXXX:2 B0YYYY   # mette nel carrello ASIN:quantità
  amazon.py carrello                      # cosa c'è nel carrello + subtotale
  amazon.py svuota                        # toglie tutto dal carrello (prima di un ordine pulito)
  amazon.py prepara                       # va al checkout, imposta indirizzo+carta, legge il totale, SI FERMA
  amazon.py compra --totale 23.45 --ok "Daniele, Telegram 2026-11-14 12:30"
                                          # rifà prepara; clicca "Acquista ora" SOLO se totale, indirizzo e
                                          # carta coincidono con quanto approvato

Ogni prepara/compra scrive ~/.config/doppio/amazon_checkout/<data_ora>.json + screenshot.
Profilo condiviso con cerca_prezzi.py: un processo alla volta (lock di Chrome).
"""
import json, os, re, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from account import dati  # noqa: E402

PROFILE = os.path.expanduser(os.environ.get("DOPPIO_PW_SHOP", "~/.claude_pw_shop"))
OUT = os.path.expanduser("~/.config/doppio/amazon_checkout")
BASE = "https://www.amazon.it"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
TOLL_TOTALE = 0.01   # il totale approvato deve essere identico al centesimo


def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def euro(s):
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*€|€\s*(\d{1,3}(?:\.\d{3})*,\d{2})", s or "")
    if not m:
        return None
    return float((m.group(1) or m.group(2)).replace(".", "").replace(",", "."))


class Amazon:
    def __init__(self, visibile=False):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            PROFILE, channel="chrome", headless=not visibile, locale="it-IT",
            user_agent=None if visibile else UA, viewport=None if visibile else {"width": 1280, "height": 1800},
            args=["--disable-blink-features=AutomationControlled"])
        self.pg = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()

    def vai(self, url, attesa=3):
        self.pg.goto(url if url.startswith("http") else BASE + url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(attesa)

    def testo(self, sel="body"):
        try:
            return self.pg.locator(sel).first.inner_text(timeout=5000)
        except Exception:
            return ""

    def loggato(self):
        """Il saluto in alto: 'Ciao, Daniele' = dentro; 'Ciao, accedi' = fuori."""
        t = norm(self.testo("#nav-link-accountList"))
        return bool(t) and "accedi" not in t, t

    def chiede_login(self):
        u = self.pg.url
        return "/ap/signin" in u or "/ap/mfa" in u or "/ap/cvf" in u

    def foto(self, nome):
        os.makedirs(OUT, exist_ok=True)
        p = os.path.join(OUT, f"{nome}.png")
        try:
            self.pg.screenshot(path=p, full_page=True)
        except Exception:
            pass
        return p

    def chiudi(self):
        self.ctx.close()
        self._pw.stop()


# ---------------------------------------------------------------- login / stato

def cmd_login():
    print("Apro Chrome: entra su Amazon (email, password, codice). Spunta 'Resta connesso'. "
          "Chiudo da solo appena vedo 'Ciao, <nome>' (attendo fino a 15 minuti).")
    a = Amazon(visibile=True)
    a.vai("/ap/signin?openid.return_to=https%3A%2F%2Fwww.amazon.it%2F&openid.assoc_handle=itflex"
          "&openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
          "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
          "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select")
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(4)
        try:
            if "amazon.it" in a.pg.url and not a.chiede_login():
                ok, saluto = a.loggato()
                if ok:
                    print(f"ok: dentro ({saluto}). Da qui in poi lavoro headless da solo.")
                    a.chiudi(); return 0
        except Exception:
            pass
    a.chiudi()
    sys.exit("login non completato entro 15 minuti")


def leggi_indirizzi(a):
    a.vai("/a/addresses", 4)
    if a.chiede_login():
        return None
    out = []
    for el in a.pg.locator("[id^='ya-myab-display-address-block'], .address-column, #ya-myab-address-list .a-box").all():
        t = el.inner_text().strip()
        if t and len(t) > 10:
            out.append(re.sub(r"\n+", " | ", t)[:200])
    return out


def leggi_carte(a):
    a.vai("/cpe/yourpayments/wallet", 5)
    if a.chiede_login():
        return None
    t = a.testo()
    return sorted(set(re.findall(r"(?:termina(?:nte)? (?:con|in|per)|•••• ?|\*{4} ?)(\d{4})", t, re.I)))


def cmd_stato(dettagli=False):
    a = Amazon()
    try:
        a.vai("/", 3)
        ok, saluto = a.loggato()
        print(f"loggato: {'sì' if ok else 'NO'}  ({saluto or 'saluto non letto'})")
        if not ok:
            print("→ serve `amazon.py login` (Daniele, una volta)")
            return 1
        if dettagli:
            d = dati()["amazon"]
            ind = leggi_indirizzi(a)
            if ind is None:
                print("indirizzi: Amazon chiede di rientrare con la password (vedi SKILL.md, sessione scaduta)")
            else:
                print(f"indirizzi ({len(ind)}):")
                for i in ind:
                    giusto = all(k in norm(i) for k in d["indirizzo_cerca"])
                    print(f"  {'→' if giusto else ' '} {i}")
            carte = leggi_carte(a)
            print(f"carte (ultime 4): {carte if carte is not None else 'Amazon chiede la password'}")
            print(f"carta impostata per il doppio: {d.get('carta_ultime4') or 'NON IMPOSTATA (chiedere a Daniele)'}")
        return 0
    finally:
        a.chiudi()


# ---------------------------------------------------------------- carrello

def aggiungi_da_scheda(a, asin, qty):
    """Dalla scheda prodotto: quantità + 'Aggiungi al carrello'. (Il link /gp/aws/cart/add oggi rimanda
    al login anche da loggati in alcuni casi: la scheda è la via che regge.)"""
    a.vai(f"/dp/{asin}", 4)
    if qty > 1:
        try:
            a.pg.select_option("#quantity", str(qty), timeout=4000)
        except Exception:
            print(f"   ! {asin}: menu quantità non trovato, aggiungo {qty} volte")
    volte = 1 if qty == 1 or a.pg.locator("#quantity").count() else qty
    for _ in range(volte):
        b = a.pg.locator("#add-to-cart-button")
        if not b.count():
            print(f"   ! {asin}: 'Aggiungi al carrello' assente (non disponibile o solo altri venditori)")
            return False
        b.first.click(); time.sleep(4)
        for chiudi in ["#attach-close_sideSheet-link", "#attachSiNoCoverage input", "input[aria-labelledby*='no']"]:
            c = a.pg.locator(chiudi)
            if c.count() and c.first.is_visible():
                c.first.click(); time.sleep(1); break
        if volte > 1:
            a.vai(f"/dp/{asin}", 3)
    return True


def cmd_aggiungi(voci):
    a = Amazon()
    try:
        a.vai("/", 2)
        if not a.loggato()[0]:
            print("attenzione: non loggato, il carrello resta nel profilo ma il checkout richiederà il login")
        for v in voci:
            asin, _, q = v.partition(":")
            aggiungi_da_scheda(a, asin, int(q or 1))
        cmd_carrello(a)
    finally:
        a.chiudi()


def leggi_carrello(a):
    a.vai("/gp/cart/view.html", 4)
    righe = []
    for el in a.pg.locator("[data-name='Active Items'] [data-asin]").all():
        asin = el.get_attribute("data-asin")
        if not asin:
            continue
        tit = el.locator(".sc-product-title, .a-truncate-full").first.inner_text().strip() if el.locator(
            ".sc-product-title, .a-truncate-full").count() else ""
        qty = el.get_attribute("data-quantity") or ""
        prezzo = el.get_attribute("data-price") or ""
        righe.append({"asin": asin, "titolo": tit[:90], "qty": qty, "prezzo": prezzo})
    sub = euro(a.testo("#sc-subtotal-amount-activecart, #sc-subtotal-amount-buybox"))
    return righe, sub


def cmd_carrello(a=None):
    mio = a is None
    a = a or Amazon()
    try:
        righe, sub = leggi_carrello(a)
        for r in righe:
            print(f"  {r['asin']}  x{r['qty']:>2}  {r['prezzo']:>8} €  {r['titolo']}")
        print(f"subtotale: {sub} €  ({len(righe)} voci)")
        return righe, sub
    finally:
        if mio:
            a.chiudi()


def cmd_svuota():
    a = Amazon()
    try:
        for _ in range(40):
            a.vai("/gp/cart/view.html", 3)
            b = a.pg.locator("[data-name='Active Items'] input[value='Rimuovi'], "
                             "[data-name='Active Items'] input[data-action='delete'], "
                             "[data-name='Active Items'] [data-action='delete'] input")
            if not b.count():
                break
            b.first.click(); time.sleep(2)
        cmd_carrello(a)
    finally:
        a.chiudi()


# ---------------------------------------------------------------- checkout

def _sezione(a, chiavi):
    """Testo della sezione del riepilogo (indirizzo o pagamento): il checkout Amazon cambia spesso id,
    quindi provo gli id noti e poi ripiego sul blocco che contiene la parola chiave."""
    for sel in chiavi:
        t = a.testo(sel)
        if t.strip():
            return t
    return ""


def _scegli(a, link_cambia, voci_testo, conferma):
    """Apre 'Cambia', sceglie l'opzione il cui testo contiene TUTTE le voci_testo, conferma."""
    for sel in link_cambia:
        l = a.pg.locator(sel)
        if l.count() and l.first.is_visible():
            l.first.click(); time.sleep(4); break
    else:
        return False
    for opz in a.pg.locator("input[type='radio']").all():
        try:
            box = opz.locator("xpath=ancestor::*[self::label or self::div[contains(@class,'a-row')] or "
                              "self::div[contains(@class,'a-box')]][1]")
            t = norm(box.inner_text())
        except Exception:
            continue
        if all(v in t for v in voci_testo):
            opz.check(force=True); time.sleep(1.5)
            for c in conferma:
                b = a.pg.locator(c)
                if b.count() and b.first.is_visible():
                    b.first.click(); time.sleep(5); return True
            return True
    return False


SEL_IND = ["#shipaddress", "#deliver-to-address-text", "#checkout-deliveryAddressPanel",
           "[data-testid='Address_selectShipToThisAddress']", "#addressChangeLinkId ~ *"]
SEL_PAG = ["#payment-information", "#checkout-paymentInformationSection", "#payChangeButtonId ~ *",
           ".pmts-instrument-display-name", "#paymentMethodHeader ~ *"]
CAMBIA_IND = ["#addressChangeLinkId", "a[data-args*='address']", "a:has-text('Cambia') >> nth=0"]
CAMBIA_PAG = ["#payChangeButtonId", "a[data-args*='payment']", "a:has-text('Cambia') >> nth=1"]
CONF_IND = ["input[data-testid='Address_selectShipToThisAddress']", "#shipToThisAddressButton input",
            "span:has-text('Usa questo indirizzo')"]
CONF_PAG = ["input[name='ppw-widgetEvent:SetPaymentPlanSelectContinueEvent']", "#orderSummaryPrimaryActionBtn input",
            "span:has-text('Usa questo metodo di pagamento')"]
ACQUISTA = ["#submitOrderButtonId input", "input[name='placeYourOrder1']", "#placeYourOrder input",
            "#bottomSubmitOrderButtonId input"]


def prepara(a):
    d = dati()["amazon"]
    ultime4 = (d.get("carta_ultime4") or "").strip()
    voci_ind = d["indirizzo_cerca"]
    esito = {"ora": datetime.now().isoformat(timespec="seconds"), "ok": False, "problemi": []}
    if not re.fullmatch(r"\d{4}", ultime4):
        esito["problemi"].append("carta non impostata: `account.py imposta amazon.carta_ultime4 NNNN` (la dà Daniele)")
        return esito
    righe, sub = leggi_carrello(a)
    esito["carrello"], esito["subtotale"] = righe, sub
    if not righe:
        esito["problemi"].append("carrello vuoto"); return esito
    a.vai("/gp/buy/spc/handlers/display.html?hasWorkingJavascript=1", 6)
    if a.chiede_login():
        esito["problemi"].append("Amazon chiede di rientrare (password/codice): sessione da rinnovare")
        esito["foto"] = a.foto("login_richiesto"); return esito

    # indirizzo
    if not all(v in norm(_sezione(a, SEL_IND)) for v in voci_ind):
        _scegli(a, CAMBIA_IND, voci_ind, CONF_IND)
    t_ind = _sezione(a, SEL_IND)
    esito["indirizzo"] = re.sub(r"\s+", " ", t_ind)[:200]
    if not all(v in norm(t_ind) for v in voci_ind):
        esito["problemi"].append(f"indirizzo NON impostato su {voci_ind}")

    # carta
    if ultime4 not in _sezione(a, SEL_PAG):
        _scegli(a, CAMBIA_PAG, [ultime4], CONF_PAG)
        a.vai("/gp/buy/spc/handlers/display.html?hasWorkingJavascript=1", 6)
    t_pag = _sezione(a, SEL_PAG)
    esito["pagamento"] = re.sub(r"\s+", " ", t_pag)[:160]
    if ultime4 not in t_pag:
        esito["problemi"].append(f"carta che termina con {ultime4} NON selezionata")

    # ricontrollo l'indirizzo dopo il cambio carta (alcuni flussi lo riportano al predefinito)
    if not all(v in norm(_sezione(a, SEL_IND)) for v in voci_ind):
        if "indirizzo" not in " ".join(esito["problemi"]):
            esito["problemi"].append("indirizzo cambiato dopo la scelta della carta")

    tot = None
    for sel in ["#subtotals-marketplace-table .grand-total-price", "#subtotals-marketplace-table",
                ".order-summary-grand-total", "#orderSummaryPrimaryActionBtn ~ *", "#spc-orders"]:
        t = a.testo(sel)
        m = re.search(r"Totale ordine[^\d€]*([\d.,]+\s*€|€\s*[\d.,]+)", t, re.I)
        if m:
            tot = euro(m.group(1)); break
    esito["totale"] = tot
    if tot is None:
        esito["problemi"].append("totale ordine non letto")
    esito["foto"] = a.foto(datetime.now().strftime("checkout_%Y%m%d_%H%M%S"))
    esito["ok"] = not esito["problemi"]
    return esito


def registra(esito, tipo):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, datetime.now().strftime(f"{tipo}_%Y%m%d_%H%M%S.json"))
    with open(p, "w") as f:
        json.dump(esito, f, ensure_ascii=False, indent=2)
    return p


def cmd_prepara():
    a = Amazon()
    try:
        e = prepara(a)
        p = registra(e, "prepara")
        print(json.dumps({k: e.get(k) for k in ("ok", "totale", "indirizzo", "pagamento", "problemi")},
                         ensure_ascii=False, indent=2))
        print(f"registro: {p}\nfoto: {e.get('foto')}")
        print("FERMO prima di 'Acquista ora'. Per comprare: compra --totale <totale> --ok '<chi, dove, quando>'")
        return 0 if e["ok"] else 2
    finally:
        a.chiudi()


def cmd_compra(totale, ok):
    if not ok or len(ok) < 8:
        sys.exit("--ok obbligatorio: chi ha approvato, su che canale, quando")
    a = Amazon()
    try:
        e = prepara(a)
        e["approvato"], e["totale_approvato"] = ok, totale
        if not e["ok"]:
            registra(e, "compra_rifiutato"); sys.exit(f"NON compro: {e['problemi']}")
        if e["totale"] is None or abs(e["totale"] - totale) > TOLL_TOTALE:
            registra(e, "compra_rifiutato")
            sys.exit(f"NON compro: totale {e['totale']} € ≠ approvato {totale} € (riproponi a Daniele)")
        for sel in ACQUISTA:
            b = a.pg.locator(sel)
            if b.count() and b.first.is_visible():
                b.first.click(); time.sleep(8); break
        else:
            registra(e, "compra_rifiutato"); sys.exit("pulsante 'Acquista ora' non trovato: nulla acquistato")
        t = a.testo()
        e["conferma"] = bool(re.search(r"ordine (?:effettuato|inviato)|grazie, il tuo ordine", t, re.I))
        m = re.search(r"\b(\d{3}-\d{7}-\d{7})\b", t)
        e["numero_ordine"] = m.group(1) if m else None
        e["foto_conferma"] = a.foto(datetime.now().strftime("ordine_%Y%m%d_%H%M%S"))
        p = registra(e, "ordine")
        print(json.dumps({k: e.get(k) for k in ("conferma", "numero_ordine", "totale", "indirizzo", "pagamento")},
                         ensure_ascii=False, indent=2))
        print(f"registro: {p}")
        return 0 if e["conferma"] else 3
    finally:
        a.chiudi()


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    c = a[0]
    if c == "login":
        return cmd_login()
    if c == "stato":
        return cmd_stato("--dettagli" in a)
    if c == "aggiungi":
        return cmd_aggiungi(a[1:])
    if c == "carrello":
        cmd_carrello(); return 0
    if c == "svuota":
        return cmd_svuota()
    if c == "prepara":
        return cmd_prepara()
    if c == "compra":
        tot = float(a[a.index("--totale") + 1].replace(",", ".")) if "--totale" in a else None
        ok = a[a.index("--ok") + 1] if "--ok" in a else ""
        if tot is None:
            sys.exit("--totale obbligatorio (quello letto da prepara e approvato)")
        return cmd_compra(tot, ok)
    print(__doc__)


if __name__ == "__main__":
    sys.exit(main())
