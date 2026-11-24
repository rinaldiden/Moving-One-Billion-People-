/* Logica pura "la A ri-sveglia la B" (nessuna dipendenza IDF: si prova sul Mac, vedi ../host_test/test_wake_logic.c).
 * 24/11: la B non si e' svegliata alle 16:39:34 e la A ha registrato 35 min da sola. La A alza WAKE una volta sola all'avvio:
 * se quel fronte si perde (B ancora in dormi, B armata troppo tardi) la B dorme per sempre. Rimedio: se la B non ha mai
 * mandato una riga UART da quando la A e' accesa, a 25 s e a 60 s la A fa un impulso su WAKE (basso 200 ms poi alto).
 * La B non puo' addormentarsi per un impulso: wake_task vuole 6 letture da 500 ms consecutive a livello basso. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#define WAKE_RIPROVA1_S 25
#define WAKE_RIPROVA2_S 60
#define WAKE_IMPULSO_MS 200

/* t_us: tempo dall'avvio della A; b_vista_us: istante dell'ultima riga ricevuta dalla B (0 = mai); fatti: quanti impulsi gia' dati.
 * -> true = dai ora un impulso (e incrementa fatti) */
static inline bool l02_wake_impulso(int64_t t_us, int64_t b_vista_us, int fatti)
{
    if (b_vista_us > 0) return false;                 /* la B parla: e' sveglia */
    if (fatti == 0) return t_us >= WAKE_RIPROVA1_S * 1000000LL;
    if (fatti == 1) return t_us >= WAKE_RIPROVA2_S * 1000000LL;
    return false;                                      /* solo due tentativi: poi niente, non disturbare */
}
