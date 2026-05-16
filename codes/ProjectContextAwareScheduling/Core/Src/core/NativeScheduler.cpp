#include "core/NativeScheduler.h"

void NativeScheduler::DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) 
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

        // We DO NOT update the absolute deadline or update task priorities here
        // like we do in EDFScheduler. We just fall back to native FreeRTOS
        // vTaskDelayUntil which manages waking the task at the exact right tick.
        tasks[task_id].next_wake_time = absolute_deadline;
        m_last_executed_task = task_id;
    }
    
    // Native FreeRTOS blocking call (Task retains its static priority)
    vTaskDelayUntil(pxPreviousWakeTime, xTimeIncrement);
}

const char* NativeScheduler::GetSchedulerName() const
{
    return "Native RMS Scheduler";
}
