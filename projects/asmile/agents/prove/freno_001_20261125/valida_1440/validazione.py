"""Validazione COMPLETA del file soglie: ogni numero ha min/max e deve essere finito; chiave mancante, file mancante,
JSON rotto, NaN/Infinity o tipo sbagliato = SogliaError. Mai default silenziosi: il servizio esce con il motivo senza toccare il pin."""
import json
import math


class SogliaError(ValueError):
    pass


# percorso -> (min, max)   (estremi inclusi)
LIMITI = {
    "velocita.v_max_kmh": (5.0, 20.0), "velocita.zona_inizio_kmh": (3.0, 19.0),
    "encoder.m_per_count": (1.0e-5, 4.0e-5), "encoder.finestra_parabola_s": (0.15, 0.6),
    "encoder.pedale_T_default_s": (0.28, 0.7), "encoder.pedale_T_min_s": (0.2, 0.4), "encoder.pedale_T_max_s": (0.4, 1.0), "encoder.pedale_v_min_ms": (0.5, 5.0),
    "encoder.max_salto_counts": (100, 16384), "encoder.v_fisica_max_ms": (12.0, 30.0), "encoder.fresco_s": (0.05, 1.0), "encoder.verso_avanti": (-1, 1),
    "encoder.plausibilita.tol_v_gps_ms": (0.3, 3.0), "encoder.plausibilita.tol_v_gps_rel": (0.05, 0.6),
    "encoder.plausibilita.tol_a_imu_ms2": (1.0, 6.0), "encoder.plausibilita.tempo_s": (0.5, 5.0),
    "encoder.plausibilita.riammissione_s": (1.0, 30.0), "encoder.plausibilita.vel_senza_vibrazione_ms": (0.5, 4.0),
    "imu.ay_riposo_g": (-0.2, 0.2), "imu.gx_bias_dps": (-10.0, 10.0), "imu.ema_dec_s": (0.05, 0.4),
    "imu.morta_dopo_s": (0.1, 0.5), "imu.vibr_moto_g": (0.01, 0.06), "imu.vibr_fermo_g": (0.005, 0.04),
    "imu.a_min_g": (0.5, 0.9), "imu.a_max_g": (1.1, 1.6), "imu.a_min_inst_g": (0.1, 0.5), "imu.a_max_inst_g": (1.8, 4.0), "imu.congelato_cicli": (3, 20),
    "imu.recal_max_dev_ay_g": (0.0, 0.1), "imu.recal_max_dev_gx_dps": (0.0, 5.0),
    "imu.recal_max_dec_ms2": (0.1, 1.0), "imu.recal_max_gx_dps": (1.0, 10.0),
    "fusione_gps_imu.r_gps_ms": (0.05, 1.0), "fusione_gps_imu.r_ble_ms": (0.05, 1.5),
    "fusione_gps_imu.r_enc_bias": (0.1, 2.0), "fusione_gps_imu.q_v": (0.05, 3.0),
    "fusione_gps_imu.q_bias": (0.001, 0.2), "fusione_gps_imu.gps_fresco_s": (0.5, 5.0),
    "fusione_gps_imu.ble_fresco_s": (0.5, 6.0), "fusione_gps_imu.imu_solo_max_s": (0.2, 3.0),
    "fusione_gps_imu.sigma_v_max_ms": (0.2, 3.0), "fusione_gps_imu.v_max_valida_ms": (5.0, 15.0),
    "decel_obiettivo_ms2.normale": (0.1, 1.2), "decel_obiettivo_ms2.normale_picco_max": (0.3, 2.0),
    "decel_obiettivo_ms2.forte": (0.2, 1.5), "decel_obiettivo_ms2.forte_picco_max": (0.5, 2.5),
    "decel_obiettivo_ms2.massima_tollerata": (0.5, 2.0), "decel_obiettivo_ms2.massima_picco_max": (1.0, 2.5),
    "decel_obiettivo_ms2.mai_oltre": (1.5, 3.0), "decel_obiettivo_ms2.jerk_max_ms3": (0.5, 6.0),
    "decel_obiettivo_ms2.forte_se_sopra_kmh": (5.0, 20.0),
    "freno.tetto_deg": (0.0, 50.0), "freno.tetto_assoluto_codice_deg": (0.0, 50.0),
    "freno.rampa_su_deg_s": (1.0, 30.0), "freno.rampa_su_sopra_vmax_deg_s": (1.0, 30.0),
    "freno.rampa_su_oltre_soglia_deg_s": (0.5, 6.0), "freno.soglia_lenta_deg": (10.0, 50.0),
    "freno.rampa_giu_deg_s": (5.0, 100.0), "freno.rampa_tetto_deg_s": (10.0, 150.0),
    "freno.k_anello_deg_s_per_ms2": (1.0, 40.0), "freno.impulso_trigger_deg": (0.5, 3.0),
    "freno.impulso_tieni_s": (0.1, 0.5),
    "freno.tieni_per_grado_s": (0.01, 0.06), "freno.tieni_zero_s": (1.0, 3.0), "freno.libera_sotto_deg": (0.5, 5.0),
    "freno.tetto_imu_morta_deg": (0.0, 25.0), "freno.tetto_imu_morta_emergenza_deg": (0.0, 35.0),
    "freno.ritardo_comando_decel_s": (0.0, 1.0), "freno.uscita_tieni_s": (0.6, 3.0),
    "anti_impuntata.dec_imu_min_ms2": (1.0, 3.0), "anti_impuntata.muso_giu_min_deg": (0.5, 3.0),
    "anti_impuntata.finestra_s": (0.15, 0.6), "anti_impuntata.ripresa_frazione": (0.3, 1.0),
    "anti_impuntata.ripresa_in_piano_deg": (0.1, 1.5), "anti_impuntata.ripresa_in_piano_dps": (1.0, 10.0),
    "anti_impuntata.ripresa_in_piano_s": (0.1, 1.0), "anti_impuntata.ripresa_ripristino_s": (1.0, 15.0),
    "anti_impuntata.tetto_precoce.dec_imu_ms2": (2.0, 5.0), "anti_impuntata.tetto_precoce.frazione": (0.3, 1.0),
    "anti_impuntata.rilascio_gradi": (3.0, 25.0), "anti_impuntata.ancora_giu_dps": (0.5, 10.0),
    "anti_impuntata.fermo_s": (0.1, 2.0), "anti_impuntata.ripresa_rampa_deg_s": (0.5, 6.0),
    "anti_impuntata.ripresa_rampa_s": (1.0, 10.0), "anti_impuntata.dec_enc_conferma_ms2": (0.0, 2.0), "anti_impuntata.attesa_piano_max_s": (0.5, 5.0),
    "ina219.ma_fermo_max": (300.0, 2500.0), "ina219.tempo_s": (0.3, 3.0), "ina219.arretra_deg": (1.0, 10.0),
    "ina219.servo_fermo_s": (0.2, 2.0), "ina219.assente_dopo_s": (0.5, 10.0),
    "ina219.ma_rilascio_max": (200.0, 1500.0), "ina219.rilascio_tempo_s": (0.1, 2.0),
    "log_hz": (1, 50),
    "fallback.tetto_deg": (0.0, 50.0), "fallback.imu_scala_vs_enc": (1.0, 3.0),
    "freno.contatto_min_deg": (3.0, 22.0), "freno.contatto_max_deg": (10.0, 35.0), "freno.contatto_default_deg": (3.0, 25.0), "freno.rampa_cerca_deg_s": (1.0, 12.0),   # 25/11: #001 morde da 21-24 gradi (misurato)
    "freno.margine_contatto_deg": (0.5, 6.0), "freno.rampa_avvicinamento_deg_s": (5.0, 30.0),
    "freno.rampa_fine_su_deg_s": (0.5, 12.0), "freno.rampa_fine_su_sopra15_deg_s": (0.5, 25.0),
    "freno.rampa_fine_giu_deg_s": (0.5, 25.0),
    "regolatore.v_obiettivo_kmh": (4.0, 19.0), "regolatore.ti_s": (2.0, 30.0), "regolatore.guadagno_anello_1_s": (0.2, 2.0), "regolatore.g_default_ms2_per_deg": (0.03, 0.6), "regolatore.kp_min_deg_per_ms": (0.5, 10.0), "regolatore.kp_max_deg_per_ms": (2.0, 30.0), "regolatore.contatto_rate_max_deg_s": (1.0, 12.0), "regolatore.contatto_a_nat_max_ms2": (0.1, 1.5), "regolatore.kp_sopra_rel": (0.0, 3.0), "regolatore.contatto_soglia_fit_a_ms2": (0.3, 1.5), "regolatore.contatto_conferme": (1, 10), "regolatore.gia_margine_ms2": (0.0, 0.6), "regolatore.salita_dura_decel_ms2": (0.0, 0.5), "regolatore.contatto_coerenza_deg": (0.5, 3.0), "regolatore.contatto_salto_max_deg": (0.5, 3.0), "regolatore.contatto_soglia_anticipo_ms2": (0.2, 1.0), "regolatore.contatto_anticipo_cicli": (3, 50), "freno.contatto_scadenza_s": (3600, 2592000),
    "regolatore.contatto_alfa": (0.05, 1.0), "regolatore.a_nat_tau_s": (0.5, 5.0), "regolatore.ritardo_misura_a_s": (0.0, 1.0),  "regolatore.rilascio_dolce_deg_s": (0.0, 6.0),
    "regolatore.incrementale.margine_morso_deg": (0.0, 10.0), "regolatore.incrementale.avvicinamento_deg_s": (1.0, 60.0),
    "regolatore.incrementale.v_filtro_s": (0.05, 3.0), "regolatore.incrementale.k_v_deg_s_per_kmh": (0.2, 20.0), "regolatore.incrementale.k_v_giu_deg_s_per_kmh": (0.2, 40.0),
    "regolatore.incrementale.su_max_deg_s": (0.5, 25.0), "regolatore.incrementale.dec_ok_ms2": (0.1, 2.0),
    "regolatore.incrementale.k_dec_deg_s_per_ms2": (1.0, 100.0), "regolatore.incrementale.giu_max_deg_s": (1.0, 60.0),
    "regolatore.incrementale.fascia_sopra_deg": (0.5, 8.0), "regolatore.incrementale.cerca_deg_s": (0.5, 8.0), "regolatore.incrementale.morso_deriva_deg_s": (0.0, 3.0), "regolatore.incrementale.corsa_veloce_deg": (0.0, 35.0), "regolatore.incrementale.v_stabile_ms2": (0.0, 0.5), "regolatore.incrementale.banda_kmh": (0.0, 3.0),   # 25/11 fascia del morso
    "regolatore.ingaggio_sotto_zona_kmh": (0.0, 3.0), "regolatore.disimpegno_sotto_zona_kmh": (0.5, 5.0),
    "regolatore.esponente_zona": (1.0, 3.0), "regolatore.k_sopra_15_ms2_per_ms": (0.2, 3.0),
    "regolatore.a_pos_max_ms2": (0.05, 0.6), "regolatore.banda_morta_ms2": (0.0, 0.2), "regolatore.a_filtro_s": (0.05, 0.5),
}
BOOL = ["anti_impuntata.tetto_precoce.attivo", "regolatore.incrementale.attivo"]


