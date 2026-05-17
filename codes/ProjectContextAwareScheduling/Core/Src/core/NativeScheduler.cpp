#include "core/NativeScheduler.h"
#include "test/SchedulerTest.h"

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

        // 1. Response-time Jitter using Welford's Algorithm
        float response_time = static_cast<float>(current_time - *pxPreviousWakeTime);
        m_jitter_count[task_id]++;
        float delta = response_time - m_jitter_mean[task_id];
        m_jitter_mean[task_id] += delta / m_jitter_count[task_id];
        float delta2 = response_time - m_jitter_mean[task_id];
        m_jitter_m2[task_id] += delta * delta2;

        // 2. Cache Contention Penalty tracking
        if (task_id == eCryptoEncryption || task_id == eVisionProcessing)
        {
            if (tasks[m_last_executed_task].memory_intensity > CONTENTION_THRESHOLD)
            {
                m_total_contention_penalty_ms += CONTENTION_PENALTY_MS;
            }
        }

        // We DO NOT update the absolute deadline or update task priorities here
        // like we do in EDFScheduler. We just fall back to native FreeRTOS
        // vTaskDelayUntil which manages waking the task at the exact right tick.
        tasks[task_id].next_wake_time = absolute_deadline;
        m_last_executed_task = task_id;
        
        m_overhead_call_count++; // Native RM has 0 cycles decision overhead
    }
    
    // Native FreeRTOS blocking call (Task retains its static priority)
    vTaskDelayUntil(pxPreviousWakeTime, xTimeIncrement);
}

const char* NativeScheduler::GetSchedulerName() const
{
    return "Native RMS Scheduler";
}
