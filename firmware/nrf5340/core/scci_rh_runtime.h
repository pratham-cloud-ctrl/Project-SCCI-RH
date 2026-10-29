#ifndef SCCI_RH_RUNTIME_H
#define SCCI_RH_RUNTIME_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Shared production policy core. Time is monotonic local microseconds. The
 * target owns GPIO/SPIM/DPPI edges; this core never claims measured timing. */
#define SCCI_RH_SBP_PACKET_BYTES 56u
#define SCCI_RH_FAULT_LOG_CAPACITY 16u
#define SCCI_RH_PHASE_MAX_US 200u
#define SCCI_RH_GAP_MIN_US 200u
#define SCCI_RH_EVENT_MIN_US 2778u
#define SCCI_RH_RAW_QUEUE_CAPACITY 16384u
#define SCCI_RH_NORMAL_QUEUE_CAPACITY 8192u
#define SCCI_RH_REQUIRED_HEALTH 0x007fu
#define SCCI_RH_HEALTH_RESET 0x0001u
#define SCCI_RH_HEALTH_RAILS 0x0002u
#define SCCI_RH_HEALTH_WATCHDOG 0x0004u
#define SCCI_RH_HEALTH_AFE_BLANK 0x0008u
#define SCCI_RH_HEALTH_MONITORS 0x0010u
#define SCCI_RH_HEALTH_POWER 0x0020u
#define SCCI_RH_HEALTH_RAW_CONFIG 0x0040u
#define SCCI_RH_ACTION_ROUTE_COMMIT 0x0001u
#define SCCI_RH_ACTION_ROUTE_ACK 0x0002u
#define SCCI_RH_ACTION_ROUTE_REARM 0x0004u
#define SCCI_RH_ACTION_PHASE_REARM 0x0008u
#define SCCI_RH_ACTION_FAULT_RESET 0x0010u
#define SCCI_RH_ACTION_SUP_REARM 0x0020u
#define SCCI_RH_ACTION_MON_REARM 0x0040u

typedef enum {
    SCCI_RH_MODE_OBSERVE=0, SCCI_RH_MODE_MOTOR=1, SCCI_RH_MODE_PRESSURE=2,
    SCCI_RH_MODE_DIAGNOSTIC=3
} scci_rh_mode;
typedef enum {
    SCCI_RH_STATE_IDLE=0, SCCI_RH_STATE_PREPARE_FIRST=1, SCCI_RH_STATE_FIRST=2,
    SCCI_RH_STATE_GAP=3, SCCI_RH_STATE_PREPARE_SECOND=4, SCCI_RH_STATE_SECOND=5,
    SCCI_RH_STATE_RECOVERY=6
} scci_rh_runtime_state;
typedef enum {
    SCCI_RH_FAULT_NONE=0, SCCI_RH_FAULT_BOOT=1, SCCI_RH_FAULT_CONFIG=2,
    SCCI_RH_FAULT_HEALTH=3, SCCI_RH_FAULT_PACKET=4, SCCI_RH_FAULT_STALE=5,
    SCCI_RH_FAULT_LEASE=6, SCCI_RH_FAULT_ROUTE=7, SCCI_RH_FAULT_PHASE=8,
    SCCI_RH_FAULT_SAMPLE=9, SCCI_RH_FAULT_OVERRUN=10, SCCI_RH_FAULT_HARD_TRIP=11,
    SCCI_RH_FAULT_CLOCK=12
} scci_rh_runtime_fault;
typedef struct {
    uint64_t at_us;
    uint32_t event_id;
    uint16_t reason;
    uint16_t detail;
} scci_rh_fault_record;
typedef struct {
    uint32_t epoch;
    uint32_t event_id;
    uint16_t current_ua[2];
    uint16_t phase_us;
    uint16_t gap_us;
    uint8_t contact[2];
    uint8_t source_mask;
    uint8_t off_trial;
} scci_rh_event_plan;
typedef struct {
    uint32_t generation;
    uint16_t current_ua[2];
    uint8_t contact[2];
    uint8_t request_mask;
    uint8_t plus_mask;
    uint8_t want_mask;
    uint8_t armed;
    uint8_t diagnostic_capture;
    uint8_t reserved;
} scci_rh_runtime_output;
typedef struct {
    uint64_t now_us;
    uint64_t deadline_us;
    uint64_t lease_deadline_us;
    uint64_t last_event_us;
    uint64_t pressure_oldest_us;
    uint64_t pressure_newest_peer_us;
    uint64_t last_raw_aperture_us;
    int64_t clock_offset_lo_us;
    int64_t clock_offset_hi_us;
    uint32_t config_epoch;
    uint32_t session_epoch;
    uint32_t calibration_id;
    uint32_t pressure_sequence;
    uint32_t command_sequence;
    uint32_t last_capture_id;
    uint32_t raw_queue_used;
    uint32_t normal_queue_used;
    uint32_t fault_total;
    uint16_t health;
    uint16_t pending_actions;
    uint16_t sticky_fault;
    uint8_t quiet_mask;
    uint8_t timer_active_mask;
    uint8_t run_mask;
    uint8_t route_valid;
    uint8_t route_pending;
    uint8_t route_contact[2];
    uint8_t pressure_valid;
    uint8_t pressure_seen;
    uint8_t command_seen;
    uint8_t session_valid;
    uint8_t config_valid;
    uint8_t sample_seen;
    uint8_t event_seen;
    uint8_t phase_ready;
    uint8_t fault_head;
    uint8_t fault_count;
    uint8_t mode;
    uint8_t state;
    scci_rh_event_plan plan;
    scci_rh_runtime_output output;
    scci_rh_fault_record faults[SCCI_RH_FAULT_LOG_CAPACITY];
} scci_rh_runtime;

