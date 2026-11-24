/* A: MPU6050 a 50 Hz (CSV con lo stesso orologio dei fotogrammi), batteria, autospegnimento e deep sleep.
 * Porta di logger_autospegni.py + imu_wake.py del logger001:
 *   fermo = gyro < 3 °/s e variazione accel < 30 mg; dopo FERMO_S secondi fermo (e almeno MIN_ACCESO_S acceso; col wifi aspetta lo scarico del Mac)
 *   → chiude i file, addormenta la B, arma il motion interrupt dell'IMU (soglia di Daniele 17/11: al minimo)
 *   e va in deep sleep. Si sveglia quando l'INT (GPIO4) si alza. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <unistd.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "protocol_examples_common.h"
#include "logger02.h"
#include "logger02_sleep_logic.h"
#include "logger02_batt_logic.h"

static const char *TAG = "imu";

#define MPU         0x68
#define FERMO_S     120         /* Daniele 21/11: deep sleep dopo 2 minuti fermo (era 5) */
#define MIN_ACCESO_S 120
#define MOTO_FILA   3           /* movimento vero = 3 campioni di fila (60 ms): un campione storto non tiene sveglio */
/* a casa col wifi: resta sveglio finché il Mac scarica (Daniele 21/11) */
/* 23/11 (Daniele: «deve essere così sempre»): ferma col wifi → registrazione in pausa (pezzi chiusi) e resta sveglia
 * finché sulla SD di A e B ci sono pezzi da scaricare e il Mac li sta prendendo; poi dorme. */
#define GYRO_FERMO  3.0f
#define ACC_FERMO_G 0.030f

static i2c_master_dev_handle_t s_mpu;
static FILE *s_csv;
static volatile int64_t s_ultimo_moto;
static float s_ax, s_ay, s_az, s_gx, s_gy, s_gz;
static uint32_t s_campioni, s_errori;
static adc_oneshot_unit_handle_t s_adc;
static adc_cali_handle_t s_cali;
static float s_batt = -1;
static l02_batt_t s_bl;                         /* media mobile + conteggio sotto 3 V (logger02_batt_logic.h) */
static l02_batt_esito_t s_batt_esito = L02_BATT_ASSENTE;
static int64_t s_batt_avviso_t;
static volatile int64_t s_ultimo_scarico;      /* ultimo BLOCCO davvero inviato (non /api/files) */
static volatile int64_t s_ultimo_inizio;
static int s_moto_fila;
static bool s_in_pausa;

void logger02_scarico_visto(void)
{
    s_ultimo_scarico = esp_timer_get_time();
}

/* 24/11 (Daniele: «mentre si scarica l'apparecchio resta sveglio»): contatore dei trasferimenti aperti */
static volatile int s_trasf;
static volatile int64_t s_rete_vista;
void logger02_scarico_inizio(void)
{
    s_ultimo_inizio = esp_timer_get_time();
    __atomic_add_fetch(&s_trasf, 1, __ATOMIC_SEQ_CST);
}
void logger02_scarico_fine(void)
{
    if (__atomic_sub_fetch(&s_trasf, 1, __ATOMIC_SEQ_CST) < 0) __atomic_store_n(&s_trasf, 0, __ATOMIC_SEQ_CST);
}

static bool rete_ok(void)
{
    esp_netif_t *n = get_example_netif();
    esp_netif_ip_info_t ip;
    return n && esp_netif_is_netif_up(n) && esp_netif_get_ip_info(n, &ip) == ESP_OK && ip.ip.addr != 0;
}

/* fermo da FERMO_S: dorme, salvo scarico in corso. Logica pura in logger02_sleep_logic.h (host_test). */
static bool resto_sveglio_per_scarico(int64_t t)
{
    int b = logger02_b_da_scaricare();
    l02_sveglio_in_t in = {.ultimo_moto = s_ultimo_moto, .ultimo_blocco = s_ultimo_scarico, .ultimo_inizio = s_ultimo_inizio,
                           .rete_vista = s_rete_vista, .trasf = __atomic_load_n(&s_trasf, __ATOMIC_SEQ_CST),
                           .pezzi = logger02_rec_da_scaricare() + (b > 0 ? b : 0), .rete = rete_ok()};
    return l02_resto_sveglio(t, &in);
}

static esp_err_t w(uint8_t reg, uint8_t v)
{
    uint8_t b[2] = {reg, v};
    return i2c_master_transmit(s_mpu, b, 2, 50);
}

