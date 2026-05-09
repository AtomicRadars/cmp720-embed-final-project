#ifndef TASK_CONFIG_H
#define TASK_CONFIG_H

#include <cstddef>
#include <cstdint>

#include "FreeRTOS.h"
#include "task.h"

// --- STATIC ALLOCATION STRUCTURES ---
// Since dynamic allocation is avoided [2], we statically allocate memory 
// for the Task Control Blocks (TCBs) and the Task Stacks.
constexpr size_t STACK_SIZE = 256;

// TCBs (Task Control Blocks)
static StaticTask_t xTask1TCB{};
static StaticTask_t xTask2TCB{};
static StaticTask_t xTask3TCB{};

// Task Stacks
static StackType_t xTask1Stack[STACK_SIZE];
static StackType_t xTask2Stack[STACK_SIZE];
static StackType_t xTask3Stack[STACK_SIZE];

// Target constraint: Use a large contiguous buffer (4-10 KB) allocated 
// statically to avoid runtime dynamic allocation [3, 4].
constexpr size_t CRYPTO_BUFFER_SIZE = 8192; 
static uint8_t crypto_buffer[CRYPTO_BUFFER_SIZE];

constexpr uint32_t TASK1_PERIOD_MS = 1000;  // High frequency
constexpr uint32_t TASK2_PERIOD_MS = 2000;  // Medium frequency
constexpr uint32_t TASK3_PERIOD_MS = 3000;  // Low frequency

class TaskConfig 
{
    public:
        TaskConfig();

        static void Task1_MotorControl(void *pvParameters);
        static void Task2_SensorAcquisition(void *pvParameters);
        static void Task3_CryptoEncryption(void *pvParameters);

        bool CreateTasks();

        static void DWT_Init(); 

    private:
        // Task Handles
        TaskHandle_t xTask1Handle;
        TaskHandle_t xTask2Handle;
        TaskHandle_t xTask3Handle;
};

#endif // TASK_CONFIG_H