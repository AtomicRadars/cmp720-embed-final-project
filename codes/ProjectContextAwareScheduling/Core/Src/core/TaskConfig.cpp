#include "core/TaskConfig.h"
#include "core/IScheduler.h"
#include "main.h"
#include "projdefs.h"
#include "test/SchedulerTest.h"

#include <cstring>
#include <cstdio>


StaticTask_t xTask1TCB{};
StaticTask_t xTask2TCB{};
StaticTask_t xTask3TCB{};
StaticTask_t xTask4TCB{};

StackType_t xTask1Stack[TASK_STACK_SIZE]{};
StackType_t xTask2Stack[TASK_STACK_SIZE]{};
StackType_t xTask3Stack[TASK_STACK_SIZE]{};
StackType_t xTask4Stack[TASK_STACK_SIZE]{};

uint8_t crypto_buffer[CRYPTO_BUFFER_SIZE]{};
uint8_t vision_buffer[VISION_BUFFER_SIZE]{};

// Task prototypes for FreeRTOS tasks, defined in TaskInits.cpp
extern UART_HandleTypeDef huart2;
//extern float Read_ADC_Channel(); // Hardware abstraction

TaskConfig::TaskConfig(IScheduler* p_pIScheduler) : m_pIScheduler(p_pIScheduler) 
{
    m_xTask1Handle = nullptr;
    m_xTask2Handle = nullptr;
    m_xTask3Handle = nullptr;
    m_xTask4Handle = nullptr;
}

void TaskConfig::Task1_MotorControl(IScheduler* p_pISched) 
{
    //IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
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
        if (p_pISched->GetTotalJobs(ETaskID::eMotorControl) % (1000 / TASK1_PERIOD_MS) == 0) 
        {
            char msg[128];
            snprintf(msg, sizeof(msg), "\r\nTask1_MotorControl! SP: 100, MV: %d (x1000), OUT: %d (x1000)\r\n", 
                     static_cast<int>(measured_value * 1000.0f), static_cast<int>(output * 1000.0f));
            HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
        }

        // Print testing telemetry
        SchedulerTest::PrintTaskMetrics(p_pISched, ETaskID::eMotorControl);

        p_pISched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eMotorControl);
    }
}

/**
 * Task 2 (τ2): Sensor Data Acquisition 
 * Profile: Low Memory Intensity, periodic ADC sampling/filtering [2].
 */
void TaskConfig::Task2_SensorAcquisition(IScheduler* p_pISched) 
{
    //IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
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

        if (p_pISched->GetTotalJobs(ETaskID::eSensorAcquisition) % (1000 / TASK2_PERIOD_MS) == 0) 
        {
            char msg[128];
            snprintf(msg, sizeof(msg), "Task2_SensorAcquisition! RAW: %u, FILTERED: %u\r\n", 
                     raw_adc_value, filtered_value);
            HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
        }

        // Print testing telemetry
        SchedulerTest::PrintTaskMetrics(p_pISched, ETaskID::eSensorAcquisition);

        p_pISched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eSensorAcquisition);
    }
}

/**
 * Task 3 (τ3): Cryptographic Encryption 
 * Profile: High Memory Intensity, lower-frequency, heavy shared memory access [2].
 */
void TaskConfig::Task3_CryptoEncryption(IScheduler* p_pISched) 
{
    //IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(TASK3_PERIOD_MS); 

    while (true) 
    {
        // Cache-contention model: if the previous task was memory-intensive, our
        // 8 KB crypto_buffer working set was evicted from the STM32 D-cache.
        // We simulate this with an explicit penalty, representing real cache-miss overhead.
        if (p_pISched->GetLastExecutedMemoryIntensity() > CONTENTION_THRESHOLD)
        {
            SchedulerTest::SimulateHeavyWorkload(CONTENTION_PENALTY_MS);
        }

        // Multiple passes over the crypto buffer (memory-bound)
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

        SchedulerTest::SimulateHeavyWorkload(TASK3_HEAVY_WORKLOAD_MS);

        if (p_pISched->GetTotalJobs(ETaskID::eCryptoEncryption) % (1000 / TASK3_PERIOD_MS) == 0) 
        {
            const char* cpMsg = "Task3_CryptoEncryption!\r\n";
            HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);
        }

        SchedulerTest::PrintTaskMetrics(p_pISched, ETaskID::eCryptoEncryption);

        p_pISched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eCryptoEncryption);
    }
}

