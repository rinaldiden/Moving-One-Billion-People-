/* Prova a secco della rete di sicurezza (logger02_rete_logic.h): cc -I../main test_rete_logic.c && ./a.out */
#include <stdio.h>
#include "logger02_rete_logic.h"
#define S 1000000LL
static int bad;
static void chk(const char *n, int got, int want){ printf("%s %s (%d)\n", got==want?"ok  ":"KO  ", n, got); if(got!=want) bad=1; }

/* fa girare il passo ogni 5 s da t0 a t1, ritorna la prima azione "forte" e quando */
static l02_rete_azione_t gira(l02_rete_st_t *s, l02_rete_in_t *in, int64_t t0, int64_t t1, l02_rete_azione_t cerca, int64_t *quando)
{
    for (int64_t t = t0; t <= t1; t += 5 * S) {
        l02_rete_azione_t a = l02_rete_passo(t, s, in);
        if (a == cerca) { if (quando) *quando = t; return a; }
    }
    return L02_R_NIENTE;
}

int main(void){
    int64_t q;
    /* 1) rete ok sempre: niente */
    l02_rete_st_t s = {0}; l02_rete_in_t in = {.ok = true, .pausa = true};
    chk("rete ok: niente", l02_rete_passo(10*S, &s, &in), L02_R_NIENTE);
    l02_rete_passo(100*S, &s, &in);                     /* ultima volta ok: t=100 */
    /* 2) rete giù da t=100 s, in pausa: riprova a 60 s, reset C6 a 120 s, riavvio a 180 s */
    in.ok = false;
    chk("riprova a 60 s", gira(&s, &in, 105*S, 400*S, L02_R_RIPROVA, &q), L02_R_RIPROVA); chk("... a t=160", (int)(q/S), 160);
    chk("reset C6 a 120 s", gira(&s, &in, q, 400*S, L02_R_RESET_C6, &q), L02_R_RESET_C6); chk("... a t=220", (int)(q/S), 220);
    chk("riavvio 60 s dopo", gira(&s, &in, q, 400*S, L02_R_RIAVVIA, &q), L02_R_RIAVVIA); chk("... a t=280", (int)(q/S), 280);
    /* 3) torna la rete dopo il reset del C6: TORNATA, poi niente */
    s = (l02_rete_st_t){.ok_t = 0}; in = (l02_rete_in_t){.ok = false, .pausa = true};
    gira(&s, &in, 0, 125*S, L02_R_RESET_C6, &q);
    in.ok = true;
    chk("rete tornata dopo reset C6", l02_rete_passo(q + 30*S, &s, &in), L02_R_TORNATA);
    chk("poi niente", l02_rete_passo(q + 35*S, &s, &in), L02_R_NIENTE);
    /* 4) in movimento: reset C6 sì, riavvio no (aspetta la pausa), poi riavvia appena in pausa */
    s = (l02_rete_st_t){0}; in = (l02_rete_in_t){.ok = false, .pausa = false};
    chk("in movimento: reset C6 sì", gira(&s, &in, 0, 200*S, L02_R_RESET_C6, &q), L02_R_RESET_C6);
    chk("in movimento: niente riavvio per 10 min", gira(&s, &in, q, q + 600*S, L02_R_RIAVVIA, NULL), L02_R_NIENTE);
    chk("in movimento: ASPETTA", l02_rete_passo(q + 700*S, &s, &in), L02_R_ASPETTA);
    in.pausa = true;
    chk("appena in pausa: riavvia", l02_rete_passo(q + 705*S, &s, &in), L02_R_RIAVVIA);
    /* 5) scarico in corso: mai riavvio */
    s = (l02_rete_st_t){0}; in = (l02_rete_in_t){.ok = false, .pausa = true, .scarico = true};
    gira(&s, &in, 0, 200*S, L02_R_RESET_C6, &q);
    chk("scarico in corso: niente riavvio", gira(&s, &in, q, q + 3600*S, L02_R_RIAVVIA, NULL), L02_R_NIENTE);
    /* 6) fuori portata (C6 dice rete non trovata ogni ~5 s): niente reset, niente riavvio per 1 h */
    s = (l02_rete_st_t){0}; in = (l02_rete_in_t){.ok = false, .pausa = true};
    int forte = 0;
    for (int64_t t = 0; t < 3600*S; t += 5*S) { in.noap_t = t - 3*S; l02_rete_azione_t a = l02_rete_passo(t, &s, &in); if (a != L02_R_NIENTE) forte = a; }
    chk("fuori portata 1 h: nessuna azione", forte, 0);
    /* 7) C6 che smette di parlare dopo il fuori portata: si riparte dai 60 s */
    int64_t ult = 3600*S - 5*S;
    chk("C6 muto dopo fuori portata: riprova 60+ s dopo l'ultimo 'non trovata'",
        gira(&s, &in, 3600*S, 4000*S, L02_R_RIPROVA, &q), L02_R_RIPROVA);
    chk("... non prima di 60 s", q - ult >= 60*S, 1);
    /* 8) riavvio già fatto in questo risveglio: niente riavvio, reset C6 ogni 5 min */
    s = (l02_rete_st_t){0}; in = (l02_rete_in_t){.ok = false, .pausa = true, .riavvii = 1};
    gira(&s, &in, 0, 200*S, L02_R_RESET_C6, &q);
    chk("dopo un riavvio: niente secondo riavvio in 1 h", gira(&s, &in, q, q + 3600*S, L02_R_RIAVVIA, NULL), L02_R_NIENTE);
    int64_t q2; s.t_reset = q; s.fase = 2;
    chk("dopo un riavvio: reset C6 di nuovo", gira(&s, &in, q + 5*S, q + 900*S, L02_R_RESET_C6, &q2), L02_R_RESET_C6);
    chk("... dopo 5 min", (int)((q2 - q)/S), 300);
    /* 9) rete che va e viene (ok 1 volta ogni 50 s): mai reset */
    s = (l02_rete_st_t){0}; in = (l02_rete_in_t){.pausa = true}; forte = 0;
    for (int64_t t = 0; t < 3600*S; t += 5*S) { in.ok = (t / S) % 50 == 0; l02_rete_azione_t a = l02_rete_passo(t, &s, &in); if (a >= L02_R_RIPROVA) forte = a; }
    chk("rete a singhiozzo (ok ogni 50 s): nessun reset", forte, 0);
    printf(bad ? "\nFALLITO\n" : "\nTUTTO OK\n");
    return bad;
}
