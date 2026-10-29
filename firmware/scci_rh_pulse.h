#ifndef SCCI_RH_PULSE_H
#define SCCI_RH_PULSE_H
#include <stdbool.h>
#include <stdint.h>
#if defined(_WIN32) && defined(SCCI_RH_SHARED)
#define SCCI_RH_API __declspec(dllexport)
#else
#define SCCI_RH_API
#endif

/* Digital reference, not a deployed MCU driver or medical device. */
typedef enum { SCCI_RH_IDLE, SCCI_RH_POSITIVE, SCCI_RH_GAP, SCCI_RH_NEGATIVE, SCCI_RH_RECOVERY } scci_rh_state;
typedef enum { SCCI_RH_OK, SCCI_RH_BAD_CONFIG, SCCI_RH_SENSOR_INVALID, SCCI_RH_SENSOR_STALE } scci_rh_fault;
typedef struct {
    uint16_t current_ua, phase_us, gap_us;
    uint32_t period_us, sensor_timeout_us;
} scci_rh_config;
typedef struct {
    int16_t current_ua;
    uint32_t duration_us;
} scci_rh_segment;
typedef struct {
    scci_rh_config config;
    scci_rh_state state;
    scci_rh_fault fault;
    uint32_t sensor_time_us;
    bool sensor_valid;
    bool configured;
    scci_rh_segment output;
    uint32_t last_start_us;
    bool has_started;
} scci_rh_controller;

SCCI_RH_API scci_rh_config scci_rh_default_config(void);
SCCI_RH_API bool scci_rh_init(scci_rh_controller *controller, scci_rh_config config);
SCCI_RH_API void scci_rh_sensor_update(scci_rh_controller *controller, uint32_t now_us, bool valid);
SCCI_RH_API void scci_rh_poll(scci_rh_controller *controller, uint32_t now_us);
SCCI_RH_API bool scci_rh_start_pulse(scci_rh_controller *controller, uint32_t now_us);
SCCI_RH_API void scci_rh_timer_event(scci_rh_controller *controller);
SCCI_RH_API bool scci_rh_rearm(scci_rh_controller *controller, uint32_t now_us);
#endif
