/* Host-only Stage 6 replay adapter. The production runtime is compiled unchanged.
 * This file neither emulates SPIM/GPIO nor reads biological signals. */
#include "scci_rh_runtime.h"
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
static scci_rh_runtime runtime;

EXPORT uint64_t scci_rh_replay_call(unsigned op, uint64_t now, uint64_t a,
                                uint64_t b, uint64_t c, uint64_t d) {
    scci_rh_event_plan p = {0};
    switch (op) {
    case 0: scci_rh_runtime_init(&runtime,now); return 1;
    case 1: scci_rh_runtime_health(&runtime,(uint16_t)a,(uint8_t)b,
                               (uint8_t)c,(uint8_t)d,now); return 1;
    case 2: return scci_rh_runtime_configure(&runtime,(uint32_t)a,b!=0,now);
    case 3: return scci_rh_runtime_raw_identity(&runtime,(uint32_t)d,
                 (uint32_t)b,0,(uint8_t)c,a,true,true,now);
    case 4: return scci_rh_runtime_session(&runtime,7,1,-500,500,now);
    case 5: return scci_rh_runtime_command(&runtime,(scci_rh_mode)a,1,(uint32_t)b,
                                       (uint32_t)c,now);
    case 6: return scci_rh_runtime_rearm(&runtime,now);
    case 7: return scci_rh_runtime_take_actions(&runtime);
    case 8: return scci_rh_runtime_route_prepare(&runtime,(uint8_t)a,(uint8_t)b,now);
    case 9: return scci_rh_runtime_route_readback(&runtime,(uint8_t)a,(uint8_t)b,now);
    case 10:
        p.epoch=1; p.event_id=(uint32_t)(d>>8);
        p.current_ua[0]=(uint16_t)a; p.current_ua[1]=(uint16_t)b;
        p.contact[0]=(uint8_t)(c&255); p.contact[1]=(uint8_t)(c>>8);
        p.source_mask=(uint8_t)(d&3); p.off_trial=(uint8_t)((d>>2)&1);
        p.phase_us=200; p.gap_us=200;
        return scci_rh_runtime_event(&runtime,&p,now);
    case 11: return scci_rh_runtime_phase_ready(&runtime,now);
    case 12: return scci_rh_runtime_phase_start(&runtime,now);
    case 13: scci_rh_runtime_phase_end(&runtime,now); return 1;
    case 14: scci_rh_runtime_tick(&runtime,now); return 1;
    case 15: scci_rh_runtime_trip(&runtime,(scci_rh_runtime_fault)a,(uint16_t)b,now); return 1;
    case 16: return scci_rh_runtime_recovery_begin(&runtime,now);
    default: return UINT64_MAX;
    }
}
EXPORT uint64_t scci_rh_replay_get(unsigned key) {
    switch(key) {
    case 0: return runtime.output.armed;
    case 1: return runtime.output.request_mask;
    case 2: return runtime.output.plus_mask;
    case 3: return runtime.sticky_fault;
    case 4: return runtime.state;
    case 5: return runtime.output.current_ua[0];
    case 6: return runtime.output.current_ua[1];
    case 7: return runtime.route_valid;
    case 8: return runtime.pressure_valid;
    case 9: return runtime.now_us;
    case 10: return runtime.output.want_mask;
    default: return UINT64_MAX;
    }
}
EXPORT uint64_t scci_rh_replay_packet(const unsigned char *p, unsigned n, uint64_t now) {
    return scci_rh_runtime_sbp(&runtime,p,n,now);
}
