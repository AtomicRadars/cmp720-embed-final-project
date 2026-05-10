#include "core/TaskConfig.h"
#include "core/IScheduler.h"
#include "main.h"

#include <cstring>

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
    float error = 0.0f, integral = 0.0f, derivative = 0.0f, previous_error = 0.0f;
    const float Kp = 1.0f, Ki = 0.1f, Kd = 0.05f;

    while (true) 
    {
        // Computation-dominant floating-point updates [1]
        error = setpoint - measured_value;
        integral += error;
        derivative = error - previous_error;
        
        float output = (Kp * error) + (Ki * integral) + (Kd * derivative);
        previous_error = error;

        // Ensure synchronous periodic releases [5]
        const char* cpMsg = "Task1_MotorControl!\r\n";
	    HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);

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
        raw_adc_value = 1;//Read_ADC_Channel(); 
        
        // Simple filter used by the control pipeline [2]
        filtered_value = (filtered_value * 3 + raw_adc_value) / 4;

        const char* cpMsg = "Task2_SensorAcquisition!\r\n";
	    HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);

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
        // Emulate matrix-style operations and AES-like transformations [1]
        for (size_t i = 0; i < CRYPTO_BUFFER_SIZE; i++) 
        {
            crypto_buffer[i] = crypto_buffer[i] ^ 0xAA; 
            if (i > 0) 
            {
                crypto_buffer[i] += crypto_buffer[i-1]; 
            }
        }

        const char* cpMsg = "Task3_CryptoEncryption!\r\n";
	    HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);

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
        m_pScheduler->RegisterTask(ETaskID::eMotorControl, m_xTask1Handle, TASK1_PERIOD_MS);
        m_pScheduler->RegisterTask(ETaskID::eSensorAcquisition, m_xTask2Handle, TASK2_PERIOD_MS);
        m_pScheduler->RegisterTask(ETaskID::eCryptoEncryption, m_xTask3Handle, TASK3_PERIOD_MS);
        
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