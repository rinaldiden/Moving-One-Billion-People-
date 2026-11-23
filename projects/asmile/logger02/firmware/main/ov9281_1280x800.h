/* OV9281 1280×800 RAW8, MIPI 2 lane, ingresso 24 MHz, 16,67 fps (VTS ×3; era 50) — risoluzione piena del sensore, come asmile #001 (rpicam).
 *
 * Perché qui e non in managed_components: il component manager riscrive quella cartella a ogni aggiornamento.
 * Il formato si passa al driver con VIDIOC_S_SENSOR_FMT (esp_video lo accetta come "formato personalizzato").
 *
 * Base: tabella Espressif MIPI_2lane_24Minput_RAW8_1280x720_50fps (esp_cam_sensor 2.7,
 * sensors/ov9281/private_include/ov9281_mipi_2lane_24Minput_1280x720_raw8_50fps.h), che è già la tabella 1280×800
 * con la finestra verticale tagliata al centro (lo dicono i suoi commenti ";00" ";2f" ";03" ";20").
 * Cambiano SOLO 4 registri, valori dal driver Linux mainline drivers/media/i2c/ov9282.c, mode_1280x800_regs
 * (torvalds/linux b6a9fa34, 23/11/2026):
 *   0x3803 0x28→0x00  inizio finestra Y (riga 0)
 *   0x3807 0x07→0x2f  fine finestra Y 0x032f (riga 815)
 *   0x380a/0x380b 0x02d0→0x0320  altezza uscita 800
 * Il resto (0x3810-0x3813 offset 8/8, 0x3814/15 niente binning, 0x3820/21, 0x4008/09/0c/0d, 0x4507/09) è già uguale.
 * Tempi INVARIATI: HTS 0x0369, VTS 0x071c = 1820 righe ≥ 800 + 110 (vblank_min del modo 1280x800 in ov9282.c)
 * → stesso fotogramma di 20 ms = 50 fps, stesso tempo riga 10,99 µs, stessa MIPI 400 MHz (800 Mbps/lane):
 * una riga da 1280 B passa sui 2 lane in 6,4 µs < 10,99 µs.
 * Le immagini 1280×800 contengono le 720 righe di prima (righe 40..759) più 40 righe sopra e 40 sotto:
 * stesse lenti e stessa focale in pixel, cy cresce di 40. */
#pragma once

#include <stdint.h>
#include "sdkconfig.h"
#include "esp_cam_sensor_types.h"

typedef struct {        /* stesso tracciato di ov9281_reginfo_t (sensors/ov9281/include/ov9281_types.h) */
    uint16_t reg;
    uint8_t val;
} l02_ov9281_reg_t;

#define L02_OV9281_GAIN_DEF 0x18           /* OV9281_GAIN_DEFAULT */
#if CONFIG_SOC_ISP_BLC_SUPPORTED           /* OV9281_BLC_TARGET_DEFAULT */
#define L02_OV9281_BLC_DEF  0x40
#else
#define L02_OV9281_BLC_DEF  0x10
#endif