static esp_err_t r(uint8_t reg, uint8_t *out, size_t n)
{
    return i2c_master_transmit_receive(s_mpu, &reg, 1, out, n, 50);
}

static char s_sess[24];
static uint32_t s_pezzo;
static int64_t s_pezzo_t0;

/* un file IMU al minuto (come i pezzi video): chiuderlo è l'unico modo sicuro di salvarlo senza fsync */
static void apri_csv(void)
{
    char p[112];
    if (!s_sess[0]) logger02_nome_sessione(s_sess, sizeof(s_sess));
    snprintf(p, sizeof(p), L02_REC_DIR "/sensors_%s_%05lu.csv", s_sess, (unsigned long)s_pezzo++);
    s_pezzo_t0 = esp_timer_get_time();
    s_csv = fopen(p, "w");
    if (s_csv) {
        setvbuf(s_csv, NULL, _IOFBF, 16 * 1024);
        fprintf(s_csv, "t_us,frame,imu_ax_g,imu_ay_g,imu_az_g,imu_gx_dps,imu_gy_dps,imu_gz_dps,batt_v\n");
        ESP_LOGI(TAG, "scrivo %s", p);
    }
}

static float leggi_batteria_adc(void);

static void batt_adc_init(void)                 /* idempotente: la chiama anche il controllo all'avvio */
{
    if (s_adc) return;
    adc_oneshot_unit_init_cfg_t uc = {.unit_id = ADC_UNIT_1};
    if (adc_oneshot_new_unit(&uc, &s_adc) == ESP_OK) {
        adc_oneshot_chan_cfg_t cc = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
        adc_oneshot_config_channel(s_adc, ADC_CHANNEL_4, &cc);      /* GPIO20 = ADC1_CH4 */
        adc_cali_curve_fitting_config_t cf = {.unit_id = ADC_UNIT_1, .chan = ADC_CHANNEL_4, .atten = ADC_ATTEN_DB_12,
                                              .bitwidth = ADC_BITWIDTH_DEFAULT};
        adc_cali_create_scheme_curve_fitting(&cf, &s_cali);
    }
}

static float leggi_batteria(void)
{
    if (logger02_analogico) xSemaphoreTake(logger02_analogico, portMAX_DELAY);
    float v = leggi_batteria_adc();
    if (logger02_analogico) xSemaphoreGive(logger02_analogico);
    return v;
}

static float leggi_batteria_adc(void)
{
    int raw, mv;
    if (!s_adc) return -1;
    /* Pin scollegato = galleggia e legge numeri a caso (18/11: "10,56 V" senza partitore né batteria, Daniele).
     * Prova: col pull-down interno (~45 kΩ) un pin libero va a ~0 V; col partitore 100k/33k collegato resta
     * sopra (12 V → ~1,9 V). Poi tolgo il pull-down e leggo il valore vero. */
    gpio_pulldown_en(L02_PIN_BATT_ADC);
    vTaskDelay(pdMS_TO_TICKS(2));
    bool libero = adc_oneshot_read(s_adc, ADC_CHANNEL_4, &raw) != ESP_OK ||
                  (s_cali && adc_cali_raw_to_voltage(s_cali, raw, &mv) == ESP_OK && mv < 150);
    gpio_pulldown_dis(L02_PIN_BATT_ADC);
    if (libero) return -1;
    vTaskDelay(pdMS_TO_TICKS(2));
    if (adc_oneshot_read(s_adc, ADC_CHANNEL_4, &raw) != ESP_OK) return -1;
    if (s_cali && adc_cali_raw_to_voltage(s_cali, raw, &mv) == ESP_OK) {
        float v = l02_batt_vera(mv / 1000.0f * (100.0f + 33.0f) / 33.0f);   /* taratura 24/11: logger02_batt_logic.h */
        /* partitore scollegato = pin libero, gia' escluso dal pull-down qui sopra; sotto 0,5 V = lettura impossibile.
         * (24/11: il vecchio "sotto 2 V = non collegato" nascondeva la cella vera a 1,9 V) */
        return l02_batt_valida(v) ? v : -1;
    }
    return -1;
}