/**
 * Task 4 (τ4): Vision Processing 
 * Profile: High Memory Intensity, short period.
 */
void TaskConfig::Task4_VisionProcessing(IScheduler* p_pISched) 
{
    //IScheduler* pSched = static_cast<IScheduler*>(pvParameters);
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(TASK4_PERIOD_MS); 

    while (true) 
    {
        // Cache-contention model: if the previous task was memory-intensive,
        // our 4 KB vision_buffer working set was evicted from the D-cache.
        if (p_pISched->GetLastExecutedMemoryIntensity() > CONTENTION_THRESHOLD)
        {
            SchedulerTest::SimulateHeavyWorkload(CONTENTION_PENALTY_MS);
        }

        for (uint32_t pass = 0; pass < TASK4_VISION_PASSES; pass++)
        {
            for (size_t i = 0; i < VISION_BUFFER_SIZE; i++) 
            {
                vision_buffer[i] = vision_buffer[i] ^ 0x55; 
                if (i > 0) 
                {
                    vision_buffer[i] += vision_buffer[i-1]; 
                }
            }
        }

        SchedulerTest::SimulateHeavyWorkload(TASK4_HEAVY_WORKLOAD_MS);

        if (p_pISched->GetTotalJobs(ETaskID::eVisionProcessing) % (1000 / TASK4_PERIOD_MS) == 0) 
        {
            const char* cpMsg = "Task4_VisionProcessing!\r\n";
            HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);
        }

        SchedulerTest::PrintTaskMetrics(p_pISched, ETaskID::eVisionProcessing);

        p_pISched->DelayUntil(&xLastWakeTime, xFrequency, ETaskID::eVisionProcessing);
    }
}

bool TaskConfig::CreateTasks()
{
    // Task 1: Motor Control (High frequency, Low memory)
    m_xTask1Handle = xTaskCreateStatic(
        (TaskFunction_t)Task1_MotorControl, "MotorCtrl", TASK_STACK_SIZE, m_pIScheduler, TASK1_PRIORITY, xTask1Stack, &xTask1TCB
    );

    // Task 2: Sensor Data Acquisition (Medium frequency, Low memory)
    m_xTask2Handle = xTaskCreateStatic(
        (TaskFunction_t)Task2_SensorAcquisition, "SensorAcq", TASK_STACK_SIZE, m_pIScheduler, TASK2_PRIORITY, xTask2Stack, &xTask2TCB
    );

    // Task 3: Cryptographic Encryption (Low frequency, High memory)
    m_xTask3Handle = xTaskCreateStatic(
        (TaskFunction_t)Task3_CryptoEncryption, "CryptoEnc", TASK_STACK_SIZE, m_pIScheduler, TASK3_PRIORITY, xTask3Stack, &xTask3TCB
    );

    // Task 4: Vision Processing (Medium frequency, High memory)
    m_xTask4Handle = xTaskCreateStatic(
        (TaskFunction_t)Task4_VisionProcessing, "VisionProc", TASK_STACK_SIZE, m_pIScheduler, TASK4_PRIORITY, xTask4Stack, &xTask4TCB
    );

    if ((m_xTask1Handle != nullptr) && (m_xTask2Handle != nullptr) && (m_xTask3Handle != nullptr) && (m_xTask4Handle != nullptr)) 
    {
        m_pIScheduler->Initialize();
        m_pIScheduler->RegisterTask(ETaskID::eMotorControl, m_xTask1Handle, TASK1_PERIOD_MS, TASK1_HEAVY_WORKLOAD_MS, TASK1_MEMORY_INTENSITY);
        m_pIScheduler->RegisterTask(ETaskID::eSensorAcquisition, m_xTask2Handle, TASK2_PERIOD_MS, TASK2_HEAVY_WORKLOAD_MS, TASK2_MEMORY_INTENSITY);
        m_pIScheduler->RegisterTask(ETaskID::eCryptoEncryption, m_xTask3Handle, TASK3_PERIOD_MS, TASK3_HEAVY_WORKLOAD_MS, TASK3_MEMORY_INTENSITY);
        m_pIScheduler->RegisterTask(ETaskID::eVisionProcessing, m_xTask4Handle, TASK4_PERIOD_MS, TASK4_HEAVY_WORKLOAD_MS, TASK4_MEMORY_INTENSITY);

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