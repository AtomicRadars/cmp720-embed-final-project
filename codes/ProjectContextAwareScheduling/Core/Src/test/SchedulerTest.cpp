#include "test/SchedulerTest.h"
#include "core/TaskConfig.h"
#include "main.h" // For HAL_UART_Transmit and HAL_Delay
#include <cstdio>
#include <cstring>

extern UART_HandleTypeDef huart2;

void SchedulerTest::PrintTaskMetrics(IScheduler* p_pISched, ETaskID task_id)
{
    if (p_pISched == nullptr)
    {
        return;
    }

    uint32_t total = p_pISched->GetTotalJobs(task_id);
    
    // Determine print interval based on task to achieve ~1 sec interval
    uint32_t print_interval = 1;
    switch (task_id) 
    {
        case ETaskID::eMotorControl: 
            print_interval = 1000 / TASK1_PERIOD_MS; 
            break;
        case ETaskID::eSensorAcquisition: 
            print_interval = 1000 / TASK2_PERIOD_MS; 
            break;
        case ETaskID::eCryptoEncryption: 
            print_interval = 1000 / TASK3_PERIOD_MS; 
            break;
        case ETaskID::eVisionProcessing:
            print_interval = 1000 / TASK4_PERIOD_MS;
            break;
        default: 
            print_interval = 5; 
            break;
    }

    if (((total > 0) && ((total % print_interval) == 0)) 
    {
        char msg[128];
        uint32_t misses = p_pISched->GetMissedDeadlines(task_id);
        float dmr = p_pISched->GetDeadlineMissRatio(task_id);
        UBaseType_t priority = uxTaskPriorityGet(nullptr); // Priority of the calling task
        
        snprintf(msg, sizeof(msg), "[TS: %lu ms] [Metrics] Task %d - Prio: %lu | Jobs: %lu | Misses: %lu | DMR: %d%%\r\n", 
                 xTaskGetTickCount(), static_cast<int>(task_id), static_cast<uint32_t>(priority), total, misses, static_cast<int>(dmr * 100.0f));
                 
        HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
    }
}

void SchedulerTest::SimulateHeavyWorkload(uint32_t duration_ms)
{
    // Busy-spin using a calibrated instruction loop. 
    // This ensures the task demands TRUE CPU execution time, rather than 
    // just wall-clock time (which would allow preempted tasks to "finish" early).
    // Assuming 80 MHz core clock.
    // A volatile loop on Cortex-M4 with flash wait states typically takes 15-20 cycles.
    // 80,000 cycles per ms / 20 cycles per loop = ~4,000 iterations per millisecond.
    uint32_t total_iterations = duration_ms * 4000;
    volatile uint32_t sink = 0;
    for (uint32_t i = 0; i < total_iterations; i++)
    {
        sink++; // Prevent optimizer from removing the loop
    }
}

void SchedulerTest::UpdateMotorPlant(float control_output, float& setpoint, float& measured_value)
{
    // The setpoint remains constant at 100 RPM for this simulation
    setpoint = 100.0f;
    
    // Simulate motor inertia: the measured value approaches the setpoint based on the control output
    measured_value += control_output * 0.05f;
    
    // Add some pseudo-random noise to simulate real-world sensor readings
    // Use a prime modulo (101) to avoid aliasing with the 1000ms print period
    uint32_t tick = xTaskGetTickCount();
    float noise = (static_cast<int32_t>(tick % 101) - 50) / 100.0f; 
    measured_value += noise;
}

uint16_t SchedulerTest::ReadSensorADC()
{
    uint32_t tick = xTaskGetTickCount();
    
    // Base 12-bit ADC value (2048) with slow drift (-1000 to 1000)
    // Use a prime modulo (1999) to avoid aliasing with the 1000ms print period
    int32_t drift = static_cast<int32_t>(tick % 1999) - 1000;
    
    // High frequency noise (-50 to 50)
    int32_t noise = static_cast<int32_t>(tick % 101) - 50;
    
    return static_cast<uint16_t>(2048 + drift + noise);
}
