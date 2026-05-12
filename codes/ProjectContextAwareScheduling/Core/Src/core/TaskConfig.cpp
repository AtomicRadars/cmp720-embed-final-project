#include "core/TaskConfig.h"
#include "core/IScheduler.h"
#include "main.h"
#include "test/SchedulerTest.h"

#include <cstring>
#include <cstdio>

// Task prototypes for FreeRTOS tasks, defined in TaskInits.cpp
extern UART_HandleTypeDef huart2;
//extern float Read_ADC_Channel(); // Hardware abstraction

TaskConfig::TaskConfig(IScheduler* p_pIScheduler) : m_pScheduler(p_pIScheduler) 
{
    m_xTask1Handle = nullptr;
    m_xTask2Handle = nullptr;
    m_xTask3Handle = nullptr;
}

void TaskConfig::Task1_MotorControl(void *pvParameters) 
{
    IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(TASK1_PERIOD_MS); // High frequency

    float setpoint = 100.0f;
    float measured_value = 0.0f;
    float output = 0.0f;
    float error = 0.0f, integral = 0.0f, derivative = 0.0f, previous_error = 0.0f;
    const float Kp = 1.0f, Ki = 0.1f, Kd = 0.05f;

    while (true) 
    {
        // Read simulated real-world motor parameters
        SchedulerTest::UpdateMotorPlant(output, setpoint, measured_value);

        // Computation-dominant floating-point updates [1]
        error = setpoint - measured_value;
        integral += error;
        derivative = error - previous_error;
        
        output = (Kp * error) + (Ki * integral) + (Kd * derivative);
        previous_error = error;

        // Strategy 1: Extra PID iterations (compute-bound, matching τ1 profile)
        for (uint32_t iter = 0; iter < TASK1_PID_ITERATIONS; iter++)
        {
            error = setpoint - measured_value;
            integral += error;
            derivative = error - previous_error;
            output = (Kp * error) + (Ki * integral) + (Kd * derivative);
            previous_error = error;
        }

        // Strategy 2: Busy-spin to fill remaining period budget
        SchedulerTest::SimulateHeavyWorkload(TASK1_HEAVY_WORKLOAD_MS);

        // Ensure synchronous periodic releases [5]
        if (pSched->GetTotalJobs(ETaskID::eMotorControl) % (1000 / TASK1_PERIOD_MS) == 0) 
        {
            char msg[128];
            snprintf(msg, sizeof(msg), "\r\nTask1_MotorControl! SP: 100, MV: %d (x1000), OUT: %d (x1000)\r\n", 
                     static_cast<int>(measured_value * 1000.0f), static_cast<int>(output * 1000.0f));
            HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
        }

        // Print testing telemetry
        SchedulerTest::PrintTaskMetrics(pSched, ETaskID::eMotorControl);

        pSched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eMotorControl);
    }
}

/**
 * Task 2 (τ2): Sensor Data Acquisition 
 * Profile: Low Memory Intensity, periodic ADC sampling/filtering [2].
 */
void TaskConfig::Task2_SensorAcquisition(void *pvParameters) 
{
    IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(TASK2_PERIOD_MS); 

    uint16_t raw_adc_value = 0;
    uint16_t filtered_value = 0;

    while (true) 
    {
        raw_adc_value = SchedulerTest::ReadSensorADC(); 
        
        // Simple filter used by the control pipeline [2]
        filtered_value = (filtered_value * 3 + raw_adc_value) / 4;

        // Strategy 2: Busy-spin to fill remaining period budget
        SchedulerTest::SimulateHeavyWorkload(TASK2_HEAVY_WORKLOAD_MS);

        if (pSched->GetTotalJobs(ETaskID::eSensorAcquisition) % (1000 / TASK2_PERIOD_MS) == 0) 
        {
            char msg[128];
            snprintf(msg, sizeof(msg), "Task2_SensorAcquisition! RAW: %u, FILTERED: %u\r\n", 
                     raw_adc_value, filtered_value);
            HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
        }

        // Print testing telemetry
        SchedulerTest::PrintTaskMetrics(pSched, ETaskID::eSensorAcquisition);

        pSched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eSensorAcquisition);
    }
}

/**
 * Task 3 (τ3): Cryptographic Encryption 
 * Profile: High Memory Intensity, lower-frequency, heavy shared memory access [2].
 */
void TaskConfig::Task3_CryptoEncryption(void *pvParameters) 
{
    IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(TASK3_PERIOD_MS); 

    while (true) 
    {
        // Strategy 1: Multiple passes over the crypto buffer (memory-bound, matching τ3 profile)
        for (uint32_t pass = 0; pass < TASK3_CRYPTO_PASSES; pass++)
        {
            for (size_t i = 0; i < CRYPTO_BUFFER_SIZE; i++) 
            {
                crypto_buffer[i] = crypto_buffer[i] ^ 0xAA; 
                if (i > 0) 
                {
                    crypto_buffer[i] += crypto_buffer[i-1]; 
                }
            }
        }

        // Strategy 2: Busy-spin to fill remaining period budget
        SchedulerTest::SimulateHeavyWorkload(TASK3_HEAVY_WORKLOAD_MS);

        if (pSched->GetTotalJobs(ETaskID::eCryptoEncryption) % (1000 / TASK3_PERIOD_MS) == 0) 
        {
            const char* cpMsg = "Task3_CryptoEncryption!\r\n";
            HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);
        }

        // Print testing telemetry
        SchedulerTest::PrintTaskMetrics(pSched, ETaskID::eCryptoEncryption);

        pSched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eCryptoEncryption);
    }
}

bool TaskConfig::CreateTasks()
{
    // Task 1: Motor Control (High frequency, Low memory)
    m_xTask1Handle = xTaskCreateStatic(
        Task1_MotorControl, "MotorCtrl", STACK_SIZE, m_pScheduler, 3, xTask1Stack, &xTask1TCB
    );

    // Task 2: Sensor Data Acquisition (Medium frequency, Low memory)
    m_xTask2Handle = xTaskCreateStatic(
        Task2_SensorAcquisition, "SensorAcq", STACK_SIZE, m_pScheduler, 2, xTask2Stack, &xTask2TCB
    );

    // Task 3: Cryptographic Encryption (Low frequency, High memory)
    m_xTask3Handle = xTaskCreateStatic(
        Task3_CryptoEncryption, "CryptoEnc", STACK_SIZE, m_pScheduler, 1, xTask3Stack, &xTask3TCB
    );

    if ((m_xTask1Handle != nullptr) && (m_xTask2Handle != nullptr) && (m_xTask3Handle != nullptr)) 
    {
        m_pScheduler->Initialize();
        m_pScheduler->RegisterTask(ETaskID::eMotorControl, m_xTask1Handle, TASK1_PERIOD_MS, TASK1_HEAVY_WORKLOAD_MS, 0.1f);
        m_pScheduler->RegisterTask(ETaskID::eSensorAcquisition, m_xTask2Handle, TASK2_PERIOD_MS, TASK2_HEAVY_WORKLOAD_MS, 0.2f);
        m_pScheduler->RegisterTask(ETaskID::eCryptoEncryption, m_xTask3Handle, TASK3_PERIOD_MS, TASK3_HEAVY_WORKLOAD_MS, 0.9f);
        
        return true;
    }

    return false;
}

// DWT (Data Watchpoint and Trace) initialization for cycle counting
void TaskConfig::DWT_Init(void) 
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}