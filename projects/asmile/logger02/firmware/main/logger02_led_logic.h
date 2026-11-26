/* LED che respira = stato di carica della batteria (solo A). Logica pura (nessuna dipendenza IDF, si prova sul Mac:
 * ../host_test/test_led_logic.c). Richiesta di Daniele 26/11/2026: «voglio che il led respiri, deep breath»:
 *    3,6 - 4,2 V  verde      carica
 *    3,3 - 3,6 V  arancione
 *    3,1 - 3,3 V  rosso      da ricaricare
 *  - Tensione = quella VERA (tarata in logger02_imu.c, 1,025 * lettura + 0,01) e mediata (media mobile di 5 letture,
 *    una al secondo): un picco di carico non fa cambiare colore.
 *  - Sopra 4,2 V (in carica) = verde. Sotto 3,1 V da accesa (fino allo spegnimento a 3,0 V, batt_logic) = rosso.
 *  - Isteresi L02_LED_ISTERESI_V sui confini: a 3,30-3,31 V col carico che va e viene il colore non sfarfalla.
 *  - Batteria non leggibile = LED spento (non invento un colore: "non so" e' spento).
 *  - Respiro: curva exp(-cos) (quella delle luci di riposo dei portatili): parte da buio, sale piano, pieno a meta', scende.
 *    L02_LED_RESPIRO_MS = un respiro intero (inspira + espira), 4 s + 4 s = respiro profondo. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <math.h>

#define L02_LED_VERDE_V      3.6f
#define L02_LED_ARANCIO_V    3.3f
#define L02_LED_ISTERESI_V   0.03f
#define L02_LED_RESPIRO_MS   8000u    /* deep breath: 4 s dentro, 4 s fuori */
#define L02_LED_MAX          0.60f    /* luminosita' massima (0-1): basta da vedere, non abbaglia, consuma poco */

typedef enum { L02_LED_SPENTO = 0, L02_LED_VERDE = 1, L02_LED_ARANCIO = 2, L02_LED_ROSSO = 3 } l02_led_colore_t;

static inline const char *l02_led_nome(l02_led_colore_t c)
{
    return c == L02_LED_VERDE ? "verde" : c == L02_LED_ARANCIO ? "arancione" : c == L02_LED_ROSSO ? "rosso" : "spento";
}

static inline l02_led_colore_t l02_led_fascia(float v)
{
    return v >= L02_LED_VERDE_V ? L02_LED_VERDE : v >= L02_LED_ARANCIO_V ? L02_LED_ARANCIO : L02_LED_ROSSO;
}

/* colore da tenere: prima = colore di adesso, v = tensione vera media (< 0,5 V o NaN = non leggibile) */
static inline l02_led_colore_t l02_led_colore(l02_led_colore_t prima, float v)
{
    if (isnan(v) || v < 0.5f) return L02_LED_SPENTO;
    l02_led_colore_t nuovo = l02_led_fascia(v);
    if (prima == L02_LED_SPENTO || nuovo == prima) return nuovo;
    float lo = prima == L02_LED_VERDE ? L02_LED_VERDE_V : prima == L02_LED_ARANCIO ? L02_LED_ARANCIO_V : -1e9f;
    float hi = prima == L02_LED_VERDE ? 1e9f : prima == L02_LED_ARANCIO ? L02_LED_VERDE_V : L02_LED_ARANCIO_V;
    return (v >= lo - L02_LED_ISTERESI_V && v < hi + L02_LED_ISTERESI_V) ? prima : nuovo;
}

/* luminosita' del respiro (0-1) al tempo t_ms: 0 a inizio respiro, 1 a meta' */
static inline float l02_led_respiro(uint32_t t_ms)
{
    const float e = 2.718281828f, ie = 0.367879441f;
    float x = 6.283185307f * (float)(t_ms % L02_LED_RESPIRO_MS) / (float)L02_LED_RESPIRO_MS;
    return (expf(-cosf(x)) - ie) / (e - ie);
}

/* quanto di rosso / verde / blu (0-1) per il colore, gia' moltiplicato per respiro e massimo */
static inline void l02_led_rgb(l02_led_colore_t c, float respiro, float rgb[3])
{
    static const float tinta[4][3] = {
        {0, 0, 0},          /* spento */
        {0, 1, 0},          /* verde */
        {1, 0.25f, 0},      /* arancione: il verde del KY-016 e' molto piu' luminoso del rosso, ne basta un quarto */
        {1, 0, 0},          /* rosso */
    };
    for (int k = 0; k < 3; k++) rgb[k] = tinta[c][k] * respiro * L02_LED_MAX;
}
