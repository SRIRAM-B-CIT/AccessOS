"""
Phase 3 Head Pointer Benchmark
"""
import os
import time
import psutil

from accessos.utils.config import Config
from accessos.engine.head_pointer import HeadPointerEngine, TrackingState

cfg = Config()
states = []
metrics = []

def on_state(state, detail):
    print(f"  [EVENT] State transitioned to: {state.value} ({detail})", flush=True)
    states.append((state, detail))

def on_metrics(fps, lat):
    metrics.append((fps, lat))

engine = HeadPointerEngine(
    config=cfg,
    on_state_changed=on_state,
    on_metrics_updated=on_metrics,
)

proc = psutil.Process()
mem_init = proc.memory_info().rss / (1024 * 1024)
print(f"Base RAM usage: {mem_init:.1f} MB", flush=True)

print("Starting HeadPointerEngine...", flush=True)
engine.start()

# Collect for 4 seconds of live camera processing
print("Running tracking loop for 4.0 seconds...", flush=True)
time.sleep(4.0)

mem_peak = proc.memory_info().rss / (1024 * 1024)
cpu = proc.cpu_percent(interval=0.5)

fps_vals = [m[0] for m in metrics if m[0] > 0]
lat_vals = [m[1] for m in metrics if m[1] > 0]

print("Stopping engine...", flush=True)
engine.stop()

avg_fps = sum(fps_vals) / len(fps_vals) if fps_vals else 0.0
avg_lat = sum(lat_vals) / len(lat_vals) if lat_vals else 0.0

print("\n" + "="*50, flush=True)
print(" ACCESSOS PHASE 3 BENCHMARK REPORT (ThinkPad T480)", flush=True)
print("="*50, flush=True)
print(f" Camera Hardware        : {engine._camera_device} (Chicony RGB)", flush=True)
print(f" Inference Framework    : MediaPipe 1.1 + XNNPACK CPU Delegate", flush=True)
print(f" Capture Resolution     : 640 x 480 @ 30 FPS", flush=True)
print(f" Average Processing FPS : {avg_fps:.1f} FPS", flush=True)
print(f" Vision-Processing Loop Latency : {avg_lat:.1f} ms per frame (frame grab -> landmarks -> filter)", flush=True)
print(f" CPU Utilization        : {cpu:.1f}%", flush=True)
print(f" Process RAM Footprint  : {mem_peak:.1f} MB (Delta: +{mem_peak - mem_init:.1f} MB)", flush=True)
print("="*50, flush=True)
