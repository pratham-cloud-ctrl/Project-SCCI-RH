#ifndef SCCI_RH_BACKEND_H
#define SCCI_RH_BACKEND_H
#include "scci_rh_runtime.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint64_t aperture_lo_us, aperture_hi_us;
    uint32_t epoch, capture_id;
    uint16_t code;
    uint8_t channel, valid;
} scci_rh_raw_record;
typedef struct {
    uint64_t frame_lo_us;
    uint32_t aperture_offset_lo_us[16], aperture_offset_hi_us[16];
    int16_t samples[16];
    uint32_t epoch, sequence;
    uint16_t valid_mask, supply_code;
} scci_rh_rhd_record;
typedef struct {
    uint64_t aperture_lo_us, aperture_hi_us;
    uint32_t epoch, event_id, reset_epoch;
    uint16_t code[2];
    uint8_t phase, source_mask, valid, reserved;
} scci_rh_endpoint_record;
typedef struct {
    uint32_t raw_received, rhd_frames, endpoint_pairs, uart_rejects;
    uint32_t missed_raw_slots, missed_rhd_frames, telemetry_dropped;
    uint32_t latest_sideband, configuration_epoch, integrator_epoch;
    uint16_t envelope[16];
    uint8_t commissioned, observing;
} scci_rh_backend_status;

bool scci_rh_backend_init(scci_rh_runtime *runtime);
uint64_t scci_rh_backend_now_us(void);
void scci_rh_backend_service(scci_rh_runtime *runtime);
void scci_rh_backend_stop(void);
const scci_rh_backend_status *scci_rh_backend_status_get(void);
#endif
