#include "scci_rh_backend.h"
#include "scci_rh_pins.h"
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/drivers/clock_control.h>
#include <zephyr/drivers/clock_control/nrf_clock_control.h>
#include <zephyr/irq.h>
#include <zephyr/sys/atomic.h>
#include <nrfx_spim.h>
#include <hal/nrf_gpio.h>
#include <hal/nrf_timer.h>
#include <hal/nrf_gpiote.h>
#include <hal/nrf_dppi.h>
#include <helpers/nrfx_gppi.h>
#include <string.h>

/* Production backend of the deliberately slower commissioning profile.
 * No high-rate ArrayList operation, radio, authenticated peer, biological
 * decoder, physical timing qualification or implanted use is asserted. */
static nrfx_spim_t rhd_spi = NRFX_SPIM_INSTANCE(NRF_SPIM1);
static nrfx_spim_t mon_spi = NRFX_SPIM_INSTANCE(NRF_SPIM2);
static nrfx_spim_t ctrl_spi = NRFX_SPIM_INSTANCE(NRF_SPIM3);
static nrfx_spim_t raw_spi = NRFX_SPIM_INSTANCE(NRF_SPIM4);
static volatile bool spi_complete;
static const struct device *const companion = DEVICE_DT_GET(DT_NODELABEL(uart0));
static scci_rh_backend_status status;
/* Retained records and byte queues are real linked storage, not allocations
 * copied from the earlier full-system budget. Records distinguish controller
 * aperture brackets from delayed transport completion. */
/* Volatile retention is intentional: these are inspectable debugger/fault
 * archives, including interrupted histories, not dead stores to optimize out. */
static volatile scci_rh_raw_record raw_archive[SCCI_RH_RAW_RECORDS];
static volatile scci_rh_rhd_record rhd_archive[SCCI_RH_RHD_RECORDS];
static volatile scci_rh_endpoint_record endpoint_archive[SCCI_RH_ENDPOINT_RECORDS];
static uint32_t raw_head, rhd_head, endpoint_head, capture_id;
static uint8_t normal_queue[SCCI_RH_NORMAL_QUEUE_CAPACITY];
static uint8_t raw_queue[SCCI_RH_RAW_QUEUE_CAPACITY];
static volatile uint32_t normal_write, normal_read, raw_write, raw_read;
/* An interrupt/FIFO boundary is not a wire-frame boundary. Keep ownership
 * through the whole selected frame; only then may normal traffic preempt raw. */
static uint16_t tx_frame_remaining;
static bool tx_frame_raw;
static atomic_t normal_drained, raw_drained, uart_overflow;
static uint8_t rx_queue[2048];
static volatile uint32_t rx_write, rx_read;
static uint8_t command_frame[110];
static uint16_t command_count, command_need;
static uint32_t telemetry_seq, last_control_sequence;
static bool control_sequence_seen;
static uint8_t dma_tx[8] __aligned(4), dma_rx[8] __aligned(4);
static uint8_t raw_channel;
static uint32_t previous_clock;
static uint64_t extended_clock;
static bool clock_started, ctrl_active, timer_ready;
static volatile bool phase_cut_seen;
static volatile uint32_t phase_cut_capture;
static uint64_t phase_scheduled_deadline, next_raw, next_rhd, next_heartbeat;
static uint64_t observe_after, next_telemetry;
static uint8_t heartbeat, last_runtime_state;
static uint32_t envelope_q8[16];
static uint8_t recovery_stage;
static uint64_t recovery_after;
static uint64_t feature_first_us, feature_last_us;
static uint16_t feature_transport_mask;
static nrfx_gppi_handle_t phase_connection;
static void phase_cut_consume(scci_rh_runtime *runtime);

static void rhd_irq(const void *unused) { nrfx_spim_irq_handler(&rhd_spi); }
static void mon_irq(const void *unused) { nrfx_spim_irq_handler(&mon_spi); }
static void ctrl_irq(const void *unused) { nrfx_spim_irq_handler(&ctrl_spi); }
static void raw_irq(const void *unused) { nrfx_spim_irq_handler(&raw_spi); }
static void spi_done(const nrfx_spim_event_t *event, void *unused)
{
    if (event->type == NRFX_SPIM_EVENT_DONE) { spi_complete = true; }
}

static void pin_output(uint32_t pin, bool high)
{
    nrf_gpio_pin_write(pin, high);
    nrf_gpio_cfg_output(pin);
}
static void pulse(uint32_t pin)
{
    nrf_gpio_pin_set(pin);
    k_busy_wait(2);
    nrf_gpio_pin_clear(pin);
    k_busy_wait(2);
}
static void request_clear(void)
{
    /* Task-owned pins ignore ordinary GPIO OUT writes. */
    NRF_GPIOTE0_S->TASKS_CLR[0] = 1;
    NRF_GPIOTE0_S->TASKS_CLR[1] = 1;
    __DSB();
}
void scci_rh_backend_stop(void)
{
    if (timer_ready) {
        request_clear();
        NRF_TIMER0->INTENCLR = TIMER_INTENCLR_COMPARE2_Msk;
    } else {
        nrf_gpio_pin_clear(PIN_REQ0);
        nrf_gpio_pin_clear(PIN_REQ1);
    }
    nrf_gpio_pin_clear(PIN_WANT0);
    nrf_gpio_pin_clear(PIN_WANT1);
    nrf_gpio_pin_clear(PIN_PLUS0); nrf_gpio_pin_clear(PIN_MINUS0);
    nrf_gpio_pin_clear(PIN_PLUS1); nrf_gpio_pin_clear(PIN_MINUS1);
    nrf_gpio_pin_clear(PIN_AFE_CONNECT); nrf_gpio_pin_clear(PIN_AFE_RECORD);
    status.observing = false;
    /* INT_RUN intentionally stays unchanged on trip: interrupted charge
     * history is retained rather than silently reset to a fresh baseline. */
}
static void trip(scci_rh_runtime *runtime, scci_rh_runtime_fault reason, uint16_t detail)
{
    scci_rh_backend_stop();
    scci_rh_runtime_trip(runtime, reason, detail, scci_rh_backend_now_us());
}

