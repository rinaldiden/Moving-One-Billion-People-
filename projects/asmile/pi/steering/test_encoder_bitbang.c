/*
 * SSI encoder bit-bang reader using libgpiod v2 on RPi5.
 * Fallback if SPI doesn't work through RS-485 modules.
 *
 * Compile: gcc -O2 -o test_encoder_bitbang test_encoder_bitbang.c -lgpiod
 * Run:     sudo ./test_encoder_bitbang
 *
 * Wiring (via level shifter + RS-485):
 *   CLK_GPIO (default 21) → Level Shifter → RS-485 #1 DI → Encoder CLK
 *   DATA_GPIO (default 19) ← Level Shifter ← RS-485 #2 RO ← Encoder DATA
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <gpiod.h>

#define GPIOCHIP    "/dev/gpiochip4"
#define CLK_GPIO    21
#define DATA_GPIO   19
#define SSI_BITS    12
#define HALF_CLK_NS 500  /* 500ns = ~1MHz clock */

static volatile int running = 1;

static void sighandler(int sig) {
    (void)sig;
    running = 0;
}

static inline void busy_wait_ns(unsigned int ns) {
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (;;) {
        clock_gettime(CLOCK_MONOTONIC, &now);
        unsigned long elapsed = (now.tv_sec - start.tv_sec) * 1000000000UL +
                                (now.tv_nsec - start.tv_nsec);
        if (elapsed >= ns) break;
    }
}

int main(void) {
    signal(SIGINT, sighandler);
    signal(SIGTERM, sighandler);

    struct gpiod_chip *chip = gpiod_chip_open(GPIOCHIP);
    if (!chip) {
        perror("gpiod_chip_open");
        return 1;
    }

    /* Request CLK line as output, default HIGH (SSI idle) */
    struct gpiod_line_settings *clk_settings = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(clk_settings, GPIOD_LINE_DIRECTION_OUTPUT);
    gpiod_line_settings_set_output_value(clk_settings, GPIOD_LINE_VALUE_ACTIVE);

    struct gpiod_line_config *clk_cfg = gpiod_line_config_new();
    unsigned int clk_offset = CLK_GPIO;
    gpiod_line_config_add_line_settings(clk_cfg, &clk_offset, 1, clk_settings);

    struct gpiod_request_config *clk_req_cfg = gpiod_request_config_new();
    gpiod_request_config_set_consumer(clk_req_cfg, "ssi-clk");

    struct gpiod_line_request *clk_req = gpiod_chip_request_lines(chip, clk_req_cfg, clk_cfg);
    gpiod_request_config_free(clk_req_cfg);
    gpiod_line_config_free(clk_cfg);
    gpiod_line_settings_free(clk_settings);

    if (!clk_req) {
        perror("request CLK line");
        gpiod_chip_close(chip);
        return 1;
    }

    /* Request DATA line as input */
    struct gpiod_line_settings *data_settings = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(data_settings, GPIOD_LINE_DIRECTION_INPUT);

    struct gpiod_line_config *data_cfg = gpiod_line_config_new();
    unsigned int data_offset = DATA_GPIO;
    gpiod_line_config_add_line_settings(data_cfg, &data_offset, 1, data_settings);

    struct gpiod_request_config *data_req_cfg = gpiod_request_config_new();
    gpiod_request_config_set_consumer(data_req_cfg, "ssi-data");

    struct gpiod_line_request *data_req = gpiod_chip_request_lines(chip, data_req_cfg, data_cfg);
    gpiod_request_config_free(data_req_cfg);
    gpiod_line_config_free(data_cfg);
    gpiod_line_settings_free(data_settings);

    if (!data_req) {
        perror("request DATA line");
        gpiod_line_request_release(clk_req);
        gpiod_chip_close(chip);
        return 1;
    }

    printf("SSI bit-bang reader (C, libgpiod v2) on %s\n", GPIOCHIP);
    printf("CLK=GPIO%d  DATA=GPIO%d  bits=%d\n", CLK_GPIO, DATA_GPIO, SSI_BITS);
    printf("Reading... Ctrl+C to stop\n\n");

    int last_pos = -1;

    while (running) {
        unsigned int value = 0;

        /* Ensure clock HIGH for monoflop timeout (>20us) */
        gpiod_line_request_set_value(clk_req, CLK_GPIO, GPIOD_LINE_VALUE_ACTIVE);
        busy_wait_ns(25000);

        /* Clock out SSI_BITS bits */
        for (int i = 0; i < SSI_BITS; i++) {
            /* Falling edge */
            gpiod_line_request_set_value(clk_req, CLK_GPIO, GPIOD_LINE_VALUE_INACTIVE);
            busy_wait_ns(HALF_CLK_NS);

            /* Read data */
            enum gpiod_line_value bit = gpiod_line_request_get_value(data_req, DATA_GPIO);

            /* Rising edge */
            gpiod_line_request_set_value(clk_req, CLK_GPIO, GPIOD_LINE_VALUE_ACTIVE);
            busy_wait_ns(HALF_CLK_NS);

            value = (value << 1) | (bit == GPIOD_LINE_VALUE_ACTIVE ? 1 : 0);
        }

        /* Keep clock HIGH */
        gpiod_line_request_set_value(clk_req, CLK_GPIO, GPIOD_LINE_VALUE_ACTIVE);

        int pos = value & 0x0FFF;
        if (pos != last_pos) {
            printf("Position: %4d  (0x%03X)  bin: ", pos, pos);
            for (int i = SSI_BITS - 1; i >= 0; i--)
                putchar((pos >> i) & 1 ? '1' : '0');
            putchar('\n');
            fflush(stdout);
            last_pos = pos;
        }

        usleep(50000);
    }

    printf("\nDone.\n");
    gpiod_line_request_release(clk_req);
    gpiod_line_request_release(data_req);
    gpiod_chip_close(chip);
    return 0;
}
