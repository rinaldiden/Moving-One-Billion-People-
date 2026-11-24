/* cc -I../main test_wake_logic.c -o /tmp/tw && /tmp/tw */
#include <stdio.h>
#include "logger02_wake_logic.h"
#define S 1000000LL
static int bad;
static void chk(const char *n, bool got, bool want){ printf("%s %s\n", got==want?"ok  ":"KO  ", n); if(got!=want) bad=1; }
int main(void){
    chk("B mai vista, t=10 s: niente impulso", l02_wake_impulso(10*S,0,0), false);
    chk("B mai vista, t=25 s: primo impulso", l02_wake_impulso(25*S,0,0), true);
    chk("B mai vista, t=40 s, 1 fatto: niente", l02_wake_impulso(40*S,0,1), false);
    chk("B mai vista, t=60 s, 1 fatto: secondo impulso", l02_wake_impulso(60*S,0,1), true);
    chk("B mai vista, t=10 min, 2 fatti: basta", l02_wake_impulso(600*S,0,2), false);
    chk("B ha parlato a 12 s: nessun impulso a 25 s", l02_wake_impulso(25*S,12*S,0), false);
    chk("B ha parlato a 30 s: nessun secondo impulso", l02_wake_impulso(60*S,30*S,1), false);
    /* simulazione: B muta per sempre, tick da 1 s per 10 min -> esattamente 2 impulsi, a 25 e 60 s */
    int fatti=0; int64_t quando[4]={0};
    for(int64_t t=0;t<=600*S;t+=S) if(l02_wake_impulso(t,0,fatti)) quando[fatti++]=t/S;
    chk("B muta 10 min: 2 impulsi", fatti==2, true);
    chk("... a 25 s e 60 s", quando[0]==25 && quando[1]==60, true);
    /* B che parla dopo il primo impulso: niente secondo */
    fatti=0; int64_t bv=0;
    for(int64_t t=0;t<=600*S;t+=S){ if(t==27*S) bv=t; if(l02_wake_impulso(t,bv,fatti)) fatti++; }
    chk("B risponde dopo il 1o impulso: solo 1 impulso", fatti==1, true);
    puts(bad?"FALLITI":"TUTTO OK"); return bad;
}