uint64_t scci_rh_backend_now_us(void)
{
    if (!clock_started) { return 0; }
    NRF_TIMER0->TASKS_CAPTURE[0] = 1;
    uint32_t current = NRF_TIMER0->CC[0];
    uint64_t next;
    if (scci_rh_runtime_extend_ticks(previous_clock, current, extended_clock, &next)) {
        previous_clock = current;
        extended_clock = next;
    } else {
        scci_rh_backend_stop();
        /* A half-range observation gap is not assigned an invented epoch. */
        atomic_set(&uart_overflow, 2);
    }
    return extended_clock;
}

static void phase_irq(const void *unused)
{
    if (NRF_TIMER0->EVENTS_COMPARE[2]) {
        NRF_TIMER0->EVENTS_COMPARE[2] = 0;
        NRF_TIMER0->INTENCLR = TIMER_INTENCLR_COMPARE2_Msk;
        phase_cut_capture = NRF_TIMER0->CC[1];
        phase_cut_seen = true;
        __DSB();
    }
}
static bool timer_init(void)
{
    NRF_TIMER0->TASKS_STOP = 1;
    NRF_TIMER0->MODE = TIMER_MODE_MODE_Timer;
    NRF_TIMER0->BITMODE = TIMER_BITMODE_BITMODE_32Bit;
    NRF_TIMER0->PRESCALER = 4; /* 16 MHz / 16 = 1 MHz. */
    NRF_TIMER0->TASKS_CLEAR = 1;
    nrf_gpiote_task_configure(NRF_GPIOTE0_S, 0, PIN_REQ0,
                             NRF_GPIOTE_POLARITY_NONE, NRF_GPIOTE_INITIAL_VALUE_LOW);
    nrf_gpiote_task_configure(NRF_GPIOTE0_S, 1, PIN_REQ1,
                             NRF_GPIOTE_POLARITY_NONE, NRF_GPIOTE_INITIAL_VALUE_LOW);
    nrf_gpiote_task_enable(NRF_GPIOTE0_S, 0);
    nrf_gpiote_task_enable(NRF_GPIOTE0_S, 1);
    /* Allocate through the SAME official manager as the Zephyr UART driver.
     * Its enhanced polling-TX support already owns a DPPI connection at boot,
     * even with the interrupt-driven API; hardcoding channel0 would collide. */
    uint32_t event = nrf_timer_event_address_get(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE2);
    uint32_t capture = nrf_timer_task_address_get(NRF_TIMER0, NRF_TIMER_TASK_CAPTURE1);
    if (nrfx_gppi_conn_alloc(event, capture, &phase_connection)
        || nrfx_gppi_ep_attach((uint32_t)&NRF_GPIOTE0_S->TASKS_CLR[0], phase_connection)
        || nrfx_gppi_ep_attach((uint32_t)&NRF_GPIOTE0_S->TASKS_CLR[1], phase_connection)) {
        request_clear(); return false;
    }
    nrfx_gppi_conn_enable(phase_connection);
    IRQ_CONNECT(NRFX_IRQ_NUMBER_GET(NRF_TIMER0), 1, phase_irq, NULL, 0);
    irq_enable(NRFX_IRQ_NUMBER_GET(NRF_TIMER0));
    NRF_TIMER0->TASKS_START = 1;
    timer_ready = clock_started = true;
    previous_clock = 0; extended_clock = 0;
    request_clear();
    return true;
}

static bool spi_init_one(nrfx_spim_t *instance, uint32_t sck, uint32_t mosi,
                         uint32_t miso, uint32_t frequency, nrf_spim_mode_t mode)
{
    nrfx_spim_config_t config = NRFX_SPIM_DEFAULT_CONFIG(sck, mosi, miso,
                                                        NRF_SPIM_PIN_NOT_CONNECTED);
    config.frequency = frequency; config.mode = mode; config.irq_priority = 2;
    if (instance == &raw_spi) { config.rx_delay = 0; }
    return nrfx_spim_init(instance, &config, spi_done, NULL) == 0;
}
static bool ctrl_init(void)
{
    if (ctrl_active) { return true; }
    ctrl_active = spi_init_one(&ctrl_spi, PIN_CTRL_SCK, PIN_CTRL_MOSI,
                              NRF_SPIM_PIN_NOT_CONNECTED, 8000000, NRF_SPIM_MODE_1);
    return ctrl_active;
}
static bool spi_transfer(nrfx_spim_t *instance, uint32_t cs, bool cs_high,
                         uint16_t bytes, uint64_t *lo, uint64_t *hi)
{
    memset(dma_rx, 0, sizeof(dma_rx));
    spi_complete = false;
    if (lo) { *lo = scci_rh_backend_now_us(); }
    nrf_gpio_pin_write(cs, cs_high);
    if (hi) { *hi = scci_rh_backend_now_us(); }
    /* A 1 us allocation exceeds the converters' documented CS setup minima;
     * actual CS propagation and absolute aperture still require measurement. */
    k_busy_wait(1);
    nrfx_spim_xfer_desc_t descriptor = {
        .p_tx_buffer = dma_tx, .tx_length = bytes,
        .p_rx_buffer = dma_rx, .rx_length = bytes
    };
    bool okay = nrfx_spim_xfer(instance, &descriptor, 0) == 0;
    uint64_t limit = scci_rh_backend_now_us() + 50;
    while (okay && !spi_complete && scci_rh_backend_now_us() < limit) { }
    okay = okay && spi_complete && instance->p_reg->RXD.AMOUNT == bytes
                  && instance->p_reg->TXD.AMOUNT == bytes;
    if (!okay) { nrfx_spim_abort(instance); }
    k_busy_wait(1);
    nrf_gpio_pin_write(cs, !cs_high);
    k_busy_wait(1);
    return okay;
}

