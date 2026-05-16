#include "core/EDFScheduler.h"

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
    if ((task_id < TASK_COUNT) && tasks[task_id].is_registered) 
    {
        TickType_t current_time = xTaskGetTickCount();
        TickType_t absolute_deadline = *pxPreviousWakeTime + xTimeIncrement;
        
        tasks[task_id].total_jobs++;

        // If current time is strictly greater than the absolute deadline, it's a miss
        if ((int32_t)(current_time - absolute_deadline) > 0)
        {
            tasks[task_id].missed_deadlines++;
        }

        TickType_t next_wake_time = absolute_deadline;
        tasks[task_id].next_wake_time = next_wake_time;
        
        vTaskSuspendAll(); // Disable context switches during priority calculation
        
        // The new absolute deadline is the next wake time + relative deadline (which is the period)
        tasks[task_id].deadline = next_wake_time + tasks[task_id].period;
        m_last_executed_task = task_id; // Track for contention model
        
        UpdatePriorities();
        
        xTaskResumeAll(); // Re-enable context switches (preemption may happen here)
    }

    
    // Fall back to normal FreeRTOS blocking call
    vTaskDelayUntil(pxPreviousWakeTime, xTimeIncrement);
}

const char* EDFScheduler::GetSchedulerName() const
{
    return "EDF Scheduler";
}
