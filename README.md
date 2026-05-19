# CMP720 Project: Context-Aware Deadline Scheduling Under Memory Contention for Embedded Real-Time Systems

This repository contains the source code and documentation for the CMP720 final project. The project explores and implements context-aware deadline scheduling techniques designed to mitigate task deadline misses under memory contention in embedded real-time systems.

By using an STM32 microcontroller and FreeRTOS, the system implements a dynamic scheduling heuristic that detects cache contention and selectively reorders tasks at runtime when there is sufficient scheduling slack, preventing back-to-back execution of memory-heavy tasks. Additionally, an offline Ant Colony Optimization (ACO) solver is provided to compute the mathematical upper bound (optimal schedule) for comparison.

---

## Project Structure

```
cmp720-embed-final-project/
├── codes/
│   └── ProjectContextAwareScheduling/
│       ├── Core/
│       │   ├── Inc/
│       │   │   ├── core/                  # Scheduler interfaces & configurations
│       │   │   │   ├── ContextAwareScheduler.h
│       │   │   │   ├── EDFScheduler.h
│       │   │   │   ├── IScheduler.h
│       │   │   │   ├── NativeScheduler.h
│       │   │   │   └── TaskConfig.h
│       │   │   ├── test/                  # Metrics & testing structures
│       │   │   │   └── SchedulerTest.h
│       │   │   └── ...
│       │   └── Src/
│       │       ├── core/                  # Scheduler implementations
│       │       │   ├── ContextAwareScheduler.cpp
│       │       │   ├── EDFScheduler.cpp
│       │       │   ├── IScheduler.cpp
│       │       │   ├── NativeScheduler.cpp
│       │       │   └── TaskConfig.cpp
│       │       ├── test/                  # Test telemetry & workload emulators
│       │       │   └── SchedulerTest.cpp
│       │       └── app_main.cpp           # Main C++ entry point
│       │
│       ├── app/                           # Web GUI Dashboard application files
│       │   ├── gui_server.py              # FastAPI Dashboard Backend
│       │   ├── index.html                 # Dashboard HTML UI
│       │   └── scratch.py                 # Styling patch script
│       │
│       ├── logs/                          # Telemetry logs and benchmark results
│       │   └── auto_tests/                # Automated run captures
│       │
│       ├── offline_aco_baseline/          # Python offline simulator & ACO solver
│       │   ├── aco_solver.py              # Non-preemptive ACO solver
│       │   ├── preemptive_aco_solver.py   # Preemptive ACO solver
│       │   ├── baselines.py               # RMS, EDF, and Context-Aware simulators
│       │   ├── scheduler_model.py         # Task/job models & contention functions
│       │   ├── param_sweep.py             # Hyper-parameter sensitivity analyzer
│       │   └── main.py                    # Offline CLI interface
│       │
│       ├── automate_schedulers.py         # CLI automated build, flash, & log utility
│       └── CMakeLists.txt                 # Project build configuration
│
└── docs/                                  # Project documentation
    ├── Project_Proposal/                  # Initial project proposal
    ├── Extended_Project_Proposal/         # Extended project proposal
    └── Midterm_Presentation/              # Slides & presentation materials
```

---

## Embedded Software Architecture

The embedded firmware is built on **FreeRTOS** and targets the **STM32L452XX** microcontroller (configured using STM32CubeMX). Hardware profiling, execution cycle counting, and scheduling overhead measurements are performed using the **ARM DWT (Data Watchpoint and Trace)** cycle counter.

### Task Workload Profile

To simulate real-world mixed-criticality loads with varying memory access profiles, the system defines **four statically allocated tasks**:

| Task | Name | Priority (Native) | Period (ms) | Nominal WCET (ms) | Memory Intensity | Profile & Description |
|---|---|:---:|:---:|:---:|:---:|---|
| **$\tau_1$** | Motor Control | 4 (Highest) | 10 | 2 | 0.10 (Low) | **Compute-dominant**: Emulates a PID control loop using floating-point updates. |
| **$\tau_2$** | Sensor Acquisition | 2 | 50 | 5 | 0.20 (Low) | **Low memory intensity**: Periodic ADC sampling and filtering. |
| **$\tau_3$** | Crypto Encryption | 1 (Lowest) | 500 | 75 | 0.90 (High) | **Memory-bound**: Large (8 KB) buffer manipulation, AES-like operations. |
| **$\tau_4$** | Vision Processing | 3 | 20 | 4 | 0.80 (High) | **Memory-bound**: Fast periodic image transforms on a 4 KB buffer. |