static bool raw_register(uint8_t address, uint8_t value, bool write)
{
    uint16_t command = ((uint16_t)address << 9) | (write ? 0x100 : 0) | value;
    dma_tx[0] = command >> 8; dma_tx[1] = command; dma_tx[2] = 0;
    if (!spi_transfer(&raw_spi, PIN_RAW_CS, false, 3, NULL, NULL)) { return false; }
    return dma_rx[2] == value;
}
static bool raw_command(uint16_t command, uint16_t bytes, uint64_t *lo, uint64_t *hi)
{
    memset(dma_tx, 0, sizeof(dma_tx));
    dma_tx[0] = command >> 8; dma_tx[1] = command;
    return spi_transfer(&raw_spi, PIN_RAW_CS, false, bytes, lo, hi);
}
static bool raw_configure(void)
{
    nrf_gpio_pin_clear(PIN_RAW_RESET); k_busy_wait(10);
    nrf_gpio_pin_set(PIN_RAW_RESET); k_busy_wait(20000);
    /* 20 ms is a software allocation beyond the typical 15 ms reference
     * startup, not a worst-case manufacturer turn-on guarantee. */
    for (uint8_t address = 5; address <= 12; ++address) {
        if (!raw_register(address, 6, true) || !raw_register(address, 6, false)) {
            return false;
        }
    }
    /* The lower target profile sends 40 clocks and observes the hardware
     * channel nibble. It deliberately differs from untagged 32-clock450k. */
    if (!raw_register(3, 1, true) || !raw_register(3, 1, false)) { return false; }
    if (!raw_command(0xc000, 5, NULL, NULL)) { return false; } /* Prime/discard. */
    if (!raw_register(0x3f, 0xc0, false)) { return false; }
    if (!raw_command(0xc000, 5, NULL, NULL)) { return false; }
    raw_channel = 0;
    return true;
}
static bool rhd_word(uint16_t command, uint16_t *result, uint64_t *lo, uint64_t *hi)
{
    dma_tx[0] = command >> 8; dma_tx[1] = command;
    if (!spi_transfer(&rhd_spi, PIN_AFE_CS, true, 2, lo, hi)) { return false; }
    if (result) { *result = ((uint16_t)dma_rx[0] << 8) | dma_rx[1]; }
    return true;
}
static bool rhd_register_read(uint8_t address, uint16_t *value)
{
    return rhd_word(0xc000 | ((uint16_t)address << 8), NULL, NULL, NULL)
        && rhd_word(0xff00, NULL, NULL, NULL)
        && rhd_word(0xff00, value, NULL, NULL);
}
static bool rhd_configure(void)
{
    /* RHD2216: signed output, DSP disabled, 300 Hz upper/20 Hz lower nominal
     * manufacturer register table. Intra-burst bias uses220ksps row8/32.
     * Physical noise, aliasing, recovery and neural utility remain unearned. */
    static const uint8_t registers[18] = {
        0xfe, 0x48, 32, 2, 0x40, 0, 128, 0, 6, 9, 2, 11, 54, 0, 255, 255, 0, 0
    };
    for (uint8_t i = 0; i < 18; ++i) {
        if (!rhd_word(0x8000 | ((uint16_t)i << 8) | registers[i], NULL, NULL, NULL)) {
            return false;
        }
    }
    k_busy_wait(200); /* Both Vref enable and complete register initialization. */
    if (!rhd_word(0x5500, NULL, NULL, NULL)) { return false; }
    for (uint8_t i = 0; i < 9; ++i) {
        if (!rhd_word(0xff00, NULL, NULL, NULL)) { return false; }
    }
    k_busy_wait(9000); /* Typical/recommended2.5/fH fast-settle allocation. */
    if (!rhd_word(0x80de, NULL, NULL, NULL)) { return false; }
    for (uint8_t i = 0; i < 18; ++i) {
        uint16_t value;
        if (!rhd_register_read(i, &value) || value != (i ? registers[i] : 0xde)) {
            return false;
        }
    }
    uint16_t chip, amplifiers;
    return rhd_register_read(63, &chip) && chip == 2
        && rhd_register_read(62, &amplifiers) && amplifiers == 16;
}
static bool dac_write(uint8_t address, uint16_t code)
{
    if (!ctrl_init()) { return false; }
    dma_tx[0] = address; dma_tx[1] = code >> 8; dma_tx[2] = code;
    /* DAC80502 is a write-only three-wire connection in the native package.
     * Successful clocks do not claim register readback or observed current. */
    return spi_transfer(&ctrl_spi, PIN_DAC_CS, false, 3, NULL, NULL);
}

static uint32_t sideband_snapshot(void)
{
    /* Disable SPIM3 before GPIO ownership of its shared clock changes. DAC
     * remains deselected. Its traffic may alter candidate595 data, never activeQ. */
    if (ctrl_active) { nrfx_spim_uninit(&ctrl_spi); ctrl_active = false; }
    pin_output(PIN_CTRL_SCK, false);
    nrf_gpio_pin_clear(PIN_SIDEBAND_LOAD); k_busy_wait(1);
    nrf_gpio_pin_set(PIN_SIDEBAND_LOAD); k_busy_wait(1);
    uint32_t bits = 0;
    for (uint8_t i = 0; i < 32; ++i) {
        bits |= (uint32_t)nrf_gpio_pin_read(PIN_SIDEBAND_DATA) << i;
        nrf_gpio_pin_set(PIN_CTRL_SCK); k_busy_wait(1);
        nrf_gpio_pin_clear(PIN_CTRL_SCK); k_busy_wait(1);
    }
    status.latest_sideband = bits;
    return bits;
}
static bool health_update(scci_rh_runtime *runtime)
{
    uint32_t bits = sideband_snapshot();
    bool sentinel = (bits & SIDEBAND_SENTINEL_MASK) == SIDEBAND_SENTINEL_VALUE;
    uint16_t health = 0;
    if (sentinel) {
        if (bits & (1u << 8)) { health |= SCCI_RH_HEALTH_RESET; }
        if (bits & (1u << 9)) { health |= SCCI_RH_HEALTH_RAILS; }
        if (bits & (1u << 10)) { health |= SCCI_RH_HEALTH_WATCHDOG; }
        if (bits & (1u << 11)) { health |= SCCI_RH_HEALTH_AFE_BLANK; }
        if ((bits & (3u << 14)) == (3u << 14)) { health |= SCCI_RH_HEALTH_MONITORS; }
        if ((bits & (1u << 16)) && nrf_gpio_pin_read(PIN_AFE_FAULT)) {
            health |= SCCI_RH_HEALTH_POWER;
        }
        if (status.commissioned) { health |= SCCI_RH_HEALTH_RAW_CONFIG; }
    }
    scci_rh_runtime_health(runtime, health, (bits >> 12) & 3,
                       (bits >> 21) & 3, (bits >> 19) & 3, scci_rh_backend_now_us());
    if (((bits & (3u << 24)) && runtime->output.request_mask) ||
        (runtime->output.armed && !(bits & (1u << 17)))) {
        trip(runtime, SCCI_RH_FAULT_HARD_TRIP, 0x401);
        return false;
    }
    return sentinel;
}