static void imu_task(void *arg)
{
    uint8_t d[14];
    float pax = 0, pay = 0, paz = 0;
    TickType_t t0 = xTaskGetTickCount();
    while (1) {
        vTaskDelayUntil(&t0, pdMS_TO_TICKS(20));           /* 50 Hz */
        int64_t t = esp_timer_get_time();
        if (r(0x3B, d, 14) != ESP_OK) {
            s_errori++;
            s_ultimo_moto = t;                              /* IMU che non risponde = non spengo */
            continue;
        }
        int16_t v[7];
        for (int i = 0; i < 7; i++) v[i] = (int16_t)(d[2 * i] << 8 | d[2 * i + 1]);
        s_ax = v[0] / 16384.0f; s_ay = v[1] / 16384.0f; s_az = v[2] / 16384.0f;
        s_gx = v[4] / 131.0f;   s_gy = v[5] / 131.0f;   s_gz = v[6] / 131.0f;
        s_campioni++;
        float dacc = fmaxf(fabsf(s_ax - pax), fmaxf(fabsf(s_ay - pay), fabsf(s_az - paz)));
        float g = fmaxf(fabsf(s_gx), fmaxf(fabsf(s_gy), fabsf(s_gz)));
        if (g > GYRO_FERMO || dacc > ACC_FERMO_G) {
            if (++s_moto_fila >= MOTO_FILA) s_ultimo_moto = t;
        } else {
            s_moto_fila = 0;
        }
        pax = s_ax; pay = s_ay; paz = s_az;
        if (s_campioni % 50 == 0) {
            s_batt = leggi_batteria(); if (rete_ok()) s_rete_vista = t;
            /* protezione 3 V (Daniele 24/11): PRIORITARIA su scarico, pausa e tutto il resto */
            s_batt_esito = l02_batt_campione(&s_bl, t, s_batt);
            if (s_batt_esito == L02_BATT_SPEGNI) {
                char m[96];
                snprintf(m, sizeof(m), "batteria %.2f V (media %.2f) sotto %.1f V da %d s: spengo", s_batt, s_bl.media,
                         L02_BATT_OFF_V, L02_BATT_OFF_S);
                logger02_spegni_batteria(m, s_bl.media);
            } else if (s_batt_esito == L02_BATT_ASSENTE && t - s_batt_avviso_t > 60000000LL) {
                s_batt_avviso_t = t;
                ESP_LOGW(TAG, "batteria non leggibile (<%.1f V o NaN): protezione 3 V NON attiva", L02_BATT_ASSENTE_V);
            }
        }
        if (s_csv) {
            fprintf(s_csv, "%lld,%lu,%.4f,%.4f,%.4f,%.2f,%.2f,%.2f,", (long long)t, (unsigned long)logger02_rec_frame(),
                    s_ax, s_ay, s_az, s_gx, s_gy, s_gz);
            if (s_campioni % 50 == 0 && s_batt > 0) fprintf(s_csv, "%.2f", s_batt);
            fputc('\n', s_csv);
            if (t - s_pezzo_t0 > 60000000LL) { fclose(s_csv); s_csv = NULL; apri_csv(); }
        }
        bool ferma = t > MIN_ACCESO_S * 1000000LL && t - s_ultimo_moto > FERMO_S * 1000000LL;
        if (ferma != s_in_pausa && s_campioni % 25 == 0) {     /* pausa/ripresa su A e B (ogni 0,5 s al massimo) */
            s_in_pausa = ferma;
            logger02_rec_pausa(ferma);
            logger02_link_invia(ferma ? "P" : "R");
        }
        if (ferma && s_campioni % 50 == 0 && !resto_sveglio_per_scarico(t)) {     /* una volta al secondo basta */
            logger02_dormi("bici ferma da 2 minuti, niente da scaricare");
        }
    }
}

esp_err_t logger02_imu_start(void)
{
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_master_get_bus_handle(0, &bus));
    i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = MPU, .scl_speed_hz = 100000};
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dc, &s_mpu));
    uint8_t who = 0;
    if (r(0x75, &who, 1) != ESP_OK || who != 0x68) {
        ESP_LOGE(TAG, "MPU6050 non risponde (WHO_AM_I 0x%02x)", who);
        return ESP_FAIL;
    }
    w(0x6B, 0x00); w(0x6C, 0x00);      /* sveglia, tutti gli assi */
    w(0x1A, 0x03);                      /* DLPF 44 Hz */
    w(0x1B, 0x00); w(0x1C, 0x00);       /* ±250 °/s, ±2 g */
    w(0x38, 0x00);
    uint8_t s; r(0x3A, &s, 1);          /* pulisce il latch dell'INT */

    batt_adc_init();

    s_ultimo_moto = esp_timer_get_time();
    apri_csv();
    xTaskCreatePinnedToCore(imu_task, "imu", 4096, NULL, 9, NULL, 0);
    ESP_LOGI(TAG, "MPU6050 ok, 50 Hz; spegnimento dopo %d s fermo", FERMO_S);
    return ESP_OK;
}

