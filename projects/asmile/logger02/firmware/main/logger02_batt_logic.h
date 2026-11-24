/* Protezione batteria di logger02: logica pura (nessuna dipendenza IDF, si prova sul Mac: ../host_test/test_batt_logic.c).
 * 24/11: le celle sono finite a 1,9 V (tester di Daniele) mentre il firmware leggeva 2,03 V; il modulo step-up non stacca
 * in scarica e il firmware non aveva protezione. Decisione di Daniele: "il logger si spegne ai 3 V".
 *
 *  - Taratura: L02_BATT_SCALA e' l'UNICO posto. 2,03 V letti = 1,90 V veri (tester) -> 1,90/2,03 = 0,936. Un solo punto, a cella
 *    SCARICA: da rifare con 2 punti (cella carica ~4,0 V + scarica) appena c'e' una cella carica; con un solo punto l'errore
 *    a 3-4 V puo' essere diverso (offset e guadagno non separabili). Finche' non rifatta, 3,0 V "veri" sono ~3,0 +/- 0,2 V.
 *  - Spegnimento: media mobile di L02_BATT_FINESTRA letture (1 al secondo: la lettura salta 2,36-2,83 in un secondo); media
 *    sotto L02_BATT_OFF_V per L02_BATT_OFF_S secondi CONSECUTIVI (un solo ritorno sopra azzera il conteggio); finestra piena.
 *  - Avvio: media delle prime letture sotto L02_BATT_START_V (3,1 V) = non avvio. Isteresi 0,1 V sopra la soglia di spegnimento:
 *    una cella che si e' appena spenta a 3,0 V risale a vuoto di 0,1-0,3 V appena scarica il carico; senza isteresi
 *    ripartirebbe, crollerebbe, si spegnerebbe e cosi' via (avvio-crollo-avvio).
 *  - Batteria assente / lettura impossibile (NaN o < L02_BATT_ASSENTE_V): NON spegne (potrebbe essere il partitore scollegato),
 *    azzera il conteggio e segnala L02_BATT_ASSENTE. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <math.h>

#define L02_BATT_SCALA      0.936f   /* tensione vera = lettura grezza * scala (unico punto di taratura, vedi sopra) */
#define L02_BATT_OFF_V      3.0f
#define L02_BATT_OFF_S      10
#define L02_BATT_START_V    3.1f
#define L02_BATT_ASSENTE_V  0.5f
#define L02_BATT_FINESTRA   5

typedef enum { L02_BATT_OK = 0, L02_BATT_ASSENTE = 1, L02_BATT_SPEGNI = 2 } l02_batt_esito_t;

typedef struct {
    float buf[L02_BATT_FINESTRA];
    int n, i;                  /* letture valide nella finestra, prossima posizione */
    int64_t sotto_da;          /* us da cui la media e' sotto soglia, 0 = non lo e' */
    float media;
} l02_batt_t;

static inline bool l02_batt_valida(float v) { return !isnan(v) && v >= L02_BATT_ASSENTE_V; }

static inline float l02_batt_vera(float grezza) { return l02_batt_valida(grezza) ? grezza * L02_BATT_SCALA : grezza; }

/* una lettura (gia' tarata, 1 al secondo). t in us (> 0). */
static inline l02_batt_esito_t l02_batt_campione(l02_batt_t *b, int64_t t, float v)
{
    if (!l02_batt_valida(v)) {         /* assente: non spegne, e il conteggio riparte da zero quando torna */
        b->n = 0; b->i = 0; b->sotto_da = 0;
        return L02_BATT_ASSENTE;
    }
    b->buf[b->i] = v;
    b->i = (b->i + 1) % L02_BATT_FINESTRA;
    if (b->n < L02_BATT_FINESTRA) b->n++;
    float s = 0;
    for (int k = 0; k < b->n; k++) s += b->buf[k];
    b->media = s / b->n;
    if (b->n < L02_BATT_FINESTRA || b->media >= L02_BATT_OFF_V) { b->sotto_da = 0; return L02_BATT_OK; }
    if (b->sotto_da == 0) b->sotto_da = t;
    return t - b->sotto_da >= (int64_t)L02_BATT_OFF_S * 1000000LL ? L02_BATT_SPEGNI : L02_BATT_OK;
}

/* avvio: letture gia' tarate dei primi secondi. true = si puo' avviare. *media = media delle valide (-1 se nessuna).
 * Nessuna lettura valida (batteria assente) = si avvia (e si segnala). */
static inline bool l02_batt_avvio_ok(const float *v, int n, float *media)
{
    float s = 0; int k = 0;
    for (int j = 0; j < n; j++) if (l02_batt_valida(v[j])) { s += v[j]; k++; }
    if (media) *media = k ? s / k : -1.0f;
    return k == 0 || s / k >= L02_BATT_START_V;
}
