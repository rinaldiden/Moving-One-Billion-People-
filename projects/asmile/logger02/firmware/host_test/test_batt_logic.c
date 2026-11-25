/* Prova a secco della logica reale (logger02_batt_logic.h): cc -I../main test_batt_logic.c -lm && ./a.out */
#include <stdio.h>
#include "logger02_batt_logic.h"
#define S 1000000LL
static int bad;
static void chk(const char *n, bool got, bool want){ printf("%s %s\n", got==want?"ok  ":"KO  ", n); if(got!=want) bad=1; }
static bool close_(float a,float b){ return fabsf(a-b)<0.005f; }
/* simula 1 Hz; ritorna il secondo in cui scatta SPEGNI (-1 = mai) */
static int run(l02_batt_t *b, const float *v, int n, int t0){
    for (int k=0;k<n;k++) if (l02_batt_campione(b,(int64_t)(t0+k)*S,v[k])==L02_BATT_SPEGNI) return k;
    return -1;
}
int main(void){
    /* taratura 25/11 (Daniele): V = 1,025 * lettura + 0,01 */
    chk("taratura: 3,24 letti -> 3,33 (tester)", fabsf(l02_batt_vera(3.24f)-3.33f)<0.01f, true);
    chk("taratura: 4,05 letti -> 4,16 (tester)", fabsf(l02_batt_vera(4.05f)-4.16f)<0.01f, true);
    chk("taratura: 3,87 letti -> ~4,0 (tester 14:03)", fabsf(l02_batt_vera(3.87f)-4.0f)<0.03f, true);
    chk("taratura: 2,00 letti -> 2,06", close_(l02_batt_vera(2.00f),2.06f), true);
    chk("taratura: NaN resta NaN", isnan(l02_batt_vera(NAN)), true);
    chk("taratura: <0,5 non toccata", l02_batt_vera(0.2f)==0.2f, true);
    /* 1) sotto 3,0 costante: scatta dopo 10 s (finestra piena a 5 s, poi 10 s) */
    { l02_batt_t b={0}; float v[40]; for(int i=0;i<40;i++) v[i]=2.9f; int k=run(&b,v,40,1);
      chk("2,9 V costante: spegne", k>=0, true);
      chk("... non prima di 10 s dalla finestra piena", k>=4+10, true);
      chk("... e non oltre 4+10 s", k<=4+10, true); }
    /* 2) esattamente 3,0 V non spegne */
    { l02_batt_t b={0}; float v[60]; for(int i=0;i<60;i++) v[i]=3.0f; chk("3,00 V costante: non spegne", run(&b,v,60,1)==-1, true); }
    /* 3) 3,05 V non spegne */
    { l02_batt_t b={0}; float v[60]; for(int i=0;i<60;i++) v[i]=3.05f; chk("3,05 V: non spegne", run(&b,v,60,1)==-1, true); }
    /* 4) lettura che salta (cella scarica sotto carico): media sopra soglia, nessuno spegnimento per i picchi */
    {       float v[120]; for(int i=0;i<120;i++) v[i]=(i%2)?3.8f:2.4f; l02_batt_t c={0};
      chk("a dente di sega 2,4/3,8 (media 3,1): non spegne", run(&c,v,120,1)==-1, true); }
    /* 5) picco singolo basso in batteria sana */
    { l02_batt_t b={0}; float v[60]; for(int i=0;i<60;i++) v[i]=3.9f; v[20]=1.0f; v[21]=0.9f; v[40]=2.0f;
      chk("picchi isolati a 1,0 V in batteria 3,9: non spegne", run(&b,v,60,1)==-1, true); }
    /* 6) 9 s sotto poi risale: azzera */
    { l02_batt_t b={0}; float v[80]; for(int i=0;i<80;i++) v[i]=3.5f; for(int i=10;i<10+6;i++) v[i]=2.0f;
      chk("calo breve (6 s a 2,0 V: media <3 V per ~8 s, <10 consecutivi): non spegne", run(&b,v,80,1)==-1, true); }
    { l02_batt_t b={0}; float v[80]; for(int i=0;i<80;i++) v[i]=2.9f; for(int i=0;i<8;i++) v[i]=3.5f;
      for(int i=15;i<25;i++) v[i]=3.9f;    /* ritorno sopra a meta': il conteggio riparte */
      int k=run(&b,v,80,1);
      chk("ritorno sopra 3 V a meta': scatta solo 10 s DOPO il nuovo calo", k>=25, true); }
    /* 7) batteria assente: non spegne, segnala; poi azzera il conteggio */
    { l02_batt_t b={0}; chk("lettura -1: assente", l02_batt_campione(&b,S,-1.0f)==L02_BATT_ASSENTE, true);
      chk("NaN: assente", l02_batt_campione(&b,2*S,NAN)==L02_BATT_ASSENTE, true);
      chk("0,4 V: assente", l02_batt_campione(&b,3*S,0.4f)==L02_BATT_ASSENTE, true);
      float v[50]; for(int i=0;i<50;i++) v[i]=-1; chk("5 min senza lettura: non spegne", run(&b,v,50,10)==-1, true);
      float w[12]; for(int i=0;i<12;i++) w[i]=2.5f; for(int i=0;i<4;i++) l02_batt_campione(&b,(int64_t)(100+i)*S,2.5f);
      l02_batt_campione(&b,104*S,-1.0f);   /* lettura persa a meta' calo: conteggio azzerato */
      chk("dopo lettura persa il calo riparte da zero", run(&b,w,12,105)>=14 || run(&b,w,12,105)==-1, true); }
    /* 8) avvio: isteresi 3,1 */
    { float a[6]={3.0f,3.0f,3.05f,3.0f,3.02f,3.0f}, m; chk("avvio a 3,01 V: rifiuta", !l02_batt_avvio_ok(a,6,&m), true);
      float c[6]={3.08f,3.09f,3.07f,3.08f,3.09f,3.08f}; chk("avvio a 3,08 V (fra 3,0 e 3,1): rifiuta", !l02_batt_avvio_ok(c,6,&m), true);
      float d[6]={3.1f,3.1f,3.1f,3.1f,3.1f,3.1f}; chk("avvio a 3,10 V: parte", l02_batt_avvio_ok(d,6,&m), true);
      float e[6]={3.8f,3.8f,1.0f,3.8f,3.8f,3.8f}; chk("avvio 3,8 V con un picco a 1,0: parte (media 3,3)", l02_batt_avvio_ok(e,6,&m), true);
      float f[6]={2.2f,3.9f,2.2f,2.3f,2.2f,2.4f}; chk("avvio con un picco alto isolato in cella vuota: rifiuta", !l02_batt_avvio_ok(f,6,&m), true);
      float g[6]={-1,-1,-1,-1,-1,-1}; chk("avvio con batteria assente: parte", l02_batt_avvio_ok(g,6,&m), true);
      chk("... media -1", m==-1.0f, true);
      float h[6]={-1,-1,2.5f,-1,2.6f,-1}; chk("avvio con letture miste, valide basse: rifiuta", !l02_batt_avvio_ok(h,6,&m), true); }
    /* 9) caso reale 24/11: lettura grezza 2,03 -> spegne (anche con la retta nuova, 2,09 V) */
    { l02_batt_t b={0}; float v[30]; for(int i=0;i<30;i++) v[i]=l02_batt_vera(2.03f); chk("caso 24/11 (grezza 2,03): spegne", run(&b,v,30,1)>=0, true); }
    /* 10) soglie in letture GREZZE con la taratura 25/11: spegnimento a 3,0 V veri = grezza ~2,917 */
    { l02_batt_t b={0}; float v[40]; for(int i=0;i<40;i++) v[i]=l02_batt_vera(2.90f); chk("grezza 2,90 (vera 2,98): spegne", run(&b,v,40,1)>=0, true); }
    { l02_batt_t b={0}; float v[60]; for(int i=0;i<60;i++) v[i]=l02_batt_vera(2.93f); chk("grezza 2,93 (vera 3,01): non spegne", run(&b,v,60,1)==-1, true); }
    { l02_batt_t b={0}; float v[60]; for(int i=0;i<60;i++) v[i]=l02_batt_vera(3.10f); chk("grezza 3,10 (vera 3,19, col vecchio 0,936 = 2,90 e spegneva): non spegne", run(&b,v,60,1)==-1, true); }
    /* 11) avvio 3,1 V veri = grezza ~3,015 */
    { float a[6], m; for(int i=0;i<6;i++) a[i]=l02_batt_vera(3.00f); chk("avvio grezza 3,00 (vera 3,085): rifiuta", !l02_batt_avvio_ok(a,6,&m), true);
      for(int i=0;i<6;i++) a[i]=l02_batt_vera(3.03f); chk("avvio grezza 3,03 (vera 3,116): parte", l02_batt_avvio_ok(a,6,&m), true);
      for(int i=0;i<6;i++) a[i]=l02_batt_vera(3.25f); chk("avvio grezza 3,25 (vera 3,34, col vecchio 0,936 = 3,04 rifiutava): parte", l02_batt_avvio_ok(a,6,&m), true); }
    printf(bad?"ERRORE\n":"TUTTO OK\n");
    return bad;
}