static void uart_callback(const struct device *device, void *unused)
{
    if (!uart_irq_update(device)) { return; }
    if (uart_err_check(device)) { atomic_set(&uart_overflow, 1); }
    while (uart_irq_rx_ready(device)) {
        uint8_t bytes[32];
        int count = uart_fifo_read(device, bytes, sizeof(bytes));
        if (count <= 0) { break; }
        for (int i = 0; i < count; ++i) {
            if (rx_write - rx_read >= sizeof(rx_queue)) {
                atomic_set(&uart_overflow, 1); break;
            }
            rx_queue[rx_write++ % sizeof(rx_queue)] = bytes[i];
        }
    }
    while (uart_irq_tx_ready(device)) {
        bool raw = tx_frame_remaining ? tx_frame_raw : normal_read == normal_write;
        uint32_t rd = raw ? raw_read : normal_read;
        uint32_t wr = raw ? raw_write : normal_write;
        uint32_t capacity = raw ? sizeof(raw_queue) : sizeof(normal_queue);
        uint8_t *queue = raw ? raw_queue : normal_queue;
        if (rd == wr) { uart_irq_tx_disable(device); break; }
        uint32_t available = wr - rd;
        if (!tx_frame_remaining) {
            /* packet_send publishes one complete envelope under irq_lock. */
            if (available < 14) {
                atomic_set(&uart_overflow, 1); uart_irq_tx_disable(device); break;
            }
            uint16_t payload = queue[(rd + 4) % capacity]
                | ((uint16_t)queue[(rd + 5) % capacity] << 8);
            if (payload > 96 || 14u + payload > available) {
                atomic_set(&uart_overflow, 1); uart_irq_tx_disable(device); break;
            }
            tx_frame_raw = raw;
            tx_frame_remaining = 14u + payload;
        }
        if (available > tx_frame_remaining) { available = tx_frame_remaining; }
        uint32_t contiguous = capacity - rd % capacity;
        if (available > contiguous) { available = contiguous; }
        int sent = uart_fifo_fill(device, queue + rd % capacity, available);
        if (sent <= 0) { break; }
        tx_frame_remaining -= sent;
        if (raw) { raw_read += sent; atomic_add(&raw_drained, sent); }
        else { normal_read += sent; atomic_add(&normal_drained, sent); }
    }
}
static void put16(uint8_t *out, uint16_t value) { out[0] = value; out[1] = value >> 8; }
static void put32(uint8_t *out, uint32_t value)
{ for (uint8_t i = 0; i < 4; ++i) { out[i] = value >> (8 * i); } }
static void put64(uint8_t *out, uint64_t value)
{ for (uint8_t i = 0; i < 8; ++i) { out[i] = value >> (8 * i); } }
static uint16_t get16(const uint8_t *in) { return (uint16_t)in[0] | ((uint16_t)in[1] << 8); }
static uint32_t get32(const uint8_t *in)
{ uint32_t value = 0; for (uint8_t i = 0; i < 4; ++i) { value |= (uint32_t)in[i] << (8 * i); } return value; }
static uint64_t get64(const uint8_t *in)
{ return get32(in) | ((uint64_t)get32(in + 4) << 32); }

static bool packet_send(scci_rh_runtime *runtime, uint8_t type, const uint8_t *payload,
                         uint16_t length, bool raw)
{
    uint8_t packet[110];
    if (length > 96) { return false; }
    packet[0] = 'A'; packet[1] = 'O'; packet[2] = 1; packet[3] = type;
    put16(packet + 4, length); put32(packet + 6, ++telemetry_seq);
    if (length) { memcpy(packet + 10, payload, length); }
    put32(packet + 10 + length, scci_rh_runtime_crc32(packet, 10 + length));
    uint32_t size = 14u + length;
    if (!scci_rh_runtime_queue_push(runtime, raw, size, scci_rh_backend_now_us())) {
        scci_rh_backend_stop(); return false;
    }
    uint32_t capacity = raw ? sizeof(raw_queue) : sizeof(normal_queue);
    uint8_t *queue = raw ? raw_queue : normal_queue;
    unsigned int key = irq_lock();
    uint32_t at = raw ? raw_write : normal_write;
    for (uint32_t i = 0; i < size; ++i) { queue[(at + i) % capacity] = packet[i]; }
    if (raw) { raw_write += size; } else { normal_write += size; }
    uart_irq_tx_enable(companion);
    irq_unlock(key);
    return true;
}

