#include "core/EDFScheduler.h"

void EDFScheduler::Initialize() 
{
    for (int i = 0; i < TASK_COUNT; ++i) 
    {
        tasks[i].is_registered = false;
    }
}

void EDFScheduler::RegisterTask(ETaskID task_id, TaskHandle_t handle, uint32_t period) 
{
    uint8_t id = static_cast<uint8_t>(task_id);
    if (id < TASK_COUNT) 
    {
        tasks[id].handle = handle;
        tasks[id].period = period;
        // Initial deadline is the first period
        tasks[id].deadline = period;
        tasks[id].is_registered = true;
    }
}

void EDFScheduler::UpdatePriorities() 
{
    // Sort registered tasks by deadline
    uint8_t indices[TASK_COUNT];
    uint8_t count = 0;
    
    for (uint8_t i = 0; i < TASK_COUNT; ++i) 
    {
        if (tasks[i].is_registered) 
        {
            indices[count++] = i;
        }
    }

    // Simple bubble sort for deadlines (earliest first)
    for (uint8_t i = 0; i < count; ++i) 
    {
        for (uint8_t j = 0; j < count - i - 1; ++j) 
        {
            if ((int32_t)(tasks[indices[j]].deadline - tasks[indices[j+1]].deadline) > 0) 
            {
                uint8_t temp = indices[j];
                indices[j] = indices[j+1];
                indices[j+1] = temp;
            }
        }
    }

    // Assign FreeRTOS priorities.
    // The task with the earliest deadline gets the highest priority.
    // We map deadlines to priorities: count, count - 1, ..., 1
    // (e.g. for 3 tasks: 3, 2, 1)
    UBaseType_t current_priority = count;
    for (uint8_t i = 0; i < count; ++i) 
    {
        uint8_t task_idx = indices[i];
        vTaskPrioritySet(tasks[task_idx].handle, current_priority);
        current_priority--;
    }
}

void EDFScheduler::DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) 
{
    uint8_t id = static_cast<uint8_t>(task_id);
    if (id < TASK_COUNT && tasks[id].is_registered) 
    {
        TickType_t next_wake_time = *pxPreviousWakeTime + xTimeIncrement;
        
        vTaskSuspendAll(); // Disable context switches during priority calculation
        
        // The new absolute deadline is the next wake time + relative deadline (which is the period)
        tasks[id].deadline = next_wake_time + tasks[id].period;
        
        UpdatePriorities();
        
        xTaskResumeAll(); // Re-enable context switches (preemption may happen here)
    }
    
    // Fall back to normal FreeRTOS blocking call
    vTaskDelayUntil(pxPreviousWakeTime, xTimeIncrement);
}
