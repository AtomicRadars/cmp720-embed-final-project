#ifndef TASK_CONFIG_H
#define TASK_CONFIG_H

#include <cstddef>
#include <cstdint>

#include "FreeRTOS.h"
#include "task.h"

enum ETaskID : uint8_t
{
    eMotorControl = 0,
    eSensorAcquisition = 1,
    eCryptoEncryption = 2,
    eVisionProcessing = 3,
    TASK_COUNT
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
constexpr size_t TASK_STACK_SIZE = 256;

// TCBs (Task Control Blocks)
static StaticTask_t xTask1TCB{};
static StaticTask_t xTask2TCB{};
static StaticTask_t xTask3TCB{};
static StaticTask_t xTask4TCB{};

// Task Stacks
static StackType_t xTask1Stack[TASK_STACK_SIZE];
static StackType_t xTask2Stack[TASK_STACK_SIZE];
static StackType_t xTask3Stack[TASK_STACK_SIZE];
static StackType_t xTask4Stack[TASK_STACK_SIZE];

// Target constraint: Use a large contiguous buffer (4-10 KB) allocated 
// statically to avoid runtime dynamic allocation [3, 4].
constexpr size_t CRYPTO_BUFFER_SIZE = 8192; 
static uint8_t crypto_buffer[CRYPTO_BUFFER_SIZE];

constexpr size_t VISION_BUFFER_SIZE = 4096;
static uint8_t vision_buffer[VISION_BUFFER_SIZE];

constexpr UBaseType_t TASK1_PRIORITY = 3;
constexpr UBaseType_t TASK2_PRIORITY = 2;
constexpr UBaseType_t TASK3_PRIORITY = 1;
constexpr UBaseType_t TASK4_PRIORITY = 2;

constexpr uint32_t TASK1_PERIOD_MS = 10;  // High frequency
constexpr uint32_t TASK2_PERIOD_MS = 50;  // Medium frequency
constexpr uint32_t TASK3_PERIOD_MS = 500; // Low frequency
constexpr uint32_t TASK4_PERIOD_MS = 20;  // High-Medium frequency

// Context-Aware Scheduling parameters
constexpr float     ALPHA                       = 1.0f;     // Weight for the heuristic penalty
constexpr uint32_t  SAFETY_MARGIN_MS            = 2;        // Safety margin in milliseconds for deadline slack
constexpr float     MEMORY_INTENSITY_THRESHOLD  = 0.15f;     // Threshold for memory-intensive tasks

constexpr float TASK1_MEMORY_INTENSITY = 0.1f;  // Low memory intensity
constexpr float TASK2_MEMORY_INTENSITY = 0.2f;  // Medium memory intensity
constexpr float TASK3_MEMORY_INTENSITY = 0.9f;  // High memory intensity
constexpr float TASK4_MEMORY_INTENSITY = 0.8f;  // High memory intensity

class IScheduler;

class TaskConfig 
{
    public:
        TaskConfig(IScheduler* p_pIScheduler);

        static void Task1_MotorControl(IScheduler* p_pISched);
        static void Task2_SensorAcquisition(IScheduler* p_pISched);
        static void Task3_CryptoEncryption(IScheduler* p_pISched);
        static void Task4_VisionProcessing(IScheduler* p_pISched);

        bool CreateTasks();

        static void DWT_Init(); 

    private:
        IScheduler* m_pIScheduler;
        
        // Task Handles
        TaskHandle_t m_xTask1Handle;
        TaskHandle_t m_xTask2Handle;
        TaskHandle_t m_xTask3Handle;
        TaskHandle_t m_xTask4Handle;
};

#endif // TASK_CONFIG_H