static void execute_actions(scci_rh_runtime *runtime)
{
    uint16_t actions = scci_rh_runtime_take_actions(runtime);
    if (actions & SCCI_RH_ACTION_MON_REARM) {
        pulse(PIN_MON_REARM0); pulse(PIN_MON_REARM1);
    }
    if (actions & SCCI_RH_ACTION_FAULT_RESET) { pulse(PIN_FAULT_RESET); }
    if (actions & SCCI_RH_ACTION_SUP_REARM) { pulse(PIN_SUP_REARM); }
    if (actions & SCCI_RH_ACTION_ROUTE_COMMIT) { pulse(PIN_COMMIT); }
    if (actions & SCCI_RH_ACTION_ROUTE_ACK) { pulse(PIN_ROUTE_ACK); }
    if (actions & SCCI_RH_ACTION_ROUTE_REARM) { pulse(PIN_ROUTE_REARM); }
    if (actions & SCCI_RH_ACTION_PHASE_REARM) {
        pulse(PIN_DRV_REARM); pulse(PIN_PHASE_REARM0); pulse(PIN_PHASE_REARM1);
    }
}
static bool route_write(scci_rh_runtime *runtime, uint8_t first, uint8_t second)
{
    if (!scci_rh_runtime_route_prepare(runtime, first, second, scci_rh_backend_now_us())) { return false; }
    if (ctrl_active) { nrfx_spim_uninit(&ctrl_spi); ctrl_active = false; }
    pin_output(PIN_CTRL_SCK, false); pin_output(PIN_CTRL_MOSI, false);
    uint8_t payload = (second << 4) | first;
    for (int bit = 7; bit >= 0; --bit) {
        nrf_gpio_pin_write(PIN_CTRL_MOSI, (payload >> bit) & 1);
        pulse(PIN_CTRL_SCK);
    }
    pulse(PIN_PRELOAD); k_busy_wait(25);
    execute_actions(runtime); /* Commit only after candidate setup. */
    k_busy_wait(25);
    uint32_t actual = sideband_snapshot();
    if ((actual & SIDEBAND_SENTINEL_MASK) != SIDEBAND_SENTINEL_VALUE) {
        trip(runtime, SCCI_RH_FAULT_ROUTE, 0x501); return false;
    }
    if (!scci_rh_runtime_route_readback(runtime, actual & 15, (actual >> 4) & 15,
                                     scci_rh_backend_now_us())) { return false; }
    execute_actions(runtime); /* Fresh ACK edge, then REARM edge. */
    return true;
}
static void control_dispatch(scci_rh_runtime *runtime)
{
    uint8_t type = command_frame[3];
    uint16_t length = get16(command_frame + 4);
    uint32_t sequence = get32(command_frame + 6);
    uint8_t *p = command_frame + 10;
    uint64_t now = scci_rh_backend_now_us();
    if (command_frame[2] != 1 ||
        get32(p + length) != scci_rh_runtime_crc32(command_frame, 10 + length)) {
        ++status.uart_rejects; trip(runtime, SCCI_RH_FAULT_PACKET, 0x601); return;
    }
    if (type != 2 && control_sequence_seen &&
        (sequence == last_control_sequence || sequence - last_control_sequence >= 0x80000000u)) {
        ++status.uart_rejects; trip(runtime, SCCI_RH_FAULT_PACKET, 0x602); return;
    }
    bool accepted = false;
    switch (type) {
    case 1: accepted = length == SCCI_RH_SBP_PACKET_BYTES && scci_rh_runtime_sbp(runtime, p, length, now); break;
    case 2:
        accepted = length == 24 && scci_rh_runtime_session(runtime, get32(p), get32(p + 4),
                                                       (int64_t)get64(p + 8), (int64_t)get64(p + 16), now);
        if (accepted) { control_sequence_seen = false; }
        break;
    case 3:
        accepted = length == 12 && p[1] == 0 && p[2] == 0 && p[3] == 0
            && scci_rh_runtime_command(runtime, (scci_rh_mode)p[0], get32(p + 4), sequence, get32(p + 8), now);
        if (accepted && p[0] != SCCI_RH_MODE_OBSERVE) {
            nrf_gpio_pin_clear(PIN_AFE_RECORD); nrf_gpio_pin_clear(PIN_AFE_CONNECT);
            status.observing = false;
        }
        break;
    case 4:
        accepted = length == 0 && scci_rh_runtime_recovery_begin(runtime, now);
        if (accepted) { execute_actions(runtime); recovery_stage = 1; recovery_after = scci_rh_backend_now_us() + 100; }
        break;
    case 5: accepted = length == 2 && route_write(runtime, p[0], p[1]); break;
    case 6:
        if (length == 20) {
            scci_rh_event_plan plan = {
                .epoch = get32(p), .event_id = get32(p + 4),
                .current_ua = { get16(p + 8), get16(p + 10) },
                .phase_us = get16(p + 12), .gap_us = get16(p + 14),
                .contact = { p[16], p[17] }, .source_mask = p[18], .off_trial = p[19]
            };
            accepted = scci_rh_runtime_event(runtime, &plan, now);
        }
        break;
    case 7:
        if (length == 0) { trip(runtime, SCCI_RH_FAULT_HARD_TRIP, 0x607); accepted = true; }
        break;
    default: break;
    }
    if (accepted) {
        last_control_sequence = sequence; control_sequence_seen = true;
    } else { ++status.uart_rejects; trip(runtime, SCCI_RH_FAULT_PACKET, 0x608); }
}
static void receive_commands(scci_rh_runtime *runtime)
{
    uint16_t budget = 256;
    while (budget-- && rx_read != rx_write) {
        uint8_t byte = rx_queue[rx_read++ % sizeof(rx_queue)];
        if (command_count == 0 && byte != 'A') { continue; }
        if (command_count == 1 && byte != 'O') { command_count = byte == 'A' ? 1 : 0; continue; }
        command_frame[command_count++] = byte;
        if (command_count == 6) {
            uint16_t length = get16(command_frame + 4);
            if (length > 96) { command_count = 0; trip(runtime, SCCI_RH_FAULT_PACKET, 0x609); continue; }
            command_need = 14 + length;
        }
        if (command_count >= 6 && command_count == command_need) {
            control_dispatch(runtime); command_count = 0;
        }
    }
}

