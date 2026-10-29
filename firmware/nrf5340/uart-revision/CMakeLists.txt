cmake_minimum_required(VERSION 3.20.0)
# Reuse the exact reviewed pin/peripheral configuration and unchanged policy.
set(CONF_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../app/prj.conf")
set(DTC_OVERLAY_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../app/app.overlay")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(scci_rh_nrf5340_uart_revision)

target_sources(app PRIVATE ../app/src/main.c src/scci_rh_backend.c ../core/scci_rh_runtime.c)
target_include_directories(app PRIVATE ../core ../app/src)
target_compile_options(app PRIVATE -Wall -Wextra -Werror -Wno-unused-parameter)
