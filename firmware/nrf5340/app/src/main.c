#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include "scci_rh_backend.h"

static scci_rh_runtime runtime;

int main(void)
{
    scci_rh_runtime_init(&runtime, 0);
    if (!scci_rh_backend_init(&runtime)) {
        scci_rh_backend_stop();
        scci_rh_runtime_trip(&runtime, SCCI_RH_FAULT_CONFIG, 0x100, scci_rh_backend_now_us());
        printk("SCCI_RH: commissioning failed, all requests inhibited\n");
    } else {
        printk("SCCI_RH: linked commissioning profile; explicit session/command/rearm required\n");
    }
    for (;;) {
        scci_rh_backend_service(&runtime);
        /* No sleep is a timing guarantee. The lower-rate profile detects missed
         * slots, uses actual aperture brackets, and never catches up stale work. */
        k_yield();
    }
    return 0;
}