static void raw_sample(scci_rh_runtime *runtime)
{
    uint8_t next = (raw_channel + 1) & 7;
    uint64_t lo, hi;
    bool known = raw_command(0xc000 | ((uint16_t)next << 10), 5, &lo, &hi);
    uint16_t code = ((uint16_t)dma_rx[2] << 8) | dma_rx[3];
    uint8_t claimed = dma_rx[4] >> 4;
    phase_cut_consume(runtime);
    bool valid = scci_rh_runtime_raw_identity(runtime, status.configuration_epoch, ++capture_id,
                                          raw_channel, claimed, lo, known, code != 0 && code != 65535,
                                          scci_rh_backend_now_us());
    scci_rh_raw_record record = { lo, hi, status.configuration_epoch, capture_id, code, claimed, valid };
    raw_archive[raw_head++ % SCCI_RH_RAW_RECORDS] = record;
    ++status.raw_received;
    raw_channel = next;
    if (!valid) { scci_rh_backend_stop(); return; }
    if (runtime->output.diagnostic_capture) {
        uint8_t payload[24];
        put64(payload, lo); put32(payload + 8, status.configuration_epoch);
        put32(payload + 12, capture_id); put16(payload + 16, code);
        payload[18] = claimed; payload[19] = valid; put32(payload + 20, hi - lo);
        packet_send(runtime, 0x83, payload, sizeof(payload), true);
    }
}
static bool endpoint_capture(scci_rh_runtime *runtime, uint8_t phase)
{
    scci_rh_endpoint_record record = { .epoch = status.configuration_epoch,
        .event_id = runtime->plan.event_id, .reset_epoch = status.integrator_epoch,
        .phase = phase, .source_mask = runtime->plan.source_mask, .valid = 0 };
    nrf_gpio_pin_set(PIN_MON_CS0); nrf_gpio_pin_set(PIN_MON_CS1);
    nrf_gpio_pin_clear(PIN_BOTH_CNV); k_busy_wait(2);
    record.aperture_lo_us = scci_rh_backend_now_us(); nrf_gpio_pin_set(PIN_BOTH_CNV);
    record.aperture_hi_us = scci_rh_backend_now_us();
    k_busy_wait(10); /* >8.8 us tCONV,max; CS stays high until conversion ends. */
    for (uint8_t i = 0; i < 2; ++i) {
        dma_tx[0] = dma_tx[1] = 0;
        if (!spi_transfer(&mon_spi, i ? PIN_MON_CS1 : PIN_MON_CS0, false, 2, NULL, NULL)) {
            trip(runtime, SCCI_RH_FAULT_SAMPLE, 0x701); return false;
        }
        record.code[i] = ((uint16_t)dma_rx[0] << 8) | dma_rx[1];
    }
    record.valid = runtime->sticky_fault == 0;
    endpoint_archive[endpoint_head++ % SCCI_RH_ENDPOINT_RECORDS] = record;
    ++status.endpoint_pairs;
    return true;
}
static void rhd_frame(scci_rh_runtime *runtime)
{
    scci_rh_rhd_record record = { .frame_lo_us = scci_rh_backend_now_us(),
        .epoch = status.configuration_epoch, .sequence = ++status.rhd_frames };
    uint64_t aperture_lo[19], aperture_hi[19];
    uint16_t words[19];
    bool known = true;
    for (uint8_t slot = 0; slot < 19; ++slot) {
        uint16_t command = slot < 16 ? (uint16_t)slot << 8 : slot == 16 ? 0x3000 : 0xff00;
        known = known && rhd_word(command, &words[slot], &aperture_lo[slot], &aperture_hi[slot]);
        if (!known) { break; }
        k_busy_wait(1); /* Transfer itself4us plus>=3us explicit CS allocations. */
    }
    for (uint8_t channel = 0; channel < 16; ++channel) {
        if (known) {
            record.samples[channel] = (int16_t)words[channel + 2];
            record.aperture_offset_lo_us[channel] = aperture_lo[channel + 1] - record.frame_lo_us;
            record.aperture_offset_hi_us[channel] = aperture_hi[channel + 1] - record.frame_lo_us;
        }
    }
    record.supply_code = known ? words[18] : 0;
    /* Mask is TRANSPORT identity only. A startup discard is not an analog
     * recovery qualification and the companion is told that explicitly. */
    record.valid_mask = known && nrf_gpio_pin_read(PIN_AFE_FAULT) ? 0xffff : 0;
    if (scci_rh_backend_now_us() - record.frame_lo_us > SCCI_RH_RHD_FRAME_US) { record.valid_mask = 0; }
    rhd_archive[rhd_head++ % SCCI_RH_RHD_RECORDS] = record;
    if (record.valid_mask) {
        if (!feature_first_us) { feature_first_us = record.frame_lo_us + record.aperture_offset_lo_us[0]; }
        feature_last_us = record.frame_lo_us + record.aperture_offset_hi_us[15];
        feature_transport_mask = record.valid_mask;
        for (uint8_t i = 0; i < 16; ++i) {
            int32_t sample = record.samples[i];
            uint32_t absolute = sample < 0 ? -sample : sample;
            envelope_q8[i] -= envelope_q8[i] >> 5;
            envelope_q8[i] += absolute << 3; /* 1/32 EMA of absolute rawADCcounts. */
            status.envelope[i] = envelope_q8[i] >> 8;
        }
    } else { feature_transport_mask = 0; trip(runtime, SCCI_RH_FAULT_SAMPLE, 0x702); }
}

static void phase_begin(scci_rh_runtime *runtime)
{
    request_clear();
    bool positive = runtime->state == SCCI_RH_STATE_PREPARE_FIRST;
    uint8_t mask = runtime->plan.source_mask;
    nrf_gpio_pin_write(PIN_PLUS0, positive && (mask & 1));
    nrf_gpio_pin_write(PIN_MINUS0, !positive && (mask & 1));
    nrf_gpio_pin_write(PIN_PLUS1, positive && (mask & 2));
    nrf_gpio_pin_write(PIN_MINUS1, !positive && (mask & 2));
    for (uint8_t i = 0; i < 2; ++i) {
        uint16_t code = ((uint32_t)runtime->plan.current_ua[i] * 65536u) / 25000u;
        if (!dac_write(8 + i, (mask & (1u << i)) ? code : 0)) {
            trip(runtime, SCCI_RH_FAULT_CONFIG, 0x801); return;
        }
    }
    k_busy_wait(25); /* Declared DAC/route preparation, not measured settling. */
    execute_actions(runtime);
    if (!health_update(runtime) || !scci_rh_runtime_phase_ready(runtime, scci_rh_backend_now_us())) { return; }
    uint64_t start = scci_rh_backend_now_us();
    if (!scci_rh_runtime_phase_start(runtime, start)) { return; }
    phase_scheduled_deadline = runtime->deadline_us;
    phase_cut_seen = false;
    NRF_TIMER0->EVENTS_COMPARE[2] = 0;
    NRF_TIMER0->CC[2] = (uint32_t)phase_scheduled_deadline;
    NRF_TIMER0->INTENSET = TIMER_INTENSET_COMPARE2_Msk;
    unsigned int key = irq_lock();
    if (scci_rh_backend_now_us() + 10 >= phase_scheduled_deadline) {
        irq_unlock(key); trip(runtime, SCCI_RH_FAULT_PHASE, 0x802); return;
    }
    if (mask & 1) { NRF_GPIOTE0_S->TASKS_SET[0] = 1; }
    if (mask & 2) { NRF_GPIOTE0_S->TASKS_SET[1] = 1; }
    __DSB();
    if (NRF_TIMER0->EVENTS_COMPARE[2] || scci_rh_backend_now_us() >= phase_scheduled_deadline) {
        request_clear(); irq_unlock(key); trip(runtime, SCCI_RH_FAULT_PHASE, 0x804); return;
    }
    irq_unlock(key);
}
static void phase_cut_consume(scci_rh_runtime *runtime)
{
    if (!phase_cut_seen) { return; }
    phase_cut_seen = false;
    uint64_t capture = (phase_scheduled_deadline & ~UINT64_C(0xffffffff)) | phase_cut_capture;
    if (capture != phase_scheduled_deadline ||
        (runtime->state != SCCI_RH_STATE_FIRST && runtime->state != SCCI_RH_STATE_SECOND)) {
        trip(runtime, SCCI_RH_FAULT_PHASE, 0x803); return;
    }
    scci_rh_runtime_phase_end(runtime, capture);
    /* Both requests were cleared by the SAME DPPI event that capturedCC1.
     * This is hardware event attribution, not an ISR arrival timestamp. */
}

