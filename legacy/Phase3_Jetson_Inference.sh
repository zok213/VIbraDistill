#!/bin/bash
# =========================================================================
# PHASE 3: EDGE INFERENCE & ABLATION (JETSON ORIN NX)
# Run natively on the edge hardware to generate paper metrics
# =========================================================================

echo "--- PHASE 3: JETSON ORIN NX NATIVE INFERENCE PIPELINE ---"

# 1. MAXIMIZE PERFORMANCE (Prevent thermal throttling during benchmarks)
echo "[1] Locking Jetson Clocks to maximum..."
sudo jetson_clocks
# 2. COMPILE C++ BENCHMARK (V3 Fix)
echo "[2] Compiling pipeline_benchmark.cpp with nvcc..."
nvcc pipeline_benchmark.cpp -lcufft -lnvinfer -o benchmark_exe
if [ $? -ne 0 ]; then
    echo "Compilation failed! Ensure CUDA and TensorRT are installed."
    exit 1
fi

# 3. POWER MODE LOOP & HARDWARE-SPECIFIC TRT COMPILATION (Expert Fix)
# Modes: 0 (MaxN), 1 (15W), 2 (10W)
for MODE in 0 1 2; do
    echo "====================================================="
    echo "SETTING POWER MODE: $MODE"
    sudo nvpmodel -m $MODE
    sudo jetson_clocks
    echo "Thermal stabilization (30s cooldown)..."
    sleep 30 
    
    echo "--- Building Hardware-Specific TRT Engines for Mode $MODE ---"
    # GPU Engine
    /usr/src/tensorrt/bin/trtexec \
      --onnx=student_distilled.onnx \
      --int8 --calib=cwru_calib.cache \
      --saveEngine=student_gpu_int8_mode${MODE}.engine \
      --iterations=10 \
      --warmUp=5 > /dev/null
    
    # NVDLA Engine
    /usr/src/tensorrt/bin/trtexec \
      --onnx=student_distilled.onnx \
      --int8 --calib=cwru_calib.cache \
      --useDLACore=0 --allowGPUFallback \
      --saveEngine=student_dla_int8_mode${MODE}.engine \
      --iterations=10 \
      --warmUp=5 > /dev/null

    echo "--- Executing Benchmarks ---"
    echo "   -> Running on Jetson GPU (INT8) in Mode $MODE..."
    tegrastats --interval 100 --logfile tegrastats_gpu_mode${MODE}.log &
    /usr/src/tensorrt/bin/trtexec --loadEngine=student_gpu_int8_mode${MODE}.engine --iterations=1000 > /dev/null
    kill %1
    
    echo "   -> Running on NVDLA Core 0 (INT8) in Mode $MODE..."
    tegrastats --interval 100 --logfile tegrastats_dla_mode${MODE}.log &
    /usr/src/tensorrt/bin/trtexec --loadEngine=student_dla_int8_mode${MODE}.engine --iterations=1000 > /dev/null
    kill %1
    
    echo "   -> Running C++ End-to-End Pipeline Benchmark in Mode $MODE..."
    ./benchmark_exe
done

echo "Deployment pipeline execution complete. Record metrics for Ablation Table."
echo "Check tegrastats logs to verify GR3D_FREQ did not thermally throttle!"
