#ifndef TASK_CONFIG_H
#define TASK_CONFIG_H

#include <cstddef>
#include <cstdint>

#include "FreeRTOS.h"
#include "task.h"

constexpr uint8_t TASK_COUNT = 3;

enum ETaskID : uint8_t
{
    eMotorControl = 0,
    eSensorAcquisition = 1,
    eCryptoEncryption = 2
};

struct TaskStruct
{
    TaskHandle_t handle;
    TickType_t deadline;
    uint32_t period;
    bool is_registered;
    uint32_t total_jobs;
    uint32_t missed_deadlines;
    uint32_t wcet;
    float memory_intensity;
    TickType_t next_wake_time;
};

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

constexpr uint32_t TASK1_PERIOD_MS = 10;  // High frequency
constexpr uint32_t TASK2_PERIOD_MS = 50;  // Medium frequency
constexpr uint32_t TASK3_PERIOD_MS = 500;  // Low frequency

class IScheduler;

class TaskConfig 
{
    public:
        TaskConfig(IScheduler* p_pIScheduler);

        static void Task1_MotorControl(void *pvParameters);
        static void Task2_SensorAcquisition(void *pvParameters);
        static void Task3_CryptoEncryption(void *pvParameters);

        bool CreateTasks();

        static void DWT_Init(); 

    private:
        IScheduler* m_pScheduler;
        
        // Task Handles
        TaskHandle_t m_xTask1Handle;
        TaskHandle_t m_xTask2Handle;
        TaskHandle_t m_xTask3Handle;
};

#endif // TASK_CONFIG_H