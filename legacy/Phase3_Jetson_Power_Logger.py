"""
PHASE 3: JETSON AUTOMATED HARDWARE-IN-THE-LOOP (HIL) METRICS
Target: Automate tegrastats power parsing and calculate energy per inference.
"""

import subprocess
import time
import re
import pandas as pd
import argparse

def start_tegrastats(log_file="tegra_power.log"):
    print(f"Starting tegrastats logging to {log_file}...")
    # Run in background
    process = subprocess.Popen(["sudo", "tegrastats", "--interval", "100", "--logfile", log_file])
    return process

def stop_tegrastats(process):
    print("Stopping tegrastats...")
    process.terminate()
    process.wait()
    # Ensure all zombie processes are killed
    subprocess.run(["sudo", "killall", "tegrastats"], stderr=subprocess.DEVNULL)

def parse_tegrastats(log_file):
    print("Parsing power metrics from log...")
    power_measurements = []
    
    with open(log_file, "r") as f:
        for line in f:
            # Match standard Orin NX power metric: POM_5V_IN 3456/3456
            # Extract the instantaneous power in milliWatts
            match = re.search(r'POM_5V_IN (\d+)/', line)
            if match:
                power_measurements.append(int(match.group(1)))
                
    if not power_measurements:
        print("Warning: No POM_5V_IN measurements found. Is this an Orin NX?")
        return 0.0

    avg_power_mw = sum(power_measurements) / len(power_measurements)
    return avg_power_mw

def main():
    parser = argparse.ArgumentParser()
    parser.append("--latency_ms", type=float, required=True, help="Average latency measured from trtexec in ms")
    parser.append("--duration_sec", type=int, default=30, help="Duration to run the power test")
    args = parser.parse_args()

    log_file = "tegra_power.log"
    
    # 1. Start logging
    proc = start_tegrastats(log_file)
    
    # 2. Simulated load / wait period
    # In a real run, you execute `trtexec` in a subprocess right here.
    print(f"Profiling power for {args.duration_sec} seconds...")
    time.sleep(args.duration_sec)
    
    # 3. Stop logging
    stop_tegrastats(proc)
    
    # 4. Parse and Calculate
    avg_power_mw = parse_tegrastats(log_file)
    energy_per_inference_mj = avg_power_mw * args.latency_ms / 1000.0 # mJ = mW * ms / 1000? No, mW * ms = microJoules. Actually Power(W) * Time(s) = Joules.
    # W * s = J -> (mW / 1000) * (ms / 1000) = J -> mW * ms = uJ.
    # So mJ = (mW * ms) / 1000.
    
    print("\n" + "="*50)
    print("--- JETSON EDGE ABLATION METRICS ---")
    print(f"Average Power Draw:   {avg_power_mw:.2f} mW")
    print(f"Inference Latency:    {args.latency_ms:.2f} ms")
    print(f"Energy per Inference: {energy_per_inference_mj:.4f} mJ")
    print("="*50)

if __name__ == "__main__":
    main()
