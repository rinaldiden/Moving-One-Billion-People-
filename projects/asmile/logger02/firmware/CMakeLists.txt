cmake_minimum_required(VERSION 3.16)
# MicroLink (client Tailscale, MIT) e la sua dipendenza wireguard_lwip
set(EXTRA_COMPONENT_DIRS "components/microlink/components")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(logger02)
