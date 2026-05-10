#include "test/SchedulerTest.h"
#include "core/TaskConfig.h"
#include "main.h" // For HAL_UART_Transmit and HAL_Delay
#include <cstdio>
#include <cstring>

extern UART_HandleTypeDef huart2;

void SchedulerTest::PrintTaskMetrics(IScheduler* pSched, ETaskID task_id)
{
    if (pSched == nullptr)
    {
        return;
    }

    uint32_t total = pSched->GetTotalJobs(task_id);
    
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
        default: 
            print_interval = 5; 
            break;
    }

    if (((total > 0) && (total % print_interval)) == 0) 
    {
        char msg[128];
        uint32_t misses = pSched->GetMissedDeadlines(task_id);
        float dmr = pSched->GetDeadlineMissRatio(task_id);
        
        snprintf(msg, sizeof(msg), "[Metrics] Task %d - Jobs: %lu | Misses: %lu | DMR: %d%%\r\n", 
                 static_cast<int>(task_id), total, misses, static_cast<int>(dmr * 100.0f));
                 
        HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
    }
}

void SchedulerTest::SimulateHeavyWorkload(uint32_t duration_ms)
{
    // Busy-spin: burns CPU cycles without yielding — causes real deadline pressure
    TickType_t start = xTaskGetTickCount();
    volatile uint32_t sink = 0;
    while ((xTaskGetTickCount() - start) < pdMS_TO_TICKS(duration_ms))
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
