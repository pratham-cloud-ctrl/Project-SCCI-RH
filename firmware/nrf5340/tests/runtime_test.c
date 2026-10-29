#include "scci_rh_runtime.h"
#include "packet_fixture.h"
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned assertions,scenarios;
#define CHECK(c) do { ++assertions; if (!(c)) { \
    fprintf(stderr,"assertion failed at %s:%d: %s\n",__FILE__,__LINE__,#c); \
    exit(1); } } while(0)
static uint64_t setup(scci_rh_runtime *r, scci_rh_mode mode) {
    uint64_t t=2000000;
    scci_rh_runtime_init(r,t);
    scci_rh_runtime_health(r,SCCI_RH_REQUIRED_HEALTH,3,0,0,t);
    CHECK(scci_rh_runtime_configure(r,1,true,t));
    CHECK(scci_rh_runtime_raw_identity(r,1,10,0,0,t,true,true,t));
    if (mode==SCCI_RH_MODE_PRESSURE) {
        CHECK(scci_rh_runtime_session(r,7,1,-500,500,t));
        CHECK(scci_rh_runtime_sbp(r,fixture_packet,sizeof fixture_packet,t));
    }
    CHECK(scci_rh_runtime_command(r,mode,1,1,
          mode==SCCI_RH_MODE_PRESSURE?3000000u:mode==SCCI_RH_MODE_DIAGNOSTIC?100000u:250000u,t));
    CHECK(scci_rh_runtime_rearm(r,t));
    CHECK(scci_rh_runtime_take_actions(r)==(SCCI_RH_ACTION_FAULT_RESET|SCCI_RH_ACTION_SUP_REARM));
    return t;
}
static void route(scci_rh_runtime *r,uint64_t t,uint8_t c0,uint8_t c1) {
    CHECK(scci_rh_runtime_route_prepare(r,c0,c1,t));
    CHECK(scci_rh_runtime_take_actions(r)==SCCI_RH_ACTION_ROUTE_COMMIT);
    CHECK(scci_rh_runtime_route_readback(r,c0,c1,t));
    CHECK(scci_rh_runtime_take_actions(r)==(SCCI_RH_ACTION_ROUTE_ACK|SCCI_RH_ACTION_ROUTE_REARM));
}
static scci_rh_event_plan plan(uint8_t mask) {
    scci_rh_event_plan p={0};
    p.epoch=1;p.event_id=1;p.current_ua[0]=3000;p.current_ua[1]=2500;
    p.phase_us=200;p.gap_us=200;p.contact[0]=2;p.contact[1]=9;
    p.source_mask=mask;
    return p;
}
static void start(scci_rh_runtime *r,scci_rh_event_plan *p,uint64_t t) {
    route(r,t,p->contact[0],p->contact[1]);
    CHECK(scci_rh_runtime_event(r,p,t));
    CHECK(scci_rh_runtime_take_actions(r)==SCCI_RH_ACTION_PHASE_REARM);
    CHECK(scci_rh_runtime_phase_ready(r,t));
    CHECK(scci_rh_runtime_phase_start(r,t));
    CHECK(r->output.request_mask==p->source_mask);
}
static void reseal(uint8_t *p) {
    uint32_t crc=scci_rh_runtime_crc32(p,52);
    unsigned i;
    for(i=0;i<4;++i) p[52+i]=(uint8_t)(crc>>(8*i));
}
static void put32(uint8_t *p,uint32_t value) {
    unsigned i; for(i=0;i<4;++i)p[i]=(uint8_t)(value>>(8*i));
}
static void put64(uint8_t *p,uint64_t value) {
    unsigned i; for(i=0;i<8;++i)p[i]=(uint8_t)(value>>(8*i));
}
static void packets(void) {
    unsigned fault;
    for(fault=0;fault<22;++fault) {
        scci_rh_runtime r; uint8_t p[SCCI_RH_SBP_PACKET_BYTES];
        size_t len=sizeof p; uint64_t t=2000000;
        ++scenarios;
        scci_rh_runtime_init(&r,t);
        CHECK(scci_rh_runtime_session(&r,7,1,-500,500,t));
        memcpy(p,fixture_packet,sizeof p);
        switch(fault) {
        case 0: len=55; break;
        case 1: p[41]^=1; break;
        case 2: p[0]='X'; reseal(p); break;
        case 3: p[2]=2; reseal(p); break;
        case 4: p[3]=1; reseal(p); break;
        case 5: p[36]=11; reseal(p); break;
        case 6: p[38]=1; reseal(p); break;
        case 7: put32(p+4,8); reseal(p); break;
        case 8: put64(p+12,1700000); put64(p+20,1600000); reseal(p); break;
        case 9: put64(p+28,1500000); reseal(p); break;
        case 10: put64(p+20,2000001); put64(p+28,2000010); reseal(p); break;
        case 11: put64(p+12,1); reseal(p); t=3000000; break;
        case 12: put32(p+40,0x7fc00000u); reseal(p); break;
        case 13: put32(p+44,0x7f800000u); reseal(p); break;
        case 14: put32(p+40,0x42440000u); reseal(p); break; /* 49 */
        case 15: put32(p+40,0x437b0000u); reseal(p); break; /* 251 */
        case 16: put32(p+44,0xbf800000u); reseal(p); break;
        case 17: put32(p+44,0x424c0000u); reseal(p); break; /* 51 */
        case 18: put32(p+48,2); reseal(p); break;
        case 19: CHECK(scci_rh_runtime_sbp(&r,p,len,t)); break; /* sequence replay */
        case 20: CHECK(scci_rh_runtime_sbp(&r,p,len,t)); put32(p+8,2); reseal(p); break;
        case 21: r.session_valid=0; break;
        }
        CHECK(!scci_rh_runtime_sbp(&r,p,len,t));
        CHECK(!r.pressure_valid && r.sticky_fault==SCCI_RH_FAULT_PACKET);
        CHECK(!r.output.request_mask && !r.output.armed);
    }
    {
        scci_rh_runtime r; uint8_t p[56]; uint64_t t=setup(&r,SCCI_RH_MODE_PRESSURE);
        ++scenarios;
        CHECK(r.pressure_valid);
        scci_rh_runtime_tick(&r,3499501);
        CHECK(r.sticky_fault==SCCI_RH_FAULT_STALE && !r.output.armed);
        CHECK(!scci_rh_runtime_rearm(&r,3499501));
        memcpy(p,fixture_packet,sizeof p);
        put32(p+8,2);put64(p+12,3000000);put64(p+20,3100000);
        put64(p+28,3200000);reseal(p);
        CHECK(scci_rh_runtime_sbp(&r,p,56,3500000));
        CHECK(!r.output.armed); /* new support does not rearm */
        CHECK(scci_rh_runtime_rearm(&r,3500000));
        (void)t;
    }
    {
        scci_rh_runtime r; uint8_t p[56];
        ++scenarios;
        scci_rh_runtime_init(&r,2000000);
        CHECK(!scci_rh_runtime_session(&r,7,1,-501,501,2000000));
        CHECK(!scci_rh_runtime_session(&r,7,1,INT64_MIN,INT64_MAX,2000000));
        CHECK(scci_rh_runtime_session(&r,7,1,-500,500,2000000));
        memcpy(p,fixture_packet,sizeof p);put32(p+8,UINT32_MAX);reseal(p);
        CHECK(scci_rh_runtime_sbp(&r,p,56,2000000));
        put32(p+8,0);put64(p+12,1500001);reseal(p);
        CHECK(scci_rh_runtime_sbp(&r,p,56,2000000));
        put32(p+8,0x80000000u);put64(p+12,1500002);reseal(p);
        CHECK(!scci_rh_runtime_sbp(&r,p,56,2000000));
    }
}
int main(void) {
    scci_rh_runtime r;
    scci_rh_event_plan p;
    uint64_t t,extended;
    unsigned i,mask;
    ++scenarios;
    scci_rh_runtime_init(&r,0);
    CHECK(r.sticky_fault==SCCI_RH_FAULT_BOOT && !r.output.armed);
    CHECK(!scci_rh_runtime_rearm(&r,0));
    p=plan(1);CHECK(!scci_rh_runtime_event(&r,&p,0));
    CHECK(scci_rh_runtime_crc32((const uint8_t *)"123456789",9)==0xcbf43926u);
    CHECK(scci_rh_runtime_crc32(fixture_packet,52)==fixture_crc);
    CHECK(scci_rh_runtime_extend_ticks(0xfffffff0u,0x10u,100,&extended));
    CHECK(extended==132);
    CHECK(!scci_rh_runtime_extend_ticks(0,0x80000000u,0,&extended));
    CHECK(!scci_rh_runtime_extend_ticks(100,99,0,&extended));
    CHECK(!scci_rh_runtime_extend_ticks(0,10,UINT64_MAX-5,&extended));

    ++scenarios;
    scci_rh_runtime_init(&r,2000000);
    scci_rh_runtime_health(&r,(uint16_t)(SCCI_RH_REQUIRED_HEALTH&~SCCI_RH_HEALTH_MONITORS),3,0,0,2000000);
    CHECK(scci_rh_runtime_configure(&r,1,true,2000000));
    CHECK(scci_rh_runtime_raw_identity(&r,1,10,0,0,2000000,true,true,2000000));
    CHECK(scci_rh_runtime_command(&r,SCCI_RH_MODE_MOTOR,1,1,250000,2000000));
    CHECK(!scci_rh_runtime_rearm(&r,2000000));
    CHECK(scci_rh_runtime_recovery_begin(&r,2000000));
    CHECK(scci_rh_runtime_take_actions(&r)==SCCI_RH_ACTION_MON_REARM);
    CHECK(!r.output.armed && r.sticky_fault!=SCCI_RH_FAULT_NONE);
    CHECK(!scci_rh_runtime_rearm(&r,2000001));
    CHECK(!scci_rh_runtime_take_actions(&r)); /* no repeated clear */
    scci_rh_runtime_health(&r,SCCI_RH_REQUIRED_HEALTH,3,0,0,2000010);
    CHECK(scci_rh_runtime_rearm(&r,2000010));
    CHECK(scci_rh_runtime_take_actions(&r)==(SCCI_RH_ACTION_FAULT_RESET|SCCI_RH_ACTION_SUP_REARM));
    CHECK(!scci_rh_runtime_recovery_begin(&r,2000010));

    for(mask=1;mask<=3;++mask) {
        ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan((uint8_t)mask);
        start(&r,&p,t);
        scci_rh_runtime_health(&r,SCCI_RH_REQUIRED_HEALTH,0,mask,mask,t+1);
        scci_rh_runtime_phase_end(&r,t+200);
        CHECK(!r.output.request_mask && r.state==SCCI_RH_STATE_GAP);
        scci_rh_runtime_tick(&r,t+399);CHECK(r.state==SCCI_RH_STATE_GAP);
        scci_rh_runtime_tick(&r,t+400);CHECK(r.state==SCCI_RH_STATE_GAP); /* wait actual quiet */
        scci_rh_runtime_health(&r,SCCI_RH_REQUIRED_HEALTH,3,0,0,t+410);
        scci_rh_runtime_tick(&r,t+410);
        CHECK(r.state==SCCI_RH_STATE_PREPARE_SECOND && !r.output.plus_mask);
        CHECK(scci_rh_runtime_take_actions(&r)==SCCI_RH_ACTION_PHASE_REARM);
        CHECK(scci_rh_runtime_phase_ready(&r,t+411));
        CHECK(scci_rh_runtime_phase_start(&r,t+412));
        CHECK(r.output.request_mask==mask && !r.output.plus_mask);
        scci_rh_runtime_phase_end(&r,t+612);
        CHECK(r.state==SCCI_RH_STATE_RECOVERY);
        scci_rh_runtime_tick(&r,t+613);
        CHECK(r.state==SCCI_RH_STATE_IDLE && !r.output.want_mask);
    }
    for(i=0;i<7;++i) {
        ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(3);start(&r,&p,t);
        scci_rh_runtime_health(&r,(uint16_t)(SCCI_RH_REQUIRED_HEALTH&~(1u<<i)),0,3,3,t+50);
        CHECK(!r.output.request_mask && !r.output.want_mask && !r.output.armed);
        scci_rh_runtime_health(&r,SCCI_RH_REQUIRED_HEALTH,3,0,0,t+500);
        scci_rh_runtime_tick(&r,t+1000);
        CHECK(!r.output.armed && !r.output.request_mask);
        CHECK(scci_rh_runtime_rearm(&r,t+1000));
        CHECK(!r.route_valid && !r.output.request_mask);
    }
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(3);start(&r,&p,t);
    scci_rh_runtime_trip(&r,SCCI_RH_FAULT_HARD_TRIP,19,t+17);
    scci_rh_runtime_tick(&r,t+700);
    CHECK(r.state==SCCI_RH_STATE_IDLE && !r.output.request_mask);
    CHECK(r.faults[(r.fault_head+15u)%16u].detail==19);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(1);start(&r,&p,t);
    scci_rh_runtime_tick(&r,t+201);
    CHECK(r.sticky_fault==SCCI_RH_FAULT_PHASE && !r.output.request_mask);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(1);start(&r,&p,t);
    scci_rh_runtime_phase_end(&r,t+199);
    CHECK(r.sticky_fault==SCCI_RH_FAULT_PHASE && !r.output.request_mask);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(1);start(&r,&p,t);
    CHECK(!scci_rh_runtime_rearm(&r,t+1));
    CHECK(!scci_rh_runtime_route_prepare(&r,1,2,t+1));
    CHECK(!r.output.request_mask);

    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(3);p.off_trial=1;
    route(&r,t,2,9);CHECK(scci_rh_runtime_event(&r,&p,t));
    CHECK(!r.output.request_mask && !r.output.want_mask && r.state==SCCI_RH_STATE_IDLE);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_OBSERVE);p=plan(1);route(&r,t,2,9);
    CHECK(!scci_rh_runtime_event(&r,&p,t));CHECK(!r.output.request_mask);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_DIAGNOSTIC);p=plan(1);route(&r,t,2,9);
    CHECK(!scci_rh_runtime_event(&r,&p,t));CHECK(!r.output.request_mask);

    for(i=0;i<9;++i) {
        ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(3);
        if(i==0){p.contact[1]=2;route(&r,t,2,2);}else route(&r,t,2,9);
        switch(i){case 1:p.phase_us=201;break;case 2:p.gap_us=199;break;
        case 3:p.current_ua[0]=3001;break;case 4:p.current_ua[1]=0;break;
        case 5:p.source_mask=0;break;case 6:p.epoch=2;break;
        case 7:p.contact[0]=3;break;case 8:p.event_id=0;break;default:break;}
        CHECK(!scci_rh_runtime_event(&r,&p,t));CHECK(!r.output.request_mask);
    }
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(scci_rh_runtime_route_prepare(&r,2,9,t));
    CHECK(!scci_rh_runtime_route_readback(&r,2,9,t)); /* COMMIT not served */
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(scci_rh_runtime_route_prepare(&r,2,9,t));(void)scci_rh_runtime_take_actions(&r);
    CHECK(!scci_rh_runtime_route_readback(&r,2,8,t));CHECK(!r.route_valid);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);route(&r,t,2,9);
    CHECK(!scci_rh_runtime_route_readback(&r,2,9,t)); /* stale readback */
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(1);
    CHECK(scci_rh_runtime_route_prepare(&r,2,9,t));
    (void)scci_rh_runtime_take_actions(&r);
    CHECK(scci_rh_runtime_route_readback(&r,2,9,t));
    CHECK(!scci_rh_runtime_event(&r,&p,t)); /* ACK/route rearm not served */
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(scci_rh_runtime_rearm(&r,t));
    CHECK(!scci_rh_runtime_route_prepare(&r,2,9,t)); /* supervisor rearm not served */
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);p=plan(1);route(&r,t,2,9);
    CHECK(scci_rh_runtime_event(&r,&p,t));
    CHECK(!scci_rh_runtime_phase_ready(&r,t)); /* rearm not served */

    for(i=0;i<7;++i) {
        uint32_t ep=1,cap=11;uint8_t expected=1,claimed=1;
        bool known=true,inrange=true;uint64_t aperture;
        ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);aperture=t+2;
        switch(i){case 0:ep=2;break;case 1:cap=12;break;
        case 2:claimed=2;break;case 3:known=false;break;
        case 4:inrange=false;break;case 5:aperture=t;break;
        case 6:aperture=t+4;break;}
        CHECK(!scci_rh_runtime_raw_identity(&r,ep,cap,expected,claimed,aperture,known,inrange,t+3));
        CHECK(!r.config_valid && !r.sample_seen && !r.output.armed);
        CHECK(!scci_rh_runtime_rearm(&r,t+3));
        CHECK(!scci_rh_runtime_configure(&r,1,true,t+3));
        CHECK(scci_rh_runtime_configure(&r,2,true,t+3));
    }
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    r.last_capture_id=UINT32_MAX;
    CHECK(scci_rh_runtime_raw_identity(&r,1,0,1,1,t+2,true,true,t+3));
    ++scenarios;t=setup(&r,SCCI_RH_MODE_DIAGNOSTIC);
    CHECK(scci_rh_runtime_queue_push(&r,true,16384,t));
    CHECK(!scci_rh_runtime_queue_push(&r,true,1,t));
    CHECK(r.raw_queue_used==16384 && !r.output.diagnostic_capture);
    scci_rh_runtime_queue_drain(&r,true,UINT32_MAX);CHECK(!r.raw_queue_used);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_DIAGNOSTIC);
    scci_rh_runtime_tick(&r,t+100000);CHECK(!r.output.diagnostic_capture);
    CHECK(!scci_rh_runtime_queue_push(&r,true,1,t+100000));
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(scci_rh_runtime_queue_push(&r,false,8192,t));
    CHECK(!scci_rh_runtime_queue_push(&r,false,UINT32_MAX,t));
    CHECK(r.normal_queue_used==8192);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    scci_rh_runtime_tick(&r,t+250000);CHECK(r.sticky_fault==SCCI_RH_FAULT_LEASE);
    CHECK(!scci_rh_runtime_rearm(&r,t+250000));
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(!scci_rh_runtime_command(&r,SCCI_RH_MODE_MOTOR,1,1,250000,t));
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(!scci_rh_runtime_command(&r,SCCI_RH_MODE_MOTOR,1,2,250001,t));
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    CHECK(!scci_rh_runtime_command(&r,SCCI_RH_MODE_PRESSURE,2,2,3000000,t));
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    scci_rh_runtime_tick(&r,t-1);CHECK(r.sticky_fault==SCCI_RH_FAULT_CLOCK);
    ++scenarios;t=setup(&r,SCCI_RH_MODE_MOTOR);
    for(i=0;i<100;++i)scci_rh_runtime_trip(&r,SCCI_RH_FAULT_HARD_TRIP,(uint16_t)i,t+i);
    CHECK(r.fault_count==16 && r.fault_head<16 && r.fault_total>=100);
    CHECK(r.faults[(r.fault_head+15u)%16u].detail==99);
    packets();
    printf("{\"scenarios\":%u,\"assertions\":%u,\"runtime_bytes\":%u,"
           "\"fault_record_bytes\":%u,\"passed\":true}\n",
           scenarios,assertions,(unsigned)sizeof(scci_rh_runtime),(unsigned)sizeof(scci_rh_fault_record));
    return 0;
}
