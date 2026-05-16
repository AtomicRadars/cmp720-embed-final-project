#include "core/ContextAwareScheduler.h"

ContextAwareScheduler::ContextAwareScheduler(float alpha, float threshold, uint32_t safety_margin)
    : m_alpha(alpha), m_threshold(threshold), m_safety_margin(safety_margin), m_last_executed_task(eMotorControl)
{
}

bool ContextAwareScheduler::IsTimeReached(const TickType_t current_time, const TickType_t wake_time) const noexcept
{
    return static_cast<int32_t>(current_time - wake_time) >= 0;
}

int32_t ContextAwareScheduler::TimeUntil(const TickType_t future_time, const TickType_t current_time) const noexcept
{
    return static_cast<int32_t>(future_time - current_time);
}

bool ContextAwareScheduler::IsTaskReadyForScheduling(const uint8_t task_id, const TickType_t current_time) const noexcept
{
    if (task_id >= TASK_COUNT)
    {
        return false;
    }

    if (!tasks[task_id].is_registered)
    {
        return false;
    }

    if (!IsTimeReached(current_time, tasks[task_id].next_wake_time))
    {
        return false;
    }

    // TODO If overhead is high we might remove this
    const eTaskState state{eTaskGetState(tasks[task_id].handle)};

    return (state == eReady) || (state == eRunning);
}

int32_t ContextAwareScheduler::CalculateSlack(const TickType_t current_time, const TickType_t deadline_time, const TickType_t remaining_time) const noexcept
{
    return TimeUntil(deadline_time, current_time) - static_cast<int32_t>(remaining_time);
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
            const uint8_t left_task_id = indices[j];
            const uint8_t right_task_id = indices[j + 1];

            const bool is_right_task_has_earlier_deadline = static_cast<int32_t>(tasks[left_task_id].deadline - tasks[right_task_id].deadline) > 0;

            if (is_right_task_has_earlier_deadline)
            {
                uint8_t temp = indices[j];
                indices[j] = indices[j + 1];
                indices[j + 1] = temp;
            }
        }
    }

    // 3. Find the highest priority READY task
    int8_t cand_ready_idx = -1;
    for (uint8_t i = 0; i < count; ++i)
    {
        if (IsTaskReadyForScheduling(indices[i], current_time))
        {
            cand_ready_idx = static_cast<int8_t>(i);
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
            const int32_t cand_slack = CalculateSlack(current_time, tasks[cand_task_id].deadline, tasks[cand_task_id].wcet);
            if (cand_slack > static_cast<int32_t>(m_safety_margin))
            {
                // Find T_alt (a lower priority ready task)
                for (uint8_t i = static_cast<uint8_t>(cand_ready_idx + 1); i < count; ++i)
                {
                    const uint8_t alt_task_id = indices[i];

                    if (!IsTaskReadyForScheduling(alt_task_id, current_time))
                    {
                        continue;
                    }

                    if (tasks[alt_task_id].memory_intensity >= m_cand)
                    {
                        continue;
                    }

                    const int32_t alt_slack = CalculateSlack(current_time, tasks[alt_task_id].deadline, tasks[alt_task_id].wcet);

                    if (alt_slack <= 0)
                    {
                        continue;
                    }

                    const int32_t alt_cost = static_cast<int32_t>(tasks[alt_task_id].wcet);

                    // Candidate's slack should be greater than alt task's execution time plus the safety margin
                    if (cand_slack > alt_cost + static_cast<int32_t>(m_safety_margin))
                    {
                        indices[cand_ready_idx] = alt_task_id;
                        indices[i] = cand_task_id;
                        break;
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

const char *ContextAwareScheduler::GetSchedulerName() const
{
    return "Context-Aware Scheduler";
}
