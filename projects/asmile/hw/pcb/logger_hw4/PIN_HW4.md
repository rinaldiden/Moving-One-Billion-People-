# Tabella pin HW4 ↔ firmware hw3-def (generata da kicad/controlla_pin_fw.py, non a mano)

Conflitto = il firmware usa il GPIO e HW4 lo collega a una funzione diversa da HW3. Fonte firmware: `logger02/firmware` (main/*.c|h, sdkconfig).

| GPIO | net A | net B | usi nel firmware (file:riga) | esito |
|---|---|---|---|---|
| 0 | — | — | sdkconfig:2964 `CONFIG_ESP_HOSTED_SDIO_RESET_SLAVE_GPIO_MIN=0` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 1 | EXP_IO1 | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 2 | TRIG_M | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 3 | SYNC_M | — | main/logger02.h:15 `[solo A] #define L02_PIN_SYNC_A      3       /* A out (pin 19) → B GPIO21 (pin 11): impuls`<br>main/logger02_link.c:186 `[solo A]         gpio_set_level(L02_PIN_SYNC_A, 1);`<br>main/logger02_link.c:197 `[solo A]         gpio_set_level(L02_PIN_SYNC_A, 0);` | ok: stessa funzione di HW3 |
| 4 | IMU_INT | — | main/logger02.h:13 `[solo A] #define L02_PIN_IMU_INT     4       /* A: INT MPU6050, LP GPIO → risveglio dal de`<br>main/logger02_imu.c:195 `[solo A]     return !(s & 0x40) && !gpio_get_level(L02_PIN_IMU_INT);`<br>main/logger02_imu.c:228 `[solo A]         rtc_gpio_pulldown_en(L02_PIN_IMU_INT);` | ok: stessa funzione di HW3 |
| 5 | WAKE_M | WAKE_B | main/logger02.h:14 `#define L02_PIN_WAKE        5       /* A out → B in (LP GPIO su B) */`<br>main/logger02_imu.c:227 `gpio_set_level(L02_PIN_WAKE, 0);`<br>main/logger02_imu.c:232 `rtc_gpio_pulldown_en(L02_PIN_WAKE);` | ok: stessa funzione di HW3 |
| 6 | B_PWR_EN | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 7 | I2C_SDA_A | I2C_SDA_B | sdkconfig:825 `CONFIG_EXAMPLE_MIPI_CSI_SCCB_SDA_PIN=7`<br>sdkconfig:3273 `CONFIG_EXAMPLE_MIPI_CSI_SCCB_I2C_SDA_PIN=7` | ok: stessa funzione di HW3 |
| 8 | I2C_SCL_A | I2C_SCL_B | sdkconfig:824 `CONFIG_EXAMPLE_MIPI_CSI_SCCB_SCL_PIN=8`<br>sdkconfig:3272 `CONFIG_EXAMPLE_MIPI_CSI_SCCB_I2C_SCL_PIN=8` | ok: stessa funzione di HW3 |
| 9 | — | — | main/logger02_saluto.c:36 `.gpio_cfg = {.mclk = 13, .bclk = 12, .ws = 10, .dout = 9, .din = I2S_GPIO_UNUSED},` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 10 | — | — | main/logger02_saluto.c:36 `.gpio_cfg = {.mclk = 13, .bclk = 12, .ws = 10, .dout = 9, .din = I2S_GPIO_UNUSED},` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 11 | CAM_EN_A | CAM_EN_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 12 | — | — | main/logger02_saluto.c:36 `.gpio_cfg = {.mclk = 13, .bclk = 12, .ws = 10, .dout = 9, .din = I2S_GPIO_UNUSED},` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 13 | — | — | main/logger02_saluto.c:36 `.gpio_cfg = {.mclk = 13, .bclk = 12, .ws = 10, .dout = 9, .din = I2S_GPIO_UNUSED},` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 14 | — | — | sdkconfig:2968 `CONFIG_ESP_HOSTED_PRIV_SDIO_PIN_D0_SLOT_1=14`<br>sdkconfig:2975 `CONFIG_ESP_HOSTED_SDIO_PIN_D0=14`<br>sdkconfig:3428 `CONFIG_ESP_SDIO_PIN_D0=14` | interno al modulo (C6) |
| 15 | — | — | sdkconfig:2969 `CONFIG_ESP_HOSTED_PRIV_SDIO_PIN_D1_4BIT_BUS_SLOT_1=15`<br>sdkconfig:2976 `CONFIG_ESP_HOSTED_SDIO_PRIV_PIN_D1_4BIT_BUS=15`<br>sdkconfig:2979 `CONFIG_ESP_HOSTED_SDIO_PIN_D1=15` | interno al modulo (C6) |
| 16 | — | — | sdkconfig:2970 `CONFIG_ESP_HOSTED_PRIV_SDIO_PIN_D2_4BIT_BUS_SLOT_1=16`<br>sdkconfig:2977 `CONFIG_ESP_HOSTED_SDIO_PIN_D2=16`<br>sdkconfig:3429 `CONFIG_ESP_SDIO_PIN_D2=16` | interno al modulo (C6) |
| 17 | — | — | sdkconfig:2971 `CONFIG_ESP_HOSTED_PRIV_SDIO_PIN_D3_4BIT_BUS_SLOT_1=17`<br>sdkconfig:2978 `CONFIG_ESP_HOSTED_SDIO_PIN_D3=17`<br>sdkconfig:3430 `CONFIG_ESP_SDIO_PIN_D3=17` | interno al modulo (C6) |
| 18 | — | — | sdkconfig:2967 `CONFIG_ESP_HOSTED_PRIV_SDIO_PIN_CLK_SLOT_1=18`<br>sdkconfig:2974 `CONFIG_ESP_HOSTED_SDIO_PIN_CLK=18`<br>sdkconfig:3427 `CONFIG_ESP_SDIO_PIN_CLK=18` | interno al modulo (C6) |
| 19 | — | — | sdkconfig:2966 `CONFIG_ESP_HOSTED_PRIV_SDIO_PIN_CMD_SLOT_1=19`<br>sdkconfig:2973 `CONFIG_ESP_HOSTED_SDIO_PIN_CMD=19`<br>sdkconfig:3426 `CONFIG_ESP_SDIO_PIN_CMD=19` | interno al modulo (C6) |
| 20 | BATT_ADC | — | main/logger02.h:19 `[solo A] #define L02_PIN_BATT_ADC    20      /* A: partitore 100k/33k */`<br>main/logger02_imu.c:77 `[solo A]     gpio_pulldown_en(L02_PIN_BATT_ADC);`<br>main/logger02_imu.c:81 `[solo A]     gpio_pulldown_dis(L02_PIN_BATT_ADC);` | ok: stessa funzione di HW3 |
| 21 | VBUS_SENSE | SYNC_B | main/logger02.h:16 `[solo B] #define L02_PIN_SYNC_B      21`<br>main/logger02_link.c:220 `[solo B]         gpio_config_t i = {.pin_bit_mask = 1ULL << L02_PIN_SYNC_B, .mode = GPIO_M`<br>main/logger02_link.c:224 `[solo B]         gpio_isr_handler_add(L02_PIN_SYNC_B, sync_isr, NULL);` | ok: il firmware lo usa solo sul modulo B (stessa funzione o pad libero); sull'altro è VBUS_SENSE |
| 22 | UART_AB | UART_BA_B | main/logger02.h:17 `#define L02_PIN_UART_TX     22`<br>main/logger02_link.c:207 `ESP_ERROR_CHECK(uart_set_pin(UARTN, L02_PIN_UART_TX, L02_PIN_UART_RX, UART_PIN_NO_CHANGE, ` | ok: stessa funzione di HW3 |
| 23 | UART_BA | UART_AB_B | main/logger02.h:18 `#define L02_PIN_UART_RX     23`<br>main/logger02_link.c:207 `ESP_ERROR_CHECK(uart_set_pin(UARTN, L02_PIN_UART_TX, L02_PIN_UART_RX, UART_PIN_NO_CHANGE, ` | ok: stessa funzione di HW3 |
| 24 | USB_DM_A | USB_DM_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 25 | USB_DP_A | USB_DP_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 26 | CHRG_N | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 27 | BUZZER | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 28 | SPI_SCLK_A | SPI_SCLK_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 29 | SPI_MOSI_A | SPI_MOSI_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 30 | SPI_MISO_A | SPI_MISO_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 31 | SPI_CS_A | SPI_CS_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 32 | SPI_HS_A | SPI_HS_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 33 | B_EN_CTL | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 35 | BOOT_A | BOOT_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 37 | U0TXD_A | U0TXD_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 38 | U0RXD_A | U0RXD_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 39 | SD_D0_A | SD_D0_B | main/logger02_sd_ora.c:39 `slot.d0 = 39;`<br>sdkconfig:855 `CONFIG_EXAMPLE_SDMMC_D0_PIN=39` | ok: stessa funzione di HW3 |
| 40 | SD_D1_A | SD_D1_B | main/logger02_sd_ora.c:40 `slot.d1 = 40;` | ok: stessa funzione di HW3 |
| 41 | SD_D2_A | SD_D2_B | main/logger02_sd_ora.c:41 `slot.d2 = 41;` | ok: stessa funzione di HW3 |
| 42 | SD_D3_A | SD_D3_B | main/logger02_sd_ora.c:42 `slot.d3 = 42;` | ok: stessa funzione di HW3 |
| 43 | SD_CLK_M_A | SD_CLK_M_B | main/logger02_sd_ora.c:37 `slot.clk = 43;`<br>sdkconfig:854 `CONFIG_EXAMPLE_SDMMC_CLK_PIN=43` | ok: stessa funzione di HW3 |
| 44 | SD_CMD_A | SD_CMD_B | main/logger02_sd_ora.c:38 `slot.cmd = 44;`<br>sdkconfig:853 `CONFIG_EXAMPLE_SDMMC_CMD_PIN=44` | ok: stessa funzione di HW3 |
| 45 | SD_PWR_N_A | SD_PWR_N_B | main/logger02.h:21 `#define L02_PIN_SD_PWR      45`<br>main/logger02_imu.c:212 `{L02_PIN_SD_PWR, 1},     /* SD senza alimentazione */`<br>main/logger02_main.c:90 `const int sblocca[] = {L02_PIN_C6_EN, L02_PIN_SD_PWR, L02_PIN_PA, L02_PIN_WAKE, L02_PIN_ET` | ok: stessa funzione di HW3 |
| 47 | EXP_IO47 | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 48 | EXP_IO48 | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 49 | B_BOOT_CTL | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 50 | LED_R | LED_B | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 51 | — | — | main/logger02.h:22 `#define L02_PIN_ETH_RST     51      /* PHY Ethernet (non usato): tenuto in reset = consuma`<br>main/logger02_imu.c:213 `{L02_PIN_ETH_RST, 0},    /* PHY Ethernet in reset */`<br>main/logger02_main.c:90 `const int sblocca[] = {L02_PIN_C6_EN, L02_PIN_SD_PWR, L02_PIN_PA, L02_PIN_WAKE, L02_PIN_ET` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 52 | LED_G | — | — | ok: il firmware hw3-def non lo usa (funzione nuova HW4) |
| 53 | — | — | main/logger02.h:23 `#define L02_PIN_PA          53      /* amplificatore audio */`<br>main/logger02_imu.c:214 `{L02_PIN_PA, 0},         /* amplificatore audio spento */`<br>main/logger02_main.c:90 `const int sblocca[] = {L02_PIN_C6_EN, L02_PIN_SD_PWR, L02_PIN_PA, L02_PIN_WAKE, L02_PIN_ET` | ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni) |
| 54 | — | — | main/logger02.h:20 `#define L02_PIN_C6_EN       54      /* reset della C6 (wifi): basso prima del deep sleep *`<br>main/logger02_imu.c:211 `{L02_PIN_C6_EN, 0},      /* wifi C6 in reset */`<br>main/logger02_main.c:90 `const int sblocca[] = {L02_PIN_C6_EN, L02_PIN_SD_PWR, L02_PIN_PA, L02_PIN_WAKE, L02_PIN_ET` | interno al modulo (C6) |

**Conflitti: 0**