float logger02_batteria_v(void)
{
    return s_batt;
}

void logger02_imu_stato(char *json, size_t n)
{
    int64_t fermo = (esp_timer_get_time() - s_ultimo_moto) / 1000000;
    char bv[24];
    if (s_batt > 0) snprintf(bv, sizeof(bv), "%.2f", s_batt);
    else snprintf(bv, sizeof(bv), "\"non collegata\"");
    snprintf(json, n, "{\"campioni\":%lu,\"errori\":%lu,\"acc_g\":[%.3f,%.3f,%.3f],\"gyro_dps\":[%.2f,%.2f,%.2f],"
             "\"fermo_s\":%lld,\"spegne_dopo_s\":%d,\"batteria_v\":%s,\"batt_media_v\":%.2f,\"protezione_3v\":\"%s\"}",
             (unsigned long)s_campioni, (unsigned long)s_errori, s_ax, s_ay, s_az, s_gx, s_gy, s_gz,
             (long long)fermo, FERMO_S, bv, s_bl.n ? s_bl.media : 0.0f,
             s_batt_esito == L02_BATT_ASSENTE ? "NON attiva (batteria non leggibile)" : "attiva");
}

/* arma il motion interrupt come imu_wake.py "arma" (taratura di stamattina) */
static bool arma_imu(void)
{
    w(0x6B, 0x00);
    w(0x1C, 0x04);          /* ±2 g + passa-alto 0,63 Hz */
    w(0x1F, 1);             /* MOT_THR minimo */
    w(0x20, 1);             /* MOT_DUR 1 campione */
    w(0x69, 0x15);
    w(0x37, 0x20);          /* INT attivo alto, push-pull, latch */
    w(0x38, 0x40);          /* solo MOT_INT */
    vTaskDelay(pdMS_TO_TICKS(50));
    w(0x6C, (3 << 6) | 0x07);   /* basso consumo 40 Hz, giroscopio spento */
    w(0x6B, 0x28);              /* CYCLE */
    uint8_t s;
    r(0x3A, &s, 1);
    vTaskDelay(pdMS_TO_TICKS(300));
    r(0x3A, &s, 1);
    return !(s & 0x40) && !gpio_get_level(L02_PIN_IMU_INT);
}

uint32_t g_dormi_prova_s;   /* >0: sveglia anche a tempo (solo per le prove dal web) */

/* tutto quello che non serve per svegliarsi: spento e tenuto spento durante il deep sleep */
static void spegni_periferiche(void)
{
    const struct { int pin, livello; } off[] = {
        {L02_PIN_C6_EN, 0},      /* wifi C6 in reset */
        {L02_PIN_SD_PWR, 1},     /* SD senza alimentazione */
        {L02_PIN_ETH_RST, 0},    /* PHY Ethernet in reset */
        {L02_PIN_PA, 0},         /* amplificatore audio spento */
    };
    for (size_t i = 0; i < sizeof(off) / sizeof(off[0]); i++) {
        gpio_set_direction(off[i].pin, GPIO_MODE_OUTPUT);
        gpio_set_level(off[i].pin, off[i].livello);
        gpio_hold_en(off[i].pin);
    }
}

/* Sonno SENZA risvegli (batteria): nessuna sorgente (ne' IMU ne' timer ne' WAKE), riparte solo con reset/riaccensione.
 * WAKE tenuto basso: la B (che dorme, o dormira' entro 3 s da WAKE basso) non viene svegliata da un pin che galleggia. */
static void dormi_per_sempre(bool a)
{
    if (a) {
        w(0x6B, 0x40);                               /* IMU in sleep: niente consumo, niente interrupt */
        gpio_set_direction(L02_PIN_WAKE, GPIO_MODE_OUTPUT);
        gpio_set_level(L02_PIN_WAKE, 0);
        gpio_hold_en(L02_PIN_WAKE);
    }
    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    esp_deep_sleep_start();
}

