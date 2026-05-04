# ⚡ Phase 3: Jetson Orin NX Edge Ablation
> **Hardware-in-the-loop (HIL) Benchmarking & Profiling**

This directory contains the scripts required to perform Phase 3 of the VIbraDistill pipeline: **Edge Hardware Ablation.**

## 🛠️ Components
1.  **`jetson_inference.sh`**: Shell script to run the ONNX model via TensorRT with DLA/CUDA selection.
2.  **`power_logger.py`**: Real-time power monitoring script (INA219 or Jtop-based) to measure Watts per inference.
3.  **`pipeline_benchmark.cpp`**: C++ benchmark tool for sub-millisecond latency profiling.

## 🚀 Execution Flow
1.  **Export Model:** Ensure you have the `model.onnx` exported from the Master Notebook.
2.  **Build TensorRT Engine:**
    ```bash
    trtexec --onnx=model.onnx --saveEngine=model.trt --int8 --useDLACore=0 --allowGPUFallback
    ```
3.  **Run Benchmarks:**
    ```bash
    # Monitor power in background
    python3 power_logger.py --output power_stats.csv &
    # Run latency benchmark
    ./pipeline_benchmark model.trt
    ```

## 📊 Reported Metrics
*   **Throughput (FPS):** Inferences per second.
*   **Latency (ms):** Pre-processing + Inference + Post-processing.
*   **Joule/Inference:** Total energy cost per diagnostic window.
