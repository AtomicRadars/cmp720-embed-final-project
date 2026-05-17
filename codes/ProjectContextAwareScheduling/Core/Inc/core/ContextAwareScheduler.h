#ifndef CONTEXT_AWARE_SCHEDULER_H
#define CONTEXT_AWARE_SCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include <stdint.h>

#include "core/IScheduler.h"

class ContextAwareScheduler : public IScheduler 
{
    public:
        ContextAwareScheduler(float alpha = 1.0f, float threshold = 0.15f, uint32_t safety_margin = 2);
        virtual ~ContextAwareScheduler() = default;

        virtual void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) override;
        const char* GetSchedulerName() const override;

    private:
        void ApplyHeuristicAndUpdatePriorities();
        
        inline bool IsTimeReached(const TickType_t current_time, const TickType_t wake_time) const noexcept
        {
            return static_cast<int32_t>(current_time - wake_time) >= 0;
        }

        inline int32_t TimeUntil(const TickType_t future_time, const TickType_t current_time) const noexcept
        {
            return static_cast<int32_t>(future_time - current_time);
        }

        inline bool IsTaskReadyForScheduling(const uint8_t task_id, const TickType_t current_time) const noexcept
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

            const eTaskState state{eTaskGetState(tasks[task_id].handle)};
            return (state == eReady) || (state == eRunning);
        }

        inline int32_t CalculateSlack(const TickType_t current_time, const TickType_t deadline_time, const TickType_t remaining_time) const noexcept
        {
            return TimeUntil(deadline_time, current_time) - static_cast<int32_t>(remaining_time);
        }

        float m_alpha;
        float m_threshold;
        uint32_t m_safety_margin;
};

#endif // CONTEXT_AWARE_SCHEDULER_H
