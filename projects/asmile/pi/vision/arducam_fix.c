/*
 * arducam_fix.c — LD_PRELOAD shim for libcamera 0.7 + Arducam Camarray HAT
 *
 * Compile: gcc -shared -fPIC -O2 -o arducam_fix.so arducam_fix.c -ldl
 * Usage:   LD_PRELOAD=./arducam_fix.so rpicam-vid ...
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <linux/media.h>
#include <stdio.h>
#include <unistd.h>

typedef int (*real_ioctl_t)(int, unsigned long, ...);

int ioctl(int fd, unsigned long request, ...)
{
    va_list ap;
    va_start(ap, request);
    void *arg = va_arg(ap, void *);
    va_end(ap);

    real_ioctl_t real_ioctl = (real_ioctl_t)dlsym(RTLD_NEXT, "ioctl");
    int ret = real_ioctl(fd, request, arg);

    if (request == MEDIA_IOC_G_TOPOLOGY && ret == 0 && arg != NULL) {
        struct media_v2_topology *topo = (struct media_v2_topology *)arg;
        if (topo->num_entities > 0 && topo->ptr_entities != 0) {
            struct media_v2_entity *ents =
                (struct media_v2_entity *)(uintptr_t)topo->ptr_entities;
            for (uint32_t i = 0; i < topo->num_entities; i++) {
                if (strncmp(ents[i].name, "arducam-pivariety", 17) == 0) {
                    char suffix[64];
                    strncpy(suffix, ents[i].name + 17, sizeof(suffix) - 1);
                    suffix[sizeof(suffix) - 1] = '\0';
                    snprintf(ents[i].name, sizeof(ents[i].name),
                             "ov9281%s", suffix);
                }
            }
        }
    }

    return ret;
}
