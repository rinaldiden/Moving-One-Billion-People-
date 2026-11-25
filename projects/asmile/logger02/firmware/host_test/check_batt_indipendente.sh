#!/bin/sh
# Test strutturale (VETO 2, 24/11): il controllo batteria 3 V non deve stare dentro imu_task (che su errore I2C fa `continue`)
# ma in un task 1 Hz proprio. Uso: sh check_batt_indipendente.sh   (da host_test/)
f=../main/logger02_imu.c
imu=$(awk '/^static void imu_task/,/^esp_err_t logger02_imu_start/' $f)
bat=$(awk '/^static void batt_task/,/^void logger02_batt_start/' $f)
ok=1
echo "$imu" | grep -q 'l02_batt_campione\|logger02_spegni_batteria' && { echo "KO  imu_task contiene il controllo batteria"; ok=0; }
echo "$bat" | grep -q 'l02_batt_campione' && echo "$bat" | grep -q 'vTaskDelayUntil' && echo "$bat" | grep -q 'leggi_batteria()' || { echo "KO  batt_task incompleto"; ok=0; }
echo "$bat" | grep -q 's_campioni\|r(0x3B' && { echo "KO  batt_task dipende dall'IMU"; ok=0; }
grep -q 'logger02_batt_start' ../main/logger02_main.c || { echo "KO  batt_task non avviato in app_main"; ok=0; }
grep -q 'xSemaphoreTake(logger02_analogico' $f || { echo "KO  manca il mutex ADC"; ok=0; }
[ $ok = 1 ] && echo "ok   controllo batteria indipendente da imu_task, stesso mutex ADC" && exit 0
exit 1