void logger02_dormi_def(const char *motivo)
{
    ESP_LOGW(TAG, "deep sleep DEFINITIVO: %s", motivo);
    bool a = logger02_ruolo()->is_a;
    if (a) logger02_link_invia("Z");                 /* prima la B */
    logger02_rec_stop();
    if (s_csv) { fclose(s_csv); s_csv = NULL; }
    logger02_salute_chiudi();                        /* scrive il motivo nel registro errori prima di chiudere */
    logger02_rec_standby();
    if (a) vTaskDelay(pdMS_TO_TICKS(500));           /* la Z arriva alla B prima che WAKE scenda */
    spegni_periferiche();
    dormi_per_sempre(a);
}

/* spegnimento per batteria sotto soglia: motivo nel registro errori (ESP_LOGE -> errori_*.log, chiuso da salute_chiudi)
 * e nella NVS (salute: batt_stop_*, riletto e loggato al riavvio) PRIMA di dormire. */
void logger02_spegni_batteria(const char *motivo, float media_v)
{
    ESP_LOGE(TAG, "SPEGNIMENTO BATTERIA: %s", motivo);
    logger02_salute_batt_stop(1, media_v);
    logger02_dormi_def(motivo);
}

/* Controllo all'avvio (solo A, dopo example_video_init, prima di wifi/registrazione): media delle prime letture < 3,1 V =
 * non avvio niente e torno a dormire senza risvegli. Batteria non leggibile = avvio normale + avviso. */
void logger02_batt_avvio(void)
{
    if (!logger02_ruolo()->is_a) return;
    batt_adc_init();
    float v[6];
    for (int i = 0; i < 6; i++) {
        v[i] = leggi_batteria();
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    float media;
    bool ok = l02_batt_avvio_ok(v, 6, &media);
    if (media < 0) {
        ESP_LOGW(TAG, "batteria non leggibile all'avvio: protezione 3 V NON attiva, avvio normale");
        return;
    }
    if (ok) {
        ESP_LOGI(TAG, "batteria all'avvio %.2f V (soglia %.1f V)", media, L02_BATT_START_V);
        return;
    }
    ESP_LOGE(TAG, "batteria %.2f V sotto %.1f V all'avvio: non avvio, torno a dormire senza risvegli", media, L02_BATT_START_V);
    logger02_salute_batt_stop(2, media);
    gpio_set_direction(L02_PIN_WAKE, GPIO_MODE_OUTPUT);        /* B: WAKE basso >3 s la fa dormire (wake_task) */
    gpio_set_level(L02_PIN_WAKE, 0);
    vTaskDelay(pdMS_TO_TICKS(4000));
    spegni_periferiche();
    dormi_per_sempre(true);
}

void logger02_dormi(const char *motivo)
{
    ESP_LOGW(TAG, "deep sleep: %s", motivo);
    bool a = logger02_ruolo()->is_a;
    if (a) logger02_link_invia("Z");                 /* prima la B */
    logger02_rec_stop();
    if (s_csv) { fclose(s_csv); s_csv = NULL; }
    logger02_salute_chiudi();

    logger02_rec_standby();                          /* camera in standby */
    /* tutto quello che non serve per svegliarsi: spento e tenuto spento durante il deep sleep */
    spegni_periferiche();

    if (a) {
        if (!arma_imu()) {
            ESP_LOGW(TAG, "la bici si muove allo spegnimento: resto acceso");
            esp_restart();
        }
        gpio_set_level(L02_PIN_WAKE, 0);
        rtc_gpio_pulldown_en(L02_PIN_IMU_INT);
        esp_sleep_enable_ext1_wakeup_io(1ULL << L02_PIN_IMU_INT, ESP_EXT1_WAKEUP_ANY_HIGH);
        if (g_dormi_prova_s) esp_sleep_enable_timer_wakeup((uint64_t)g_dormi_prova_s * 1000000ULL);
    } else {
        rtc_gpio_pulldown_en(L02_PIN_WAKE);
        esp_sleep_enable_ext1_wakeup_io(1ULL << L02_PIN_WAKE, ESP_EXT1_WAKEUP_ANY_HIGH);
        for (int i = 0; i < 200 && gpio_get_level(L02_PIN_WAKE); i++) {
            vTaskDelay(pdMS_TO_TICKS(50));           /* aspetta che la A abbassi WAKE (max 10 s) */
        }
    }
    esp_deep_sleep_start();
}
