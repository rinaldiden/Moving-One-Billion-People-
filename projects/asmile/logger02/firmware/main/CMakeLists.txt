idf_component_register(SRCS "logger02_main.c" "logger02_ruolo.c" "logger02_rete.c" "logger02_saluto.c"
                            "logger02_sd_ora.c" "logger02_link.c" "logger02_rec.c" "logger02_imu.c" "logger02_web.c" "logger02_tailscale.c" "logger02_salute.c"
                       PRIV_INCLUDE_DIRS .
                       EMBED_FILES "saluto.pcm")
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-format-truncation)
