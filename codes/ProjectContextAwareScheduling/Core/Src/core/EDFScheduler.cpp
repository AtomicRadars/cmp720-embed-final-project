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
    if (task_id < TASK_COUNT) 
    {
        tasks[task_id].handle = handle;
        tasks[task_id].period = period;
        // Initial deadline is the first period
        tasks[task_id].deadline = period;
        tasks[task_id].is_registered = true;
        tasks[task_id].total_jobs = 0;
        tasks[task_id].missed_deadlines = 0;
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
        
        vTaskSuspendAll(); // Disable context switches during priority calculation
        
        // The new absolute deadline is the next wake time + relative deadline (which is the period)
        tasks[task_id].deadline = next_wake_time + tasks[task_id].period;
        
        UpdatePriorities();
        
        xTaskResumeAll(); // Re-enable context switches (preemption may happen here)
    }
    
    // Fall back to normal FreeRTOS blocking call
    vTaskDelayUntil(pxPreviousWakeTime, xTimeIncrement);
}

uint32_t EDFScheduler::GetTotalJobs(ETaskID task_id) const
{
    if ((task_id < TASK_COUNT) && (tasks[task_id].is_registered)) 
    {
        return tasks[task_id].total_jobs;
    }
    return 0;
}

uint32_t EDFScheduler::GetMissedDeadlines(ETaskID task_id) const
{
    if ((task_id < TASK_COUNT) && (tasks[task_id].is_registered)) 
    {
        return tasks[task_id].missed_deadlines;
    }
    return 0;
}

float EDFScheduler::GetDeadlineMissRatio(ETaskID task_id) const
{
    if ((task_id < TASK_COUNT) && (tasks[task_id].is_registered) && (tasks[task_id].total_jobs > 0)) 
    {
        return static_cast<float>(tasks[task_id].missed_deadlines) / static_cast<float>(tasks[task_id].total_jobs);
    }
    return 0.0f;
}