bool scci_rh_backend_init(scci_rh_runtime *runtime)
{
    static const uint8_t low_outputs[] = {
        PIN_PRELOAD, PIN_COMMIT, PIN_ROUTE_REARM, PIN_ROUTE_ACK, PIN_WANT0, PIN_WANT1,
        PIN_AFE_CS, PIN_AFE_CONNECT, PIN_AFE_RECORD, PIN_BOTH_CNV,
        PIN_MON_REARM0, PIN_MON_REARM1, PIN_REQ0, PIN_REQ1,
        PIN_PLUS0, PIN_MINUS0, PIN_PLUS1, PIN_MINUS1,
        PIN_DRV_REARM, PIN_SUP_REARM, PIN_FAULT_RESET, PIN_WDI,
        PIN_PHASE_REARM0, PIN_PHASE_REARM1, PIN_RAW_RESET
    };
    for (size_t i = 0; i < sizeof(low_outputs); ++i) { pin_output(low_outputs[i], false); }
    pin_output(PIN_RAW_CS, true); pin_output(PIN_MON_CS0, true); pin_output(PIN_MON_CS1, true);
    pin_output(PIN_DAC_CS, true); pin_output(PIN_SIDEBAND_LOAD, true);
    pin_output(PIN_INT_RUN0, true); pin_output(PIN_INT_RUN1, true);
    nrf_gpio_cfg_input(PIN_SIDEBAND_DATA, NRF_GPIO_PIN_PULLDOWN);
    nrf_gpio_cfg_input(PIN_AFE_FAULT, NRF_GPIO_PIN_PULLDOWN);
    const struct device *clock = DEVICE_DT_GET(DT_NODELABEL(clock));
    if (!device_is_ready(clock)) { return false; }
    int clock_result = clock_control_on(clock, CLOCK_CONTROL_NRF_SUBSYS_HF);
    if (clock_result && clock_result != -EALREADY) { return false; }
    if (clock_control_get_status(clock, CLOCK_CONTROL_NRF_SUBSYS_HF) != CLOCK_CONTROL_STATUS_ON) { return false; }
    if (!timer_init()) { return false; }
    IRQ_CONNECT(NRFX_IRQ_NUMBER_GET(NRF_SPIM1), 2, rhd_irq, NULL, 0);
    IRQ_CONNECT(NRFX_IRQ_NUMBER_GET(NRF_SPIM2), 2, mon_irq, NULL, 0);
    IRQ_CONNECT(NRFX_IRQ_NUMBER_GET(NRF_SPIM3), 2, ctrl_irq, NULL, 0);
    IRQ_CONNECT(NRFX_IRQ_NUMBER_GET(NRF_SPIM4), 2, raw_irq, NULL, 0);
    irq_enable(NRFX_IRQ_NUMBER_GET(NRF_SPIM1)); irq_enable(NRFX_IRQ_NUMBER_GET(NRF_SPIM2));
    irq_enable(NRFX_IRQ_NUMBER_GET(NRF_SPIM3)); irq_enable(NRFX_IRQ_NUMBER_GET(NRF_SPIM4));
    if (!spi_init_one(&raw_spi, PIN_RAW_SCK, PIN_RAW_MOSI, PIN_RAW_MISO, 16000000, NRF_SPIM_MODE_1)
        || !spi_init_one(&rhd_spi, PIN_AFE_SCK, PIN_AFE_MOSI, PIN_AFE_MISO, 4000000, NRF_SPIM_MODE_0)
        || !spi_init_one(&mon_spi, PIN_MON_SCK, NRF_SPIM_PIN_NOT_CONNECTED, PIN_MON_MISO, 8000000, NRF_SPIM_MODE_0)
        || !ctrl_init() || !dac_write(4, 0x0103) || !dac_write(8, 0) || !dac_write(9, 0)) { return false; }
    nrf_gpio_cfg(PIN_RAW_SCK, NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT,
                 NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_H0H1, NRF_GPIO_PIN_NOSENSE);
    nrf_gpio_cfg(PIN_RAW_MOSI, NRF_GPIO_PIN_DIR_OUTPUT, NRF_GPIO_PIN_INPUT_DISCONNECT,
                 NRF_GPIO_PIN_NOPULL, NRF_GPIO_PIN_H0H1, NRF_GPIO_PIN_NOSENSE);
    if (!device_is_ready(companion) || uart_irq_callback_user_data_set(companion, uart_callback, NULL)) { return false; }
    uart_irq_rx_enable(companion);
    if (!raw_configure() || !rhd_configure()) { return false; }
    status.configuration_epoch = 1;
    status.commissioned = true;
    health_update(runtime);
    if (!scci_rh_runtime_configure(runtime, status.configuration_epoch, true, scci_rh_backend_now_us())) { return false; }
    uint64_t now = scci_rh_backend_now_us();
    next_raw = now; next_rhd = now; next_heartbeat = now;
    observe_after = now + SCCI_RH_RHD_RECOVERY_US; next_telemetry = now;
    return true;
}

