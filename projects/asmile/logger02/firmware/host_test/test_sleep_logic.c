/* Prova a secco della logica reale (logger02_sleep_logic.h): cc -I../main test_sleep_logic.c && ./a.out */
#include <stdio.h>
#include "logger02_sleep_logic.h"
#define S 1000000LL
static int bad;
static void chk(const char *n, bool got, bool want){ printf("%s %s\n", got==want?"ok  ":"KO  ", n); if(got!=want) bad=1; }
int main(void){
    l02_sveglio_in_t in = {.ultimo_moto=0, .rete=true, .pezzi_moto=3};   /* fermo da t=0 (+120 s) */
    /* 1) pezzi>0, download che fallisce sempre: solo /api/files ogni 120 s (nessun blocco, nessun trasferimento) */
    bool sveglio_a_4h=true, dorme_prima_di_3h=false;
    for (int64_t t=130*S; t<=4*3600*S; t+=S){ bool v=l02_resto_sveglio(t,&in); if(!v){ if(t<3*3600*S) dorme_prima_di_3h=true; sveglio_a_4h=false; break; } }
    chk("solo /api/files per 4 h: alla fine dorme", !sveglio_a_4h, true);
    chk("... e dorme entro 3 h dal fermo", dorme_prima_di_3h, true);
    /* attesa Mac mai passato: 10 min poi dorme */
    chk("Mac mai passato: sveglio a 5 min", l02_resto_sveglio(120*S+300*S,&in), true);
    chk("Mac mai passato: dorme dopo 10 min", l02_resto_sveglio(120*S+650*S,&in), false);
    /* 2) download vero lungo: 5 h di blocchi ogni 5 s, trasferimento aperto */
    in.trasf=1; in.ultimo_inizio=200*S; bool ok=true;
    for (int64_t t=200*S; t<=5*3600*S; t+=S){ if(t%5==0) in.ultimo_blocco=t; if(!l02_resto_sveglio(t,&in)){ok=false;break;} }
    chk("download vero 5 h (oltre il tetto 3 h): resta sveglio", ok, true);
    /* 3) contatore appeso (nessun blocco da 3 min): non conta */
    in.ultimo_blocco=1000*S; in.ultimo_inizio=1000*S; in.trasf=1;
    chk("contatore appeso senza blocchi: entro 3 min sveglio", l02_resto_sveglio(1100*S,&in), true);
    in.pezzi_moto=0; chk("contatore appeso senza blocchi 4 h dopo: dorme", l02_resto_sveglio(4*3600*S,&in), false);
    /* 4) dopo il tetto, trasferimento non attivo: dorme anche con blocchi vecchi di 1 min */
    in.trasf=0; in.pezzi_moto=3; in.ultimo_blocco=4*3600*S-60*S;
    chk("tetto 3 h senza trasferimento attivo: dorme", l02_resto_sveglio(4*3600*S,&in), false);
    /* 5) wifi giu' */
    in = (l02_sveglio_in_t){.ultimo_moto=0,.pezzi_moto=2,.rete=false,.rete_vista=1000*S,.ultimo_blocco=900*S};
    chk("wifi giu' da 1 min con pezzi: sveglio", l02_resto_sveglio(1060*S,&in), true);
    chk("wifi giu' da 4 min: dorme", l02_resto_sveglio(1240*S,&in), false);
    in.rete_vista=-1; chk("rete mai vista dopo il moto: dorme", l02_resto_sveglio(300*S,&in), false);
    /* 6) 25/11 regola Daniele: solo video a bici FERMA (pezzi_moto=0) -> non tengono sveglio */
    in = (l02_sveglio_in_t){.ultimo_moto=0,.rete=true,.pezzi_moto=0};
    chk("solo pezzi da fermo, Mac mai passato: sveglio a 30 s dal fermo", l02_resto_sveglio(120*S+30*S,&in), true);
    chk("solo pezzi da fermo, Mac mai passato: dorme a 70 s dal fermo", l02_resto_sveglio(120*S+70*S,&in), false);
    in.trasf=1; in.ultimo_inizio=200*S; in.ultimo_blocco=299*S;
    chk("solo pezzi da fermo, Mac che scarica (blocchi ogni s): dorme lo stesso", l02_resto_sveglio(300*S,&in), false);
    { bool sv=false; for (int64_t t=400*S; t<=3*3600*S; t+=S){ in.ultimo_blocco=t-S; if(l02_resto_sveglio(t,&in)){sv=true;break;} }
      chk("solo pezzi da fermo, Mac che scarica per 3 h: mai sveglio (era il caso del 25/11)", sv, false); }
    in.trasf=0; in.ultimo_blocco=170*S;
    chk("solo pezzi da fermo, Mac passato a 50 s dal fermo: sveglio a 55 s", l02_resto_sveglio(175*S,&in), true);
    in.ultimo_blocco=180*S;
    chk("... il Mac non allunga: dorme a 65 s dal fermo", l02_resto_sveglio(185*S,&in), false);
    /* 7) con pezzi in moto il Mac che scarica tiene sveglio come prima */
    in = (l02_sveglio_in_t){.ultimo_moto=0,.rete=true,.pezzi_moto=1,.trasf=1,.ultimo_inizio=200*S,.ultimo_blocco=899*S};
    chk("1 pezzo in moto, Mac che scarica: sveglio", l02_resto_sveglio(900*S,&in), true);
    in.pezzi_moto=0; in.trasf=0;   /* /del dell'ultimo pezzo in moto */
    chk("ultimo pezzo in moto cancellato (fermo da 13 min): dorme subito", l02_resto_sveglio(900*S+5*S,&in), false);
    in = (l02_sveglio_in_t){.ultimo_moto=0,.pezzi_moto=0,.rete=false,.rete_vista=1000*S};
    chk("wifi giu' con solo pezzi da fermo: dorme", l02_resto_sveglio(1060*S,&in), false);
    puts(bad?"FALLITI":"TUTTO OK"); return bad;
}
