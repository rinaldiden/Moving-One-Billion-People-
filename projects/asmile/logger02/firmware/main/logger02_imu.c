/* A: MPU6050 a 50 Hz (CSV con lo stesso orologio dei fotogrammi), batteria, autospegnimento e deep sleep.
 * Porta di logger_autospegni.py + imu_wake.py del logger001:
 *   fermo = gyro < 3 °/s e variazione accel < 30 mg; dopo FERMO_MIN minuti fermo (e almeno MIN_ACCESO_MIN acceso)
 *   → chiude i file, addormenta la B, arma il motion interrupt dell'IMU (soglia di Daniele 17/11: al minimo)
 *   e va in deep sleep. Si sveglia quando l'INT (GPIO4) si alza. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_sleep.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "logger02.h"

static const char *TAG = "imu";

#define MPU         0x68
#define FERMO_MIN   5
#define MIN_ACCESO_MIN 3
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

static esp_err_t w(uint8_t reg, uint8_t v)
{
    uint8_t b[2] = {reg, v};
    return i2c_master_transmit(s_mpu, b, 2, 50);
}

static esp_err_t r(uint8_t reg, uint8_t *out, size_t n)
{
    return i2c_master_transmit_receive(s_mpu, &reg, 1, out, n, 50);
}

static void apri_csv(void)
{
    char sess[24], p[96];
    logger02_nome_sessione(sess, sizeof(sess));
    snprintf(p, sizeof(p), L02_REC_DIR "/sensors_%s.csv", sess);
    s_csv = fopen(p, "w");
    if (s_csv) {
        setvbuf(s_csv, NULL, _IOFBF, 16 * 1024);
        fprintf(s_csv, "t_us,frame,imu_ax_g,imu_ay_g,imu_az_g,imu_gx_dps,imu_gy_dps,imu_gz_dps,batt_v\n");
        ESP_LOGI(TAG, "scrivo %s", p);
    }
}

static float leggi_batteria(void)
{
    int raw, mv;
    if (!s_adc || adc_oneshot_read(s_adc, ADC_CHANNEL_4, &raw) != ESP_OK) return -1;
    if (s_cali && adc_cali_raw_to_voltage(s_cali, raw, &mv) == ESP_OK) {
        float v = mv / 1000.0f * (100.0f + 33.0f) / 33.0f;
        return v < 2.0f ? -1 : v;                  /* sotto 2 V = partitore non collegato */
    }
    return -1;
}

static void imu_task(void *arg)
{
    uint8_t d[14];
    float pax = 0, pay = 0, paz = 0;
    TickType_t t0 = xTaskGetTickCount();
    int64_t flush = esp_timer_get_time();
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
        if (g > GYRO_FERMO || dacc > ACC_FERMO_G) s_ultimo_moto = t;
        pax = s_ax; pay = s_ay; paz = s_az;
        if (s_campioni % 50 == 0) s_batt = leggi_batteria();
        if (s_csv) {
            fprintf(s_csv, "%lld,%lu,%.4f,%.4f,%.4f,%.2f,%.2f,%.2f,", (long long)t, (unsigned long)logger02_rec_frame(),
                    s_ax, s_ay, s_az, s_gx, s_gy, s_gz);
            if (s_campioni % 50 == 0 && s_batt > 0) fprintf(s_csv, "%.2f", s_batt);
            fputc('\n', s_csv);
            if (t - flush > 2000000) { fflush(s_csv); flush = t; }
        }
        if (t > MIN_ACCESO_MIN * 60000000LL && t - s_ultimo_moto > FERMO_MIN * 60000000LL) {
            logger02_dormi("bici ferma da 5 minuti");
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

    adc_oneshot_unit_init_cfg_t uc = {.unit_id = ADC_UNIT_1};
    if (adc_oneshot_new_unit(&uc, &s_adc) == ESP_OK) {
        adc_oneshot_chan_cfg_t cc = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
        adc_oneshot_config_channel(s_adc, ADC_CHANNEL_4, &cc);      /* GPIO20 = ADC1_CH4 */
        adc_cali_curve_fitting_config_t cf = {.unit_id = ADC_UNIT_1, .chan = ADC_CHANNEL_4, .atten = ADC_ATTEN_DB_12,
                                              .bitwidth = ADC_BITWIDTH_DEFAULT};
        adc_cali_create_scheme_curve_fitting(&cf, &s_cali);
    }

    s_ultimo_moto = esp_timer_get_time();
    apri_csv();
    xTaskCreatePinnedToCore(imu_task, "imu", 4096, NULL, 9, NULL, 0);
    ESP_LOGI(TAG, "MPU6050 ok, 50 Hz; spegnimento dopo %d min fermo", FERMO_MIN);
    return ESP_OK;
}

float logger02_batteria_v(void)
{
    return s_batt;
}

void logger02_imu_stato(char *json, size_t n)
{
    int64_t fermo = (esp_timer_get_time() - s_ultimo_moto) / 1000000;
    snprintf(json, n, "{\"campioni\":%lu,\"errori\":%lu,\"acc_g\":[%.3f,%.3f,%.3f],\"gyro_dps\":[%.2f,%.2f,%.2f],"
             "\"fermo_s\":%lld,\"spegne_dopo_s\":%d,\"batteria_v\":%.2f}",
             (unsigned long)s_campioni, (unsigned long)s_errori, s_ax, s_ay, s_az, s_gx, s_gy, s_gz,
             (long long)fermo, FERMO_MIN * 60, s_batt);
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

void logger02_dormi(const char *motivo)
{
    ESP_LOGW(TAG, "deep sleep: %s", motivo);
    bool a = logger02_ruolo()->is_a;
    if (a) logger02_link_invia("Z");                 /* prima la B */
    logger02_rec_stop();
    if (s_csv) { fclose(s_csv); s_csv = NULL; }

    gpio_set_direction(L02_PIN_C6_EN, GPIO_MODE_OUTPUT);
    gpio_set_level(L02_PIN_C6_EN, 0);                /* spegne la C6 (wifi) */
    gpio_hold_en(L02_PIN_C6_EN);

    if (a) {
        if (!arma_imu()) {
            ESP_LOGW(TAG, "la bici si muove allo spegnimento: resto acceso");
            esp_restart();
        }
        gpio_set_level(L02_PIN_WAKE, 0);
        rtc_gpio_pulldown_en(L02_PIN_IMU_INT);
        esp_sleep_enable_ext1_wakeup_io(1ULL << L02_PIN_IMU_INT, ESP_EXT1_WAKEUP_ANY_HIGH);
    } else {
        rtc_gpio_pulldown_en(L02_PIN_WAKE);
        esp_sleep_enable_ext1_wakeup_io(1ULL << L02_PIN_WAKE, ESP_EXT1_WAKEUP_ANY_HIGH);
        for (int i = 0; i < 200 && gpio_get_level(L02_PIN_WAKE); i++) {
            vTaskDelay(pdMS_TO_TICKS(50));           /* aspetta che la A abbassi WAKE (max 10 s) */
        }
    }
    esp_deep_sleep_start();
}
