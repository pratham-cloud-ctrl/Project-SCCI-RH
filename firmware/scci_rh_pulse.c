#include "scci_rh_pulse.h"
#include <string.h>

scci_rh_config scci_rh_default_config(void) {
    const scci_rh_config c = {100, 200, 50, 20000, 100000};
    return c;
}

static bool valid_config(scci_rh_config c) {
    return c.current_ua > 0 && c.current_ua <= 250 &&
        c.phase_us >= 50 && c.phase_us <= 250 &&
        c.gap_us >= 20 && c.gap_us <= 1000 &&
        c.period_us >= 20000 && c.period_us <= 2000000 &&
        c.sensor_timeout_us >= 1000 && c.sensor_timeout_us <= 1000000 &&
        (uint32_t)c.current_ua*c.phase_us <= 62500 &&
        c.period_us > (uint32_t)2*c.phase_us+c.gap_us;
}

bool scci_rh_init(scci_rh_controller *c, scci_rh_config config) {
    memset(c, 0, sizeof(*c));
    c->config = config;
    c->state = SCCI_RH_IDLE;
    c->configured = valid_config(config);
    c->fault = c->configured ? SCCI_RH_OK : SCCI_RH_BAD_CONFIG;
    return c->configured;
}

void scci_rh_sensor_update(scci_rh_controller *c, uint32_t now_us, bool valid) {
    c->sensor_valid = valid;
    if (valid) c->sensor_time_us = now_us;
    else if (c->fault == SCCI_RH_OK) c->fault = SCCI_RH_SENSOR_INVALID;
}

void scci_rh_poll(scci_rh_controller *c, uint32_t now_us) {
    if (c->fault != SCCI_RH_OK) return;
    if (!c->sensor_valid) c->fault = SCCI_RH_SENSOR_INVALID;
    else if ((uint32_t)(now_us-c->sensor_time_us) > c->config.sensor_timeout_us)
        c->fault = SCCI_RH_SENSOR_STALE;
    /* Do not truncate an already scheduled balancing phase on a software fault.
       Independent hardware emergency inhibition is outside this abstraction. */
}

bool scci_rh_start_pulse(scci_rh_controller *c, uint32_t now_us) {
    scci_rh_poll(c, now_us);
    if (!c->configured || c->fault != SCCI_RH_OK || c->state != SCCI_RH_IDLE) return false;
    if (c->has_started && (uint32_t)(now_us-c->last_start_us) < c->config.period_us) return false;
    c->last_start_us = now_us;
    c->has_started = true;
    c->state = SCCI_RH_POSITIVE;
    c->output.current_ua = (int16_t)c->config.current_ua;
    c->output.duration_us = c->config.phase_us;
    return true;
}

void scci_rh_timer_event(scci_rh_controller *c) {
    /* The backend must call once at each hardware-timer boundary. */
    switch (c->state) {
    case SCCI_RH_POSITIVE:
        c->state = SCCI_RH_GAP;
        c->output.current_ua = 0;
        c->output.duration_us = c->config.gap_us;
        break;
    case SCCI_RH_GAP:
        c->state = SCCI_RH_NEGATIVE;
        c->output.current_ua = -(int16_t)c->config.current_ua;
        c->output.duration_us = c->config.phase_us;
        break;
    case SCCI_RH_NEGATIVE:
        c->state = SCCI_RH_RECOVERY;
        c->output.current_ua = 0;
        c->output.duration_us = c->config.period_us-(uint32_t)2*c->config.phase_us-c->config.gap_us;
        break;
    case SCCI_RH_RECOVERY:
    default:
        c->state = SCCI_RH_IDLE;
        c->output.current_ua = 0;
        c->output.duration_us = 0;
        break;
    }
}

bool scci_rh_rearm(scci_rh_controller *c, uint32_t now_us) {
    if (!c->configured || !c->sensor_valid || c->state != SCCI_RH_IDLE ||
        (uint32_t)(now_us-c->sensor_time_us) > c->config.sensor_timeout_us) return false;
    c->fault = SCCI_RH_OK;
    return true;
}