void scci_rh_runtime_init(scci_rh_runtime *r, uint64_t now_us);
bool scci_rh_runtime_configure(scci_rh_runtime *r, uint32_t epoch, bool readback_ok,
                           uint64_t now_us);
void scci_rh_runtime_health(scci_rh_runtime *r, uint16_t health, uint8_t quiet_mask,
                        uint8_t timer_active_mask, uint8_t run_mask,
                        uint64_t now_us);
bool scci_rh_runtime_session(scci_rh_runtime *r, uint32_t epoch, uint32_t calibration_id,
                         int64_t offset_lo_us, int64_t offset_hi_us,
                         uint64_t now_us);
bool scci_rh_runtime_sbp(scci_rh_runtime *r, const uint8_t *packet, size_t length,
                     uint64_t now_us);
bool scci_rh_runtime_command(scci_rh_runtime *r, scci_rh_mode mode, uint32_t epoch,
                         uint32_t sequence, uint32_t lease_us,
                         uint64_t now_us);
/* Explicit inhibited recovery first qualifies pre-MON health and requests only
 * monitor-latch rearm. The backend waits observed permits before final rearm. */
bool scci_rh_runtime_recovery_begin(scci_rh_runtime *r, uint64_t now_us);
bool scci_rh_runtime_rearm(scci_rh_runtime *r, uint64_t now_us);
bool scci_rh_runtime_route_prepare(scci_rh_runtime *r, uint8_t contact0,
                               uint8_t contact1, uint64_t now_us);
bool scci_rh_runtime_route_readback(scci_rh_runtime *r, uint8_t active0,
                                uint8_t active1, uint64_t now_us);
bool scci_rh_runtime_event(scci_rh_runtime *r, const scci_rh_event_plan *plan,
                       uint64_t now_us);
bool scci_rh_runtime_phase_ready(scci_rh_runtime *r, uint64_t now_us);
bool scci_rh_runtime_phase_start(scci_rh_runtime *r, uint64_t now_us);
void scci_rh_runtime_phase_end(scci_rh_runtime *r, uint64_t now_us);
void scci_rh_runtime_tick(scci_rh_runtime *r, uint64_t now_us);
void scci_rh_runtime_trip(scci_rh_runtime *r, scci_rh_runtime_fault reason, uint16_t detail,
                      uint64_t now_us);
bool scci_rh_runtime_raw_identity(scci_rh_runtime *r, uint32_t epoch,
                              uint32_t capture_id, uint8_t expected_channel,
                              uint8_t claimed_channel, uint64_t aperture_us,
                              bool transaction_known, bool in_range,
                              uint64_t now_us);
bool scci_rh_runtime_queue_push(scci_rh_runtime *r, bool raw, uint32_t bytes,
                            uint64_t now_us);
void scci_rh_runtime_queue_drain(scci_rh_runtime *r, bool raw, uint32_t bytes);
uint16_t scci_rh_runtime_take_actions(scci_rh_runtime *r);
uint32_t scci_rh_runtime_crc32(const uint8_t *bytes, size_t length);
/* A 32-bit tick delta >= half range is ambiguous and rejected. Calls must be
 * closer than 2^31 input ticks; conversion to microseconds belongs to target. */
bool scci_rh_runtime_extend_ticks(uint32_t previous, uint32_t current,
                               uint64_t accumulated, uint64_t *extended);
#endif