### Memory Contention Model
If a memory-bound task (intensity $> 0.50$, i.e., $\tau_3$ or $\tau_4$) is scheduled immediately after another memory-bound task, the cache lines are thrashed. We simulate this by applying a **contention penalty of 30 ms** to the second task's execution time, representing the real-world performance degradation of cache misses on embedded microcontrollers.

---

## Schedulers

The system implements three distinct schedulers in C++:

1. **Native FreeRTOS Scheduler**: Standard fixed-priority preemptive scheduling based on the tasks' static priority levels.
2. **Earliest Deadline First (EDF) Scheduler**: Dynamically assigns FreeRTOS task priorities based on the closest absolute deadline. EDF is prone to cache thrashing because it can schedule high-memory tasks ($\tau_3, \tau_4$) back-to-back if their deadlines align.
3. **Context-Aware Scheduler (CAS)**: Extends EDF with a cache-contention penalty heuristic:
   $$P = \alpha \cdot M_{prev} \cdot M_{cand}$$
   If the penalty exceeds a configured threshold (default `0.15`), the scheduler checks if the candidate task has sufficient deadline slack (determined using safety margins). If slack permits, it temporarily swaps the execution order, running a lower-memory ready task (like $\tau_2$) to act as a cache-clearance buffer and delay the memory-heavy task.

---

## Interactive Web GUI & Test Lab

The project features a full-stack developer dashboard that serves as a **Performance Lab** to experiment with scheduler configurations and visualize results.

### Features
- **Live Parameter Customization**: Fine-tune the context-aware penalty weight ($\alpha$), safety margin, memory intensity threshold, and individual task periods/priorities using interactive slider controls.
- **Automated HW Benchmarking**: Triggers automated test sequences that programmatically update `TaskConfig.h`, run CMake builds, flash the firmware to the connected STM32 board via `STM32_Programmer_CLI`, capture UART telemetry on the COM port, and display results.
- **Real-Time Telemetry Plots**: Compares and graphs performance metrics:
  - **Deadline Miss Ratio (DMR%)**
  - **Response-time Jitter** (calculated using Welford's algorithm)
  - **Total Cache Contention Penalty**
  - **Scheduler Decision Overhead** (captured via DWT cycle count)
  - **Simulated Hardware States** (Motor PID variables, Sensor ADC telemetry)
- **Offline ACO Solver**: Simulates and solves optimal schedules using Ant Colony Optimization (preemptive and non-preemptive) and plots baseline comparison tables and convergence graphs.
- **Telemetry Log Uploader**: Uploads and visualizes historical serial log files.

---

## Hardware and Toolchain Requirements

To compile and flash the firmware:
- **Build System**: CMake (version 3.22 or higher)
- **Languages**: C11, C++23
- **Compiler**: GNU Arm Embedded Toolchain (`arm-none-eabi-gcc`)
- **Flashing Utility**: STM32CubeProgrammer CLI (`STM32_Programmer_CLI`)
- **Python Environment**: Python 3.9+ with `fastapi`, `uvicorn`, and `pyserial` dependencies.

---

## How to Build & Run

### 1. Building the Embedded Code Manually

1. Navigate to the project folder:
   ```bash
   cd codes/ProjectContextAwareScheduling
   ```
2. Generate the build files (using the Release preset, specifying the active scheduler e.g., `CONTEXT_AWARE`, `EDF`, or `NATIVE`):
   ```bash
   cmake --preset Release -DACTIVE_SCHEDULER=CONTEXT_AWARE
   ```
3. Build the binary:
   ```bash
   cmake --build --preset Release
   ```
   The compiled `.elf` and `.hex` binaries will be located in the `build/Release` directory.

### 2. Running the Interactive Web GUI

The FastAPI GUI manages parameters, automates CMake builds, flashes the target board, and visualizes the results.

1. Navigate to the directory:
   ```bash
   cd codes/ProjectContextAwareScheduling
   ```
2. Launch the GUI server:
   ```bash
   python app/gui_server.py
   ```
3. Open your browser and navigate to `http://127.0.0.1:8000`.

### 3. Running Automated CLI Benchmarks

If you prefer to run the test suite and log UART outputs directly via the terminal:

```bash
python automate_schedulers.py --port COM4 --baud 115200 --duration 30
```
This script will sequentially configure, build, flash, and record telemetry logs for the `NATIVE`, `EDF`, and `CONTEXT_AWARE` schedulers in `logs/auto_tests/`.

### 4. Running the Offline ACO Solver CLI

To run the offline mathematical simulation and solver without hardware:

```bash
python -m offline_aco_baseline.main
```