def _foglie(d, p=""):
    for k, v in d.items():
        if k.startswith("_") or k == "stato":
            continue
        if isinstance(v, dict):
            yield from _foglie(v, p + k + ".")
        else:
            yield p + k, v


def _rifiuta_costante(s):
    raise SogliaError("valore non finito nel JSON: %s" % s)


def leggi(path):
    try:
        with open(path) as f:
            cfg = json.load(f, parse_constant=_rifiuta_costante)
    except FileNotFoundError:
        raise SogliaError("file soglie mancante: %s" % path)
    except (ValueError, OSError) as e:
        raise SogliaError("file soglie illeggibile/corrotto (%s): %s" % (path, e))
    if not isinstance(cfg, dict):
        raise SogliaError("file soglie: la radice deve essere un oggetto")
    return valida(cfg)


def valida(cfg):
    trovati = dict(_foglie(cfg))
    for k in LIMITI:
        if k not in trovati:
            raise SogliaError("soglia mancante: %s (niente default silenziosi)" % k)
    for k in BOOL:
        if not isinstance(trovati.get(k), bool):
            raise SogliaError("%s deve essere true/false" % k)
    for k, (lo, hi) in LIMITI.items():
        v = trovati[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise SogliaError("%s: non e' un numero (%r)" % (k, v))
        if not math.isfinite(v):
            raise SogliaError("%s: non finito" % k)
        if not (lo <= v <= hi):
            raise SogliaError("%s = %r fuori dai limiti [%s, %s]" % (k, v, lo, hi))
    ignote = [k for k in trovati if k not in LIMITI and k not in BOOL]
    if ignote:
        raise SogliaError("soglie sconosciute (senza limiti): %s" % ", ".join(sorted(ignote)))
    if cfg["encoder"]["verso_avanti"] not in (-1, 1):
        raise SogliaError("encoder.verso_avanti deve essere 1 o -1")
    d = cfg["decel_obiettivo_ms2"]
    ordine = [d["normale"], d["forte"], d["massima_tollerata"], d["mai_oltre"]]
    if ordine != sorted(ordine) or d["normale_picco_max"] < d["normale"] or d["forte_picco_max"] < d["forte"]:
        raise SogliaError("decelerazioni obiettivo non ordinate (normale <= forte <= massima <= mai_oltre)")
    if not cfg["velocita"]["zona_inizio_kmh"] < cfg["velocita"]["v_max_kmh"]:
        raise SogliaError("zona_inizio_kmh deve essere < v_max_kmh")
    fr = cfg["freno"]
    if not fr["contatto_min_deg"] <= fr["contatto_default_deg"] <= fr["contatto_max_deg"] <= min(fr["tetto_deg"], 50.0):
        raise SogliaError("freno: serve contatto_min <= contatto_default <= contatto_max <= tetto_deg (<= 50)")
    if fr["contatto_min_deg"] - fr["margine_contatto_deg"] < fr["libera_sotto_deg"]:
        raise SogliaError("freno: contatto_min - margine deve essere >= libera_sotto_deg (sotto verrebbe azzerato)")
    if not fr["rampa_cerca_deg_s"] <= 12.0:
        raise SogliaError("freno.rampa_cerca_deg_s > 12 gradi/s rifiutato (condizione asmile-sicurezza)")
    rg = cfg["regolatore"]
    if not (cfg["velocita"]["zona_inizio_kmh"] < rg["v_obiettivo_kmh"] < cfg["velocita"]["v_max_kmh"]):
        raise SogliaError("regolatore.v_obiettivo_kmh deve stare fra zona_inizio_kmh e v_max_kmh")
    if not rg["ingaggio_sotto_zona_kmh"] < rg["disimpegno_sotto_zona_kmh"]:
        raise SogliaError("regolatore: ingaggio_sotto_zona_kmh deve essere < disimpegno_sotto_zona_kmh (isteresi)")
    if cfg["freno"]["tetto_deg"] > 50.0 or cfg["freno"]["tetto_assoluto_codice_deg"] > 50.0:
        raise SogliaError("tetto freno > 50 gradi rifiutato")
    if cfg["imu"]["vibr_fermo_g"] >= cfg["imu"]["vibr_moto_g"]:
        raise SogliaError("imu.vibr_fermo_g deve essere < vibr_moto_g")
    if cfg["imu"]["a_min_g"] >= cfg["imu"]["a_max_g"]:
        raise SogliaError("imu.a_min_g deve essere < a_max_g")
    return cfg
