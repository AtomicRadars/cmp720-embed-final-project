#ifndef SCHEDULER_TEST_H
#define SCHEDULER_TEST_H

#include "core/IScheduler.h"
#include <stdint.h>

// Nominal utilization: 0.20+0.10+0.15+0.20 = 65% total
// Contention penalty (+30ms on Crypto/Vision) can push effective U up to ~85%
// EDF suffers the penalty (Vision->Crypto back-to-back);
// CAS avoids it by inserting Sensor between them.
constexpr uint32_t TASK1_HEAVY_WORKLOAD_MS = (TASK1_PERIOD_MS * 20) / 100; // 20% -> 2ms
constexpr uint32_t TASK2_HEAVY_WORKLOAD_MS = (TASK2_PERIOD_MS * 10) / 100; // 10% -> 5ms
constexpr uint32_t TASK3_HEAVY_WORKLOAD_MS = (TASK3_PERIOD_MS * 15) / 100; // 15% -> 75ms
constexpr uint32_t TASK4_HEAVY_WORKLOAD_MS = (TASK4_PERIOD_MS * 20) / 100; // 20% -> 4ms

// Simulates cache-pollution penalty: when a high-memory task runs right after another,
// its effective WCET is inflated (represents real STM32 D-cache thrashing).
constexpr uint32_t CONTENTION_PENALTY_MS    = 30;  // Extra ms when running after M>0.5 task
constexpr float    CONTENTION_THRESHOLD     = 0.5f;

constexpr uint32_t TASK1_PID_ITERATIONS   = 50;  // Extra PID compute passes per activation
constexpr uint32_t TASK3_CRYPTO_PASSES    = 3;   // Number of full-buffer passes per activation
constexpr uint32_t TASK4_VISION_PASSES    = 2;   // Number of full-buffer passes per activation

class SchedulerTest 
{
    public:
        // Safely formats and prints the Deadline Miss Ratio for a given task via UART
        static void PrintTaskMetrics(IScheduler* p_pISched, ETaskID task_id);
        
        // Burns CPU cycles for the given duration (no yielding, real CPU pressure)
        static void SimulateHeavyWorkload(uint32_t duration_ms);

        // Simulates a physical motor responding to PID control output
        static void UpdateMotorPlant(float control_output, float& setpoint, float& measured_value);

        // Simulates an ADC reading with pseudo-random drift and noise
        static uint16_t ReadSensorADC();
};

#endif // SCHEDULER_TEST_H
