/* Logica pura "resto sveglio per lo scarico" (nessuna dipendenza IDF: si prova sul Mac, vedi ../host_test/). Tempi in us.
 * 25/11 (Daniele): contano SOLO i pezzi registrati con la bici IN MOVIMENTO (pezzi_moto, A + B). Senza pezzi in moto
 * l'IMU ferma da 2 minuti fa dormire (piu' i 60 s di DOPO_SCARICO_S), anche se ci sono file e anche se il Mac sta
 * scaricando (lo scarico interrotto riprende col Range al prossimo giro). */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#define ATTESA_SCARICO_S  600    /* pezzi da scaricare ma il Mac non e' ancora passato */
#define SENZA_RICHIESTE_S 600    /* nessun BLOCCO inviato da 10 minuti con pezzi ancora li': dormo */
#define DOPO_SCARICO_S    60
#define RETE_GIU_S        180
#define TRASF_STALLO_S    180    /* trasferimento aperto ma senza blocchi inviati da 3 min = appeso: non conta */
#define MAX_DAL_FERMO_S   10800  /* tetto totale 3 h dal fermo; non vale per un trasferimento attivo con blocchi in corso */
#define FERMO_S_L         120

typedef struct {
    int64_t ultimo_moto, ultimo_blocco, ultimo_inizio, rete_vista;   /* us; ultimo_blocco = ultimo byte VERO inviato (non /api/files) */
    int trasf, pezzi_moto;     /* pezzi_moto: pezzi video IN MOTO ancora da scaricare (A + B) */
    bool rete;
} l02_sveglio_in_t;

static inline bool l02_resto_sveglio(int64_t t, const l02_sveglio_in_t *i)
{
    int64_t u = i->ultimo_blocco > i->ultimo_inizio ? i->ultimo_blocco : i->ultimo_inizio;
    if (i->pezzi_moto > 0 && i->trasf > 0 && t - u < TRASF_STALLO_S * 1000000LL) return true;
    int64_t fermo_da = i->ultimo_moto + FERMO_S_L * 1000000LL;
    if (t - fermo_da > MAX_DAL_FERMO_S * 1000000LL) return false;
    if (!i->rete)
        return i->pezzi_moto > 0 && i->rete_vista > i->ultimo_moto && t - i->rete_vista < RETE_GIU_S * 1000000LL;
    bool visitato = i->ultimo_blocco > i->ultimo_moto;
    if (i->pezzi_moto > 0) {
        if (!visitato) return t - fermo_da < ATTESA_SCARICO_S * 1000000LL;
        return t - i->ultimo_blocco < SENZA_RICHIESTE_S * 1000000LL;
    }
    /* nessun pezzo in moto: 60 s dal fermo e basta. Le visite del Mac NON allungano (prima: ogni blocco dava altri 60 s e il Mac
     * che scaricava i pezzi da fermo lo teneva sveglio fino al tetto di 3 h, 25/11) */
    return t - fermo_da < DOPO_SCARICO_S * 1000000LL;
}