static const l02_ov9281_reg_t l02_ov9281_1280x800_regs[] = {
    {0x0103, 0x01},
    {0x0106, 0x00},
    {0x0302, 0x32},
    {0x030d, 0x50},
    {0x030e, 0x02},
    {0x3001, 0x00},
    {0x3004, 0x00},
    {0x3005, 0x00},
    {0x3006, 0x04},
    {0x3011, 0x0a},
    {0x3013, 0x18},
    {0x301c, 0xf0},
    {0x3022, 0x01},
    {0x3030, 0x10},
    {0x3039, 0x32},
    {0x303a, 0x00},
    {0x3500, 0x00}, /* default exp */
    {0x3501, 0x2a},
    {0x3502, 0x90},
    {0x3503, 0x08},
    {0x3505, 0x8c},
    {0x3507, 0x03}, /* gain shift, left shift 3 bit */
    {0x3508, 0x00},
    {0x3509, L02_OV9281_GAIN_DEF}, /* default gain */
    {0x3610, 0x80},
    {0x3611, 0xa0},
    {0x3620, 0x6e},
    {0x3632, 0x56},
    {0x3633, 0x78},
    {0x3662, 0x07}, /* ;05 */
    {0x3666, 0x00},
    {0x366f, 0x5a},
    {0x3680, 0x84},
    {0x3707, 0x56},
    {0x370d, 0x00},
    {0x370e, 0xfa},
    {0x3712, 0x80},
    {0x372d, 0x22},
    {0x3731, 0x80},
    {0x3732, 0x30},
    {0x3778, 0x00},
    {0x377d, 0x22},
    {0x3788, 0x02},
    {0x3789, 0xa4},
    {0x378a, 0x00},
    {0x378b, 0x4a},
    {0x3799, 0x20},
    {0x379c, 0x01},
    {0x3800, 0x00},
    {0x3801, 0x00},
    {0x3802, 0x00},
    {0x3803, 0x00}, /* era 0x28 (crop centrato del 720). Linux ov9282.c mode_1280x800_regs: 0x00 = riga 0 dell'array */
    {0x3804, 0x05},
    {0x3805, 0x0f},
    {0x3806, 0x03},
    {0x3807, 0x2f}, /* era 0x07. Linux mode_1280x800_regs: fine finestra Y = 0x032f = riga 815 (array pieno 816 righe) */
    {0x3808, 0x05},
    {0x3809, 0x00},
    {0x380a, 0x03}, /* era 0x02. Linux mode_1280x800_regs: altezza uscita 0x0320 = 800 */
    {0x380b, 0x20}, /* era 0xd0. Linux mode_1280x800_regs: altezza uscita 0x0320 = 800 */
    {0x380c, 0x03}, /* 0x05b0: 30fps, 0x0369: 50fps */
    {0x380d, 0x69},
    {0x380e, 0x15}, /* VTS 0x1554 = 5460 righe = 3 × 1820: 16,67 fps (23/11: a 50 fps piena altezza la P4 perdeva il wifi) */
    {0x380f, 0x54},
    {0x3810, 0x00},
    {0x3811, 0x08},
    {0x3812, 0x00},
    {0x3813, 0x08},
    {0x3814, 0x11},
    {0x3815, 0x11},
    {0x3820, 0x40},
    {0x3821, 0x00},
    {0x382b, 0x3a},
    {0x382c, 0x06},
    {0x382d, 0xc2},
    {0x389d, 0x00},
    {0x3881, 0x42},
    {0x3882, 0x02},
    {0x3883, 0x12},
    {0x3885, 0x07},
    {0x38a8, 0x02},
    {0x38a9, 0x80},
    {0x38b1, 0x03},
    {0x38b3, 0x07},
    {0x38c4, 0x00},
    {0x38c5, 0xc0},
    {0x38c6, 0x04},
    {0x38c7, 0x80},
    {0x3920, 0xff},
    {0x4003, L02_OV9281_BLC_DEF},/* BLC */
    {0x4008, 0x04},
    {0x4009, 0x0b},
    {0x400c, 0x01},
    {0x400d, 0x07},
    {0x4010, 0xf0},
    {0x4011, 0x3b},
    {0x4042, 0x01},
    {0x4043, 0x40},
    {0x4307, 0x30},
    {0x4317, 0x00},
    {0x4501, 0x00},
    {0x4507, 0x00},
    {0x4509, 0x00},
    {0x450a, 0x08},
    {0x4601, 0x30}, /* ;04 */
    {0x470f, 0x00},
    {0x4f07, 0x00},
    {0x4800, 0x60},
    {0x4837, 0x14},
    {0x5000, 0x9f},
    {0x5001, 0x00},
    {0x5e00, 0x00},
    {0x5d00, 0x07},
    {0x5d01, 0x00},
    {0x4f00, 0x0c},
    {0x4f10, 0x00},
    {0x4f11, 0x88},
    {0x4f12, 0x0f},
    {0x4f13, 0xc4},
    {0x0100, 0x01},
    {0xffff, 0x00},};

static const esp_cam_sensor_isp_info_t l02_ov9281_1280x800_isp = {
    .isp_v1_info = {                       /* uguale al 720 Espressif: tempi invariati */
        .version = SENSOR_ISP_INFO_VERSION_DEFAULT,
        .pclk = 158886158,
        .vts = 1820,
        .hts = 1746,
        .tline_ns = 10989,
        .gain_def = 8,
        .exp_def = 0x2a9,
        .bayer_type = ESP_CAM_SENSOR_BAYER_BGGR,
    }
};

static const esp_cam_sensor_format_t l02_ov9281_1280x800 = {
    .name = "MIPI_2lane_24Minput_RAW8_1280x800_50fps",
    .format = ESP_CAM_SENSOR_PIXFORMAT_RAW8,
    .port = ESP_CAM_SENSOR_MIPI_CSI,
    .xclk = 24000000,
    .width = 1280,
    .height = 800,
    .regs = l02_ov9281_1280x800_regs,
    .regs_size = sizeof(l02_ov9281_1280x800_regs) / sizeof(l02_ov9281_1280x800_regs[0]),
    .fps = 50,
    .isp_info = &l02_ov9281_1280x800_isp,
    .mipi_info = {
        .mipi_clk = 400000000,
        .lane_num = 2,
        .line_sync_en = false,
    },
    .reserved = NULL,
};
