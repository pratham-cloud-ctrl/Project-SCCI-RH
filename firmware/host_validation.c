#include "scci_rh_pulse.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>

static void finish(scci_rh_controller *c) {
    unsigned guard = 0;
    while (c->state != SCCI_RH_IDLE) {
        assert(++guard <= 4);
        scci_rh_timer_event(c);
    }
}

int main(void) {
    scci_rh_controller c;
    scci_rh_config cfg = scci_rh_default_config();
    unsigned assertions = 0;
    assert(scci_rh_init(&c,cfg)); ++assertions;
    assert(!scci_rh_start_pulse(&c,0)); ++assertions;
    scci_rh_sensor_update(&c,0,true);
    assert(scci_rh_rearm(&c,0)); ++assertions;
    assert(scci_rh_start_pulse(&c,0)); ++assertions;
    int64_t charge = 0;
    uint32_t elapsed = 0;
    puts("start_us,current_ua,duration_us,state");
    while (c.state != SCCI_RH_IDLE) {
        printf("%" PRIu32 ",%d,%" PRIu32 ",%d\n",elapsed,c.output.current_ua,c.output.duration_us,c.state);
        charge += (int64_t)c.output.current_ua*c.output.duration_us;
        elapsed += c.output.duration_us;
        scci_rh_timer_event(&c);
    }
    assert(charge == 0); ++assertions;
    assert(elapsed == cfg.period_us); ++assertions;
    assert(c.output.current_ua == 0); ++assertions;
    assert(!scci_rh_start_pulse(&c,1)); ++assertions;
    scci_rh_sensor_update(&c,20000,true);
    assert(scci_rh_start_pulse(&c,20000)); ++assertions;
    scci_rh_sensor_update(&c,20100,false);
    assert(c.fault == SCCI_RH_SENSOR_INVALID); ++assertions;
    charge = (int64_t)c.output.current_ua*c.output.duration_us;
    scci_rh_timer_event(&c);
    charge += (int64_t)c.output.current_ua*c.output.duration_us;
    scci_rh_timer_event(&c);
    assert(c.output.current_ua == -100); ++assertions;
    charge += (int64_t)c.output.current_ua*c.output.duration_us;
    finish(&c);
    assert(charge == 0); ++assertions;
    assert(!scci_rh_start_pulse(&c,40000)); ++assertions;
    scci_rh_sensor_update(&c,40000,true);
    assert(scci_rh_rearm(&c,40000)); ++assertions;
    assert(!scci_rh_start_pulse(&c,140001)); ++assertions;
    assert(c.fault == SCCI_RH_SENSOR_STALE); ++assertions;
    cfg.current_ua = 251;
    assert(!scci_rh_init(&c,cfg)); ++assertions;
    assert(!scci_rh_start_pulse(&c,0)); ++assertions;
    cfg = scci_rh_default_config(); cfg.period_us = 10000;
    assert(!scci_rh_init(&c,cfg)); ++assertions;
    cfg = scci_rh_default_config(); cfg.phase_us = 0;
    assert(!scci_rh_init(&c,cfg)); ++assertions;
    cfg = scci_rh_default_config();
    assert(scci_rh_init(&c,cfg)); ++assertions;
    scci_rh_sensor_update(&c,UINT32_MAX-500,true);
    assert(scci_rh_start_pulse(&c,300)); ++assertions;
    assert(!scci_rh_start_pulse(&c,301)); ++assertions;
    finish(&c);
    fprintf(stderr,"C host validation: %u assertions passed; pulse charge = 0 nC\n",assertions);
    return 0;
}
