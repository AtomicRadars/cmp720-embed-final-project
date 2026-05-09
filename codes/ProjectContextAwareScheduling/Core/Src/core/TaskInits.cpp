#include "core/TaskInits.h"

#include "FreeRTOS.h"
#include "task.h"

extern float Read_ADC_Channel(); // Hardware abstraction

/**
 * Task 1 (τ1): Motor Control 
 * Profile: Low Memory Intensity, high-frequency, computation-bound [2].
 */
void Task1_MotorControl(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(10); // High frequency

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
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

/**
 * Task 2 (τ2): Sensor Data Acquisition 
 * Profile: Low Memory Intensity, periodic ADC sampling/filtering [2].
 */
void Task2_SensorAcquisition(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(50); 

    uint16_t raw_adc_value = 0;
    uint16_t filtered_value = 0;

    while (true) 
    {
        raw_adc_value = Read_ADC_Channel(); 
        
        // Simple filter used by the control pipeline [2]
        filtered_value = (filtered_value * 3 + raw_adc_value) / 4;

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

/**
 * Task 3 (τ3): Cryptographic Encryption 
 * Profile: High Memory Intensity, lower-frequency, heavy shared memory access [2].
 */
void Task3_CryptoEncryption(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(200); 

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

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}