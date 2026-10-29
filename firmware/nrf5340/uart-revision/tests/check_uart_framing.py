"""Compile actual historical/revised UART callbacks against finite FIFO stubs.

The historical callback must reproduce frame corruption; the current callback
must preserve independently encoded AO/CRC frames across preemption, FIFO and
ring/uint32 wrap boundaries. This does not execute target UART peripherals.
Default is read-only; --write-report records the reviewed host evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
REPORT = HERE / "uart-framing-tests.json"
ORIGINAL = ROOT / "firmware/nrf5340/app/src/scci_rh_backend.c"
CURRENT = HERE / "src/scci_rh_backend.c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frame(kind: int, sequence: int, payload: bytes) -> bytes:
    body = struct.pack("<2sBBHI", b"AO", 1, kind, len(payload), sequence) + payload
    return body + struct.pack("<I", zlib.crc32(body))


def compile_run(path: Path, revised: bool, directory: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    begin = source.index("static void uart_callback(")
    end = source.index("\nstatic void put16(", begin)
    callback = source[begin:end]
    # Extract the actual ISR; only hardware and queues are replaced by stubs.
    # Include its actual persistent arbitration declarations in the new build.
    state = ""
    if revised:
        for declaration in ("static uint16_t tx_frame_remaining;", "static bool tx_frame_raw;"):
            if source.count(declaration) != 1:
                raise AssertionError("actual persistent frame ownership declaration missing")
            state += declaration + "\n"
    prefix = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct device { int unused; };
static uint8_t normal_queue[8192], raw_queue[16384], rx_queue[2048];
static volatile uint32_t normal_write, normal_read, raw_write, raw_read, rx_write, rx_read;
static int normal_drained, raw_drained, uart_overflow;
static uint8_t wire[1024];
static unsigned wire_count, tx_budget, fifo_limit;
static bool uart_irq_update(const struct device *d) { (void)d; return true; }
static int uart_err_check(const struct device *d) { (void)d; return 0; }
static bool uart_irq_rx_ready(const struct device *d) { (void)d; return false; }
static int uart_fifo_read(const struct device *d, uint8_t *b, unsigned n)
{ (void)d; (void)b; (void)n; return 0; }
static bool uart_irq_tx_ready(const struct device *d) { (void)d; return tx_budget > 0; }
static void uart_irq_tx_disable(const struct device *d) { (void)d; tx_budget = 0; }
static int uart_fifo_fill(const struct device *d, const uint8_t *b, unsigned n)
{
    (void)d;
    if (n > tx_budget) n = tx_budget;
    if (n > fifo_limit) n = fifo_limit;
    memcpy(wire + wire_count, b, n); wire_count += n; tx_budget -= n;
    return (int)n;
}
static void atomic_set(int *a, int v) { *a = v; }
static void atomic_add(int *a, int v) { *a += v; }
'''
    raw = frame(0x83, 1, bytes(range(24)))
    normal = frame(0x81, 2, bytes(range(80)))
    driver = prefix + state + callback
    for name, data in (("raw_frame", raw), ("normal_frame", normal)):
        driver += "\nstatic const uint8_t " + name + "[]={" + ",".join(map(str, data)) + "};\n"
    reset_state = "tx_frame_remaining=0; tx_frame_raw=false;" if revised else ""
    driver += r'''
static const struct device device={0};
static unsigned cases, failed;
static void reset(uint32_t base, unsigned limit)
{
    memset(normal_queue,0,sizeof(normal_queue)); memset(raw_queue,0,sizeof(raw_queue));
    normal_write=normal_read=raw_write=raw_read=base;
    rx_write=rx_read=0; normal_drained=raw_drained=uart_overflow=0;
    wire_count=0; tx_budget=0; fifo_limit=limit;
    RESET_FRAME_STATE
}
static void enqueue(bool raw)
{
    uint8_t *queue=raw?raw_queue:normal_queue;
    unsigned capacity=raw?sizeof(raw_queue):sizeof(normal_queue);
    const uint8_t *packet=raw?raw_frame:normal_frame;
    unsigned size=raw?sizeof(raw_frame):sizeof(normal_frame);
    uint32_t at=raw?raw_write:normal_write;
    for(unsigned i=0;i<size;i++) queue[(at+i)%capacity]=packet[i];
    if(raw) raw_write+=size; else normal_write+=size;
}
static void expect(bool raw_first)
{
    uint8_t expected[sizeof(raw_frame)+sizeof(normal_frame)];
    if(raw_first){memcpy(expected,raw_frame,sizeof(raw_frame));memcpy(expected+sizeof(raw_frame),normal_frame,sizeof(normal_frame));}
    else{memcpy(expected,normal_frame,sizeof(normal_frame));memcpy(expected+sizeof(normal_frame),raw_frame,sizeof(raw_frame));}
    ++cases;
    if(wire_count!=sizeof(expected)||memcmp(wire,expected,sizeof(expected))||uart_overflow
       ||(unsigned)normal_drained!=sizeof(normal_frame)||(unsigned)raw_drained!=sizeof(raw_frame)) ++failed;
}
int main(void)
{
    static const uint32_t bases[]={0,16376,UINT32_MAX-10};
    static const unsigned limits[]={1,3,128};
    for(unsigned base=0;base<3;base++) for(unsigned limit=0;limit<3;limit++)
        for(unsigned first=0;first<2;first++){
            unsigned size=first?sizeof(raw_frame):sizeof(normal_frame);
            for(unsigned cut=1;cut<size;cut++){
                reset(bases[base],limits[limit]);enqueue(first);
                tx_budget=cut;uart_callback(&device,NULL);
                enqueue(!first);tx_budget=sizeof(wire);uart_callback(&device,NULL);
                expect(first);
            }
        }
    /* Normal priority is retained at a complete frame boundary. */
    reset(0,128);enqueue(true);enqueue(false);
    tx_budget=sizeof(wire);uart_callback(&device,NULL);expect(false);
    /* A temporarily full hardware FIFO must retain ownership without loss. */
    reset(0,0);enqueue(true);tx_budget=4;uart_callback(&device,NULL);
    fifo_limit=3;tx_budget=4;uart_callback(&device,NULL);enqueue(false);
    tx_budget=sizeof(wire);uart_callback(&device,NULL);expect(true);
    printf("{\"scenarios\":%u,\"failed\":%u,\"passed\":%u}\n",cases,failed,cases-failed);
    return 0;
}
'''.replace("RESET_FRAME_STATE", reset_state)
    spec = importlib.util.spec_from_file_location("scci_rh_host_compiler", ROOT / "firmware/nrf5340/tests/check_runtime.py")
    runner = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(runner)
    name = "current" if revised else "historical"
    cfile = directory / f"{name}.c"
    binary = directory / (f"{name}.exe" if os.name == "nt" else name)
    cfile.write_text(driver, encoding="utf-8")
    subprocess.run(runner.compiler() + ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-parameter", str(cfile), "-o", str(binary)], check=True, capture_output=True, text=True)
    return json.loads(subprocess.check_output([str(binary)], text=True))


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="scci_rh-uart-framing-") as temp:
        directory = Path(temp)
        historical = compile_run(ORIGINAL, False, directory)
        current = compile_run(CURRENT, True, directory)
    if historical["failed"] == 0:
        raise AssertionError("historical framing defect was not reproduced")
    if current["failed"] or current["scenarios"] != historical["scenarios"]:
        raise AssertionError("revised callback failed finite UART framing scenarios")
    return {"schema": "scci_rh.uart-frame-regression.v1", "date": "2026-10-28", "original_design_date": "2026-10-17", "passed": True,
        "scope": "Actual C callbacks with FIFO/interrupt stubs; no target execution or physical UART proof",
        "historical": historical, "current": current,
        "covered": ["raw interrupted by new normal frame", "normal interrupted by new raw frame",
            "all partial-frame byte positions", "1/3/128-byte FIFO fills", "ring-buffer wrap",
            "uint32 queue-index wrap", "normal priority at frame boundary", "temporarily full FIFO"],
        "source_sha256_lf": {p.relative_to(ROOT).as_posix(): sha(p) for p in (ORIGINAL, CURRENT, Path(__file__))}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    try:
        result = run()
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "")
        print(exc.stderr or "")
        raise
    if args.write_report:
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    elif result != json.loads(REPORT.read_text(encoding="utf-8")):
        raise AssertionError("current UART regression differs from reviewed receipt")
    print(json.dumps({k: result[k] for k in ("passed", "historical", "current")}, sort_keys=True))


if __name__ == "__main__":
    main()
