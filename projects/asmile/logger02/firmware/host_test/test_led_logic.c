/* Prova a secco del LED che respira (logger02_led_logic.h): cc -I../main test_led_logic.c -lm && ./a.out */
#include <stdio.h>
#include "logger02_led_logic.h"
static int bad;
static void chk(const char *n, bool got, bool want){ printf("%s %s\n", got==want?"ok  ":"KO  ", n); if(got!=want) bad=1; }
#define S L02_LED_SPENTO
#define V L02_LED_VERDE
#define A L02_LED_ARANCIO
#define R L02_LED_ROSSO
int main(void){
    /* fasce di Daniele 26/11, partendo da spento (accensione) */
    chk("4,20 V verde", l02_led_colore(S, 4.20f)==V, true);
    chk("3,60 V verde", l02_led_colore(S, 3.60f)==V, true);
    chk("4,30 V (in carica) verde", l02_led_colore(S, 4.30f)==V, true);
    chk("3,59 V arancione", l02_led_colore(S, 3.59f)==A, true);
    chk("3,30 V arancione", l02_led_colore(S, 3.30f)==A, true);
    chk("3,29 V rosso", l02_led_colore(S, 3.29f)==R, true);
    chk("3,10 V rosso", l02_led_colore(S, 3.10f)==R, true);
    chk("3,05 V (fra 3,0 e 3,1, prima dello spegnimento) rosso", l02_led_colore(S, 3.05f)==R, true);
    chk("non leggibile (-1) spento", l02_led_colore(V, -1.0f)==S, true);
    chk("NaN spento", l02_led_colore(A, NAN)==S, true);
    /* isteresi: vicino al confine resta il colore di prima, oltre l'isteresi cambia */
    chk("verde a 3,58 resta verde", l02_led_colore(V, 3.58f)==V, true);
    chk("verde a 3,56 passa arancione", l02_led_colore(V, 3.56f)==A, true);
    chk("arancione a 3,62 resta arancione", l02_led_colore(A, 3.62f)==A, true);
    chk("arancione a 3,64 passa verde", l02_led_colore(A, 3.64f)==V, true);
    chk("arancione a 3,28 resta arancione", l02_led_colore(A, 3.28f)==A, true);
    chk("arancione a 3,26 passa rosso", l02_led_colore(A, 3.26f)==R, true);
    chk("rosso a 3,32 resta rosso", l02_led_colore(R, 3.32f)==R, true);
    chk("rosso a 3,34 passa arancione", l02_led_colore(R, 3.34f)==A, true);
    chk("rosso a 4,1 (messo in carica) passa verde", l02_led_colore(R, 4.10f)==V, true);
    /* sfarfallio: tensione che oscilla 3,29/3,31 col carico non cambia colore a ogni lettura */
    { l02_led_colore_t c = A; int cambi = 0;
      for (int i = 0; i < 100; i++) { l02_led_colore_t n = l02_led_colore(c, (i%2)?3.31f:3.29f); if (n!=c) cambi++; c = n; }
      chk("3,29/3,31 alternati: nessun cambio", cambi==0, true); }
    /* respiro */
    chk("respiro: buio a inizio", l02_led_respiro(0) < 0.001f, true);
    chk("respiro: pieno a meta' (4 s)", fabsf(l02_led_respiro(L02_LED_RESPIRO_MS/2)-1.0f) < 0.001f, true);
    chk("respiro: buio a fine (8 s = 0)", l02_led_respiro(L02_LED_RESPIRO_MS) < 0.001f, true);
    chk("respiro: simmetrico (2 s = 6 s)", fabsf(l02_led_respiro(2000)-l02_led_respiro(6000)) < 0.001f, true);
    { int sale = 1; float p = -1; for (uint32_t t = 0; t <= L02_LED_RESPIRO_MS/2; t += 20) { float b = l02_led_respiro(t); if (b < p - 1e-6f) sale = 0; p = b; }
      chk("respiro: sale senza scatti fino a meta'", sale, true); }
    chk("respiro: piano all'inizio (a 1 s sotto il 15%)", l02_led_respiro(1000) < 0.15f, true);
    /* colori */
    { float c[3]; l02_led_rgb(V, 1.0f, c); chk("verde: solo G, al massimo", c[0]==0 && c[2]==0 && fabsf(c[1]-L02_LED_MAX)<1e-6f, true); }
    { float c[3]; l02_led_rgb(A, 1.0f, c); chk("arancione: R pieno + un quarto di G", c[0]>c[1] && c[1]>0 && c[2]==0, true); }
    { float c[3]; l02_led_rgb(R, 0.5f, c); chk("rosso a meta' respiro: solo R, meta'", c[1]==0 && c[2]==0 && fabsf(c[0]-0.5f*L02_LED_MAX)<1e-6f, true); }
    { float c[3]; l02_led_rgb(S, 1.0f, c); chk("spento: tutto 0", c[0]==0 && c[1]==0 && c[2]==0, true); }
    printf(bad ? "\nQUALCOSA NON VA\n" : "\ntutto ok\n");
    return bad;
}
