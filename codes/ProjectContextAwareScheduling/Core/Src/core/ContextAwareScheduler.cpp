#include "core/ContextAwareScheduler.h"

ContextAwareScheduler::ContextAwareScheduler(float alpha, float threshold, uint32_t safety_margin)
    : m_alpha(alpha), m_threshold(threshold), m_safety_margin(safety_margin), m_last_executed_task(eMotorControl)
{
}

void ContextAwareScheduler::ApplyHeuristicAndUpdatePriorities() 
{
    TickType_t current_time = xTaskGetTickCount();
    
    // 1. Identify all registered tasks
    uint8_t indices[TASK_COUNT];
    uint8_t count = 0;
    
    for (uint8_t i = 0; i < TASK_COUNT; ++i) 
    {
        if (tasks[i].is_registered) 
        {
            indices[count++] = i;
        }
    }

    if (count == 0)
    {
        return;
    }

    // 2. Sort ALL tasks by absolute deadline (EDF base)
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

    // 3. Find the highest priority READY task
    int8_t cand_ready_idx = -1;
    for (uint8_t i = 0; i < count; ++i) 
    {
        if ((int32_t)(current_time - tasks[indices[i]].next_wake_time) >= 0)
        {
            cand_ready_idx = i;
            break;
        }
    }

    // 4. Apply heuristic
    if (cand_ready_idx != -1)
    {
        uint8_t cand_task_id = indices[cand_ready_idx];
        float m_curr = tasks[m_last_executed_task].memory_intensity;
        float m_cand = tasks[cand_task_id].memory_intensity;
        float penalty = m_alpha * m_curr * m_cand;
        
        if (penalty > m_threshold)
        {
            int32_t slack = (int32_t)(tasks[cand_task_id].deadline - current_time) - (int32_t)tasks[cand_task_id].wcet;
            if (slack > (int32_t)m_safety_margin)
            {
                // Find T_alt (a lower priority ready task)
                for (uint8_t i = cand_ready_idx + 1; i < count; ++i)
                {
                    uint8_t alt_task_id = indices[i];
                    if ((int32_t)(current_time - tasks[alt_task_id].next_wake_time) >= 0) // is ready
                    {
                        if (tasks[alt_task_id].memory_intensity < m_cand)
                        {
                            int32_t alt_slack = (int32_t)(tasks[alt_task_id].deadline - current_time) - (int32_t)tasks[alt_task_id].wcet;
                            if ((alt_slack > 0) && (tasks[alt_task_id].wcet < slack))
                            {
                                // Swap cand_task_id and alt_task_id in the indices array
                                indices[cand_ready_idx] = alt_task_id;
                                indices[i] = cand_task_id;
                                break;
                            }
                        }
                    }
                }
            }
        }
    }

    // 5. Assign FreeRTOS priorities (Highest to indices[0], lowest to indices[count-1])
    UBaseType_t current_priority = count; // Max priority
    for (uint8_t i = 0; i < count; ++i) 
    {
        vTaskPrioritySet(tasks[indices[i]].handle, current_priority--);
    }
}

void ContextAwareScheduler::DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) 
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

        tasks[task_id].next_wake_time = absolute_deadline;
        
        vTaskSuspendAll(); // Disable context switches during priority calculation
        
        // The new absolute deadline is the next wake time + relative deadline (which is the period)
        tasks[task_id].deadline = absolute_deadline + tasks[task_id].period;
        m_last_executed_task = task_id;
        
        ApplyHeuristicAndUpdatePriorities();
        
        xTaskResumeAll(); // Re-enable context switches (preemption may happen here)
    }
    
    // Fall back to normal FreeRTOS blocking call
    vTaskDelayUntil(pxPreviousWakeTime, xTimeIncrement);
}

const char* ContextAwareScheduler::GetSchedulerName() const
{
    return "Context-Aware Scheduler";
}
