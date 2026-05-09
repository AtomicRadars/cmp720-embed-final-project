# CMP720 Project: Context-Aware Deadline Scheduling Under Memory Contention for Embedded Real-Time Systems

This repository contains the source code and documentation for the CMP720 final project. The project focuses on exploring and implementing context-aware deadline scheduling techniques in the presence of memory contention for embedded real-time systems using an STM32 microcontroller and FreeRTOS.

## Project Structure

- `codes/`: Contains the main source code for the embedded application (`ProjectContextAwareScheduling`).
- `docs/`: Contains the project documentation, including the initial proposal, extended proposal, and midterm presentation materials.

## Embedded Software Architecture

The system is built on **FreeRTOS** and targets the **STM32L452XX** microcontroller. It is designed to emulate a mixed-criticality workload environment to study task scheduling and memory contention. 

Hardware profiling and cycle counting are facilitated using the **ARM DWT (Data Watchpoint and Trace)** counter.

### Task Profiles

The RTOS is configured with three distinct tasks to simulate different real-world embedded operations:

1. **Task 1: Motor Control (τ1)**
   - **Profile**: High frequency, Low memory intensity, High priority.
   - **Description**: Computation-dominant task that emulates a PID control loop (floating-point updates) for motor control.

2. **Task 2: Sensor Data Acquisition (τ2)**
   - **Profile**: Medium frequency, Low memory intensity, Medium priority.
   - **Description**: Emulates periodic ADC sampling and simple filtering operations for a control pipeline.

3. **Task 3: Cryptographic Encryption (τ3)**
   - **Profile**: Low frequency, High memory intensity, Low priority.
   - **Description**: Memory-bound task that emulates matrix-style operations and AES-like cryptographic transformations, generating significant memory traffic and contention.

## Hardware and Toolchain

- **Target MCU**: STM32L452XX Series
- **RTOS**: FreeRTOS
- **Build System**: CMake (requires version 3.22 or higher)
- **Languages**: C11, C++17
- **Initialization Tool**: STM32CubeMX

## Building the Project

The project uses CMake for dependency management and building.

1. Navigate to the project directory:
   ```bash
   cd codes/ProjectContextAwareScheduling
   ```

2. Create a build directory and run CMake:
   ```bash
   mkdir build
   cd build
   cmake ..
   ```

3. Build the project:
   ```bash
   cmake --build .
   ```

The compiled binary and executable files will be generated in the `build` directory, ready to be flashed onto the STM32 board.