void scci_rh_backend_service(scci_rh_runtime *runtime)
{
    phase_cut_consume(runtime); /* Hardware capture precedes later wallclock. */
    uint64_t now = scci_rh_backend_now_us();
    if (atomic_get(&uart_overflow)) {
        trip(runtime, atomic_get(&uart_overflow) == 2 ? SCCI_RH_FAULT_CLOCK : SCCI_RH_FAULT_OVERRUN, 0x901);
        atomic_clear(&uart_overflow);
        rx_read = rx_write; command_count = 0;
    }
    scci_rh_runtime_queue_drain(runtime, false, atomic_set(&normal_drained, 0));
    scci_rh_runtime_queue_drain(runtime, true, atomic_set(&raw_drained, 0));
    /* During an active phase, do not spend tens of microseconds on control
     * packets or serial sideband. Independent native analog supervision and
     * hardware compare retain cutoff; maincore stillcheckslease everyturn. */
    bool active = runtime->state == SCCI_RH_STATE_FIRST || runtime->state == SCCI_RH_STATE_SECOND;
    if (status.commissioned && now >= next_raw) {
        if (now - next_raw >= SCCI_RH_RAW_SLOT_US) { ++status.missed_raw_slots; }
        raw_sample(runtime);
        next_raw += SCCI_RH_RAW_SLOT_US;
        if (next_raw <= scci_rh_backend_now_us()) { next_raw = scci_rh_backend_now_us() + SCCI_RH_RAW_SLOT_US; }
    }
    if (!active) { health_update(runtime); receive_commands(runtime); }
    now = scci_rh_backend_now_us();
    if (recovery_stage && now >= recovery_after) {
        if (health_update(runtime) && scci_rh_runtime_rearm(runtime, scci_rh_backend_now_us())) {
            execute_actions(runtime);
        }
        recovery_stage = 0;
    }
    if (runtime->output.armed) {
        nrf_gpio_pin_write(PIN_WANT0, runtime->output.want_mask & 1);
        nrf_gpio_pin_write(PIN_WANT1, runtime->output.want_mask & 2);
    } else { request_clear(); nrf_gpio_pin_clear(PIN_WANT0); nrf_gpio_pin_clear(PIN_WANT1); }
    if (runtime->state == SCCI_RH_STATE_PREPARE_FIRST && last_runtime_state != SCCI_RH_STATE_PREPARE_FIRST) {
        /* A NEW admitted event, after retained previous history, establishes
         * an explicitly numbered baseline. Never executed by a trip handler. */
        nrf_gpio_pin_clear(PIN_INT_RUN0); nrf_gpio_pin_clear(PIN_INT_RUN1); k_busy_wait(10);
        ++status.integrator_epoch;
        endpoint_capture(runtime, 0);
        nrf_gpio_pin_set(PIN_INT_RUN0); nrf_gpio_pin_set(PIN_INT_RUN1);
    }
    if (runtime->state == SCCI_RH_STATE_PREPARE_FIRST || runtime->state == SCCI_RH_STATE_PREPARE_SECOND) {
        if (runtime->state == SCCI_RH_STATE_PREPARE_SECOND) { endpoint_capture(runtime, 1); }
        phase_begin(runtime);
    }
    if (runtime->state == SCCI_RH_STATE_RECOVERY && now >= runtime->deadline_us) { endpoint_capture(runtime, 2); }
    phase_cut_consume(runtime);
    scci_rh_runtime_tick(runtime, scci_rh_backend_now_us());
    bool observe_inhibit = runtime->mode == SCCI_RH_MODE_OBSERVE
        && (runtime->sticky_fault == SCCI_RH_FAULT_BOOT || runtime->sticky_fault == SCCI_RH_FAULT_CONFIG);
    if (runtime->sticky_fault && !observe_inhibit) {
        scci_rh_backend_stop();
    }
    bool observe = runtime->mode == SCCI_RH_MODE_OBSERVE && !runtime->output.armed
        && (!runtime->sticky_fault || observe_inhibit)
        && runtime->state == SCCI_RH_STATE_IDLE && runtime->quiet_mask == 3 && runtime->run_mask == 0
        && (runtime->health & (SCCI_RH_HEALTH_RESET | SCCI_RH_HEALTH_RAILS | SCCI_RH_HEALTH_POWER))
            == (SCCI_RH_HEALTH_RESET | SCCI_RH_HEALTH_RAILS | SCCI_RH_HEALTH_POWER);
    if (observe && status.commissioned) {
        if (!status.observing) {
            nrf_gpio_pin_set(PIN_AFE_CONNECT); nrf_gpio_pin_set(PIN_AFE_RECORD);
            status.observing = true; observe_after = scci_rh_backend_now_us() + SCCI_RH_RHD_RECOVERY_US;
        }
        now = scci_rh_backend_now_us();
        if (now >= next_rhd && now >= observe_after) {
            if (now - next_rhd >= SCCI_RH_RHD_FRAME_US) { ++status.missed_rhd_frames; }
            uint64_t start = now;
            rhd_frame(runtime); next_rhd = start + SCCI_RH_RHD_FRAME_US;
            if (next_rhd <= scci_rh_backend_now_us()) { next_rhd = scci_rh_backend_now_us() + SCCI_RH_RHD_FRAME_US; }
        }
    } else { status.observing = false; }
    now = scci_rh_backend_now_us();
    if (now >= next_heartbeat && runtime->config_valid) {
        heartbeat ^= 1; nrf_gpio_pin_write(PIN_WDI, heartbeat); next_heartbeat = now + 50000;
    }
    if (now >= next_telemetry && device_is_ready(companion)) {
        uint8_t payload[80];
        put64(payload, now); put32(payload + 8, status.configuration_epoch);
        put32(payload + 12, runtime->fault_total); put16(payload + 16, runtime->sticky_fault);
        payload[18] = runtime->mode; payload[19] = runtime->state;
        put16(payload + 20, runtime->health); payload[22] = 0; /* analogqualified=false */
        payload[23] = status.observing;
        for (uint8_t i = 0; i < 16; ++i) { put16(payload + 24 + 2 * i, status.envelope[i]); }
        put32(payload + 56, status.rhd_frames);
        put64(payload + 60, feature_first_us); put64(payload + 68, feature_last_us);
        put16(payload + 76, status.observing && now - feature_last_us <= 100000 ? feature_transport_mask : 0);
        put16(payload + 78, 0);
        packet_send(runtime, 0x81, payload, sizeof(payload), false);
        next_telemetry = now + 20000;
    }
    last_runtime_state = runtime->state;
}
const scci_rh_backend_status *scci_rh_backend_status_get(void) { return &status; }
