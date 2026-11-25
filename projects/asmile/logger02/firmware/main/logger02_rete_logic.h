/* Rete di sicurezza della A (25/11, Daniele: "deve SEMPRE ritrovare il wifi"). Logica pura, senza IDF: si prova sul Mac
 * (../host_test/test_rete_logic.c). Tempi in us.
 *   rete ok = IP + DNS che risponde.  Senza rete:
 *   60 s  → riprovo esp_wifi_connect (costa niente)
 *   120 s → reset del C6 (esp_hosted deinit/init = impulso su GPIO54, poi wifi da capo)
 *   +60 s → riavvio pulito della A, SOLO in pausa (bici ferma) e senza scarico in corso; in movimento aspetta.
 *           Una sola volta per risveglio: dopo, solo reset del C6 ogni 5 minuti (niente giri di riavvii).
 *   Fuori portata (il C6 dice "rete non trovata" da meno di 30 s) = il C6 è vivo: niente reset, niente riavvio. */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define RETE_RIPROVA_S    60
#define RETE_RESET_C6_S   120
#define RETE_RIAVVIO_S    60      /* dopo il reset del C6 */
#define RETE_RIRESET_S    300     /* riavvio già fatto in questo risveglio: reset del C6 ogni 5 min */
#define RETE_NOAP_S       30

typedef enum { L02_R_NIENTE, L02_R_TORNATA, L02_R_RIPROVA, L02_R_RESET_C6, L02_R_RIAVVIA, L02_R_ASPETTA } l02_rete_azione_t;

typedef struct {
    int64_t ok_t;        /* ultima volta con rete ok (o C6 vivo fuori portata) */
    int64_t t_reset;     /* ultimo reset del C6 */
    int fase;            /* 0 ok, 1 riprovato, 2 C6 resettato */
} l02_rete_st_t;

typedef struct {
    bool ok;             /* IP + DNS */
    int64_t noap_t;      /* ultimo "rete non trovata" dal C6 (0 = mai) */
    bool pausa;          /* bici ferma: registrazione in pausa */
    bool scarico;        /* trasferimento in corso (contatore, non appeso) */
    int riavvii;         /* riavvii della rete di sicurezza già fatti in questo risveglio */
} l02_rete_in_t;

static inline l02_rete_azione_t l02_rete_passo(int64_t t, l02_rete_st_t *s, const l02_rete_in_t *in)
{
    if (in->ok) {
        l02_rete_azione_t a = s->fase ? L02_R_TORNATA : L02_R_NIENTE;
        s->fase = 0;
        s->ok_t = t;
        return a;
    }
    if (in->noap_t && t - in->noap_t < RETE_NOAP_S * 1000000LL) {   /* fuori portata, C6 vivo */
        s->fase = 0;
        s->ok_t = t;
        return L02_R_NIENTE;
    }
    int64_t giu = t - s->ok_t;
    if (s->fase == 0) {
        if (giu < RETE_RIPROVA_S * 1000000LL) return L02_R_NIENTE;
        s->fase = 1;
        return L02_R_RIPROVA;
    }
    if (s->fase == 1) {
        if (giu < RETE_RESET_C6_S * 1000000LL) return L02_R_NIENTE;
        s->fase = 2;
        s->t_reset = t;
        return L02_R_RESET_C6;
    }
    int64_t dal_reset = t - s->t_reset;
    if (in->riavvii >= 1) {
        if (dal_reset < RETE_RIRESET_S * 1000000LL) return L02_R_NIENTE;
        s->t_reset = t;
        return L02_R_RESET_C6;
    }
    if (dal_reset < RETE_RIAVVIO_S * 1000000LL) return L02_R_NIENTE;
    if (!in->pausa || in->scarico) return L02_R_ASPETTA;
    return L02_R_RIAVVIA;
}
