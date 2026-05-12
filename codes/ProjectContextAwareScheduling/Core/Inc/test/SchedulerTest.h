#ifndef SCHEDULER_TEST_H
#define SCHEDULER_TEST_H

#include "core/IScheduler.h"
#include <stdint.h>

constexpr uint32_t TASK1_HEAVY_WORKLOAD_MS = (TASK1_PERIOD_MS * 30) / 100; // 30% Utilization
constexpr uint32_t TASK2_HEAVY_WORKLOAD_MS = (TASK2_PERIOD_MS * 20) / 100; // 20% Utilization
constexpr uint32_t TASK3_HEAVY_WORKLOAD_MS = (TASK3_PERIOD_MS * 40) / 100; // 40% Utilization

constexpr uint32_t TASK1_PID_ITERATIONS   = 50;  // Extra PID compute passes per activation
constexpr uint32_t TASK3_CRYPTO_PASSES    = 3;   // Number of full-buffer passes per activation

class SchedulerTest 
{
    public:
        // Safely formats and prints the Deadline Miss Ratio for a given task via UART
        static void PrintTaskMetrics(IScheduler* pSched, ETaskID task_id);
        
        // Burns CPU cycles for the given duration (no yielding, real CPU pressure)
        static void SimulateHeavyWorkload(uint32_t duration_ms);

        // Simulates a physical motor responding to PID control output
        static void UpdateMotorPlant(float control_output, float& setpoint, float& measured_value);

        // Simulates an ADC reading with pseudo-random drift and noise
        static uint16_t ReadSensorADC();
};

#endif // SCHEDULER_TEST_H